from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import Base, engine, get_db
from app import models
from app.schemas import (
    ConsultaClimaOut, AvaliarEventoRequest, AvaliarEventoResponse, MelhorHorario,
    EventosEmRiscoRequest, EventosEmRiscoResponse, ResultadoEmRisco,
    MelhorDataRequest, MelhorDataResponse, ResultadoData,
    EstatisticaCidade, EstatisticasResponse,
)
from app.services.openmeteo import (
    buscar_coordenadas, buscar_previsao, buscar_previsao_horaria,
    CidadeNaoEncontrada, PrevisaoIndisponivel, ServicoExternoIndisponivel,
)
from app.services.risco import (
    classificar_risco, obter_limites_por_tipo, tipo_evento_reconhecido, gerar_recomendacao,
    calcular_melhor_horario, obter_condicoes_no_horario, escolher_melhor,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Climatch API")


@app.get("/health")
def health_check():
    return {"status": "ok"}


def obter_previsao_cacheada(cidade: str, data: str, db: Session) -> tuple[dict, tuple[float, float] | None]:
    uma_hora_atras = datetime.utcnow() - timedelta(hours=1)

    registro = (
        db.query(models.ConsultaClima)
        .filter(
            models.ConsultaClima.cidade == cidade,
            models.ConsultaClima.data_consultada == data,
            models.ConsultaClima.consultado_em >= uma_hora_atras,
        )
        .order_by(models.ConsultaClima.consultado_em.desc())
        .first()
    )

    if registro:
        dados = {
            "temp_min": registro.temp_min,
            "temp_max": registro.temp_max,
            "chance_chuva": registro.chance_chuva,
            "vento_max": registro.vento_max,
        }
        return dados, None

    try:
        lat, lon = buscar_coordenadas(cidade)
    except CidadeNaoEncontrada:
        raise HTTPException(status_code=404, detail="Cidade não encontrada")
    except ServicoExternoIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço de geocodificação indisponível no momento")

    try:
        dados_previsao = buscar_previsao(lat, lon, data)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão indisponível para essa data")
    except ServicoExternoIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço de previsão indisponível no momento")

    novo_registro = models.ConsultaClima(
        cidade=cidade,
        data_consultada=data,
        temp_min=dados_previsao["temp_min"],
        temp_max=dados_previsao["temp_max"],
        chance_chuva=dados_previsao["chance_chuva"],
        vento_max=dados_previsao["vento_max"],
    )
    db.add(novo_registro)
    db.commit()

    return dados_previsao, (lat, lon)


@app.post("/previsao/avaliar-evento", response_model=AvaliarEventoResponse)
def avaliar_evento(pedido: AvaliarEventoRequest, db: Session = Depends(get_db)):
    dados_diarios, coordenadas = obter_previsao_cacheada(pedido.cidade, pedido.data, db)

    limites = obter_limites_por_tipo(pedido.tipo_evento)
    reconhecido = tipo_evento_reconhecido(pedido.tipo_evento)
    classificacao_geral = classificar_risco(dados_diarios, limites["chance_chuva_limite"], limites["vento_limite"])
    recomendacao = gerar_recomendacao(pedido.tipo_evento, classificacao_geral, reconhecido)

    if coordenadas:
        lat, lon = coordenadas
    else:
        try:
            lat, lon = buscar_coordenadas(pedido.cidade)
        except CidadeNaoEncontrada:
            raise HTTPException(status_code=404, detail="Cidade não encontrada")
        except ServicoExternoIndisponivel:
            raise HTTPException(status_code=503, detail="Serviço de geocodificação indisponível no momento")

    try:
        dados_horarios = buscar_previsao_horaria(lat, lon, pedido.data)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão horária indisponível para essa data")
    except ServicoExternoIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço de previsão indisponível no momento")

    melhor_horario_valor, motivo_horario = calcular_melhor_horario(
        dados_horarios["horarios"], dados_horarios["chance_chuva_horaria"]
    )

    condicoes_no_horario = None
    if pedido.hora:
        condicoes_no_horario = obter_condicoes_no_horario(
            dados_horarios["horarios"],
            dados_horarios["temperatura_horaria"],
            dados_horarios["chance_chuva_horaria"],
            dados_horarios["vento_horario"],
            pedido.hora,
        )

    return AvaliarEventoResponse(
        classificacao_geral=classificacao_geral,
        recomendacao=recomendacao,
        tipo_evento_reconhecido=reconhecido,
        condicoes_no_horario_informado=condicoes_no_horario,
        melhor_horario=MelhorHorario(hora=melhor_horario_valor, motivo=motivo_horario),
    )


@app.post("/previsao/eventos-em-risco", response_model=EventosEmRiscoResponse)
def eventos_em_risco(pedido: EventosEmRiscoRequest, db: Session = Depends(get_db)):
    resultados = []
    for evento in pedido.eventos:
        try:
            dados, _ = obter_previsao_cacheada(evento.cidade, evento.data, db)
            limites = obter_limites_por_tipo(evento.tipo_evento)
            classificacao = classificar_risco(dados, limites["chance_chuva_limite"], limites["vento_limite"])
        except HTTPException:
            classificacao = "indisponivel"

        resultados.append(ResultadoEmRisco(
            cidade=evento.cidade,
            data=evento.data,
            classificacao=classificacao,
            em_risco=(classificacao == "arriscado"),
        ))

    return EventosEmRiscoResponse(resultados=resultados)


@app.post("/previsao/melhor-data", response_model=MelhorDataResponse)
def melhor_data(pedido: MelhorDataRequest, db: Session = Depends(get_db)):
    limites = obter_limites_por_tipo(pedido.tipo_evento)
    resultados = []
    for data in pedido.datas:
        try:
            dados, _ = obter_previsao_cacheada(pedido.cidade, data, db)
            classificacao = classificar_risco(dados, limites["chance_chuva_limite"], limites["vento_limite"])
            chance_chuva = dados["chance_chuva"]
        except HTTPException:
            classificacao = "indisponivel"
            chance_chuva = None

        resultados.append(ResultadoData(data=data, classificacao=classificacao, chance_chuva=chance_chuva))

    melhor = escolher_melhor([resultado.model_dump() for resultado in resultados])

    return MelhorDataResponse(
        resultados=resultados,
        melhor_data=melhor["data"] if melhor else None,
    )


@app.get("/previsao/estatisticas", response_model=EstatisticaCidade | EstatisticasResponse)
def estatisticas(cidade: str | None = None, db: Session = Depends(get_db)):
    query = db.query(
        models.ConsultaClima.cidade,
        func.count(models.ConsultaClima.id).label("total_consultas"),
        func.avg(models.ConsultaClima.chance_chuva).label("chance_chuva_media"),
        func.avg(models.ConsultaClima.vento_max).label("vento_max_medio"),
        func.avg((models.ConsultaClima.temp_min + models.ConsultaClima.temp_max) / 2).label("temperatura_media"),
    ).group_by(models.ConsultaClima.cidade)

    if cidade:
        registro = query.filter(models.ConsultaClima.cidade == cidade).first()
        if not registro:
            return EstatisticaCidade(cidade=cidade, total_consultas=0)
        return EstatisticaCidade(
            cidade=registro.cidade,
            total_consultas=registro.total_consultas,
            chance_chuva_media=round(registro.chance_chuva_media, 1),
            vento_max_medio=round(registro.vento_max_medio, 1),
            temperatura_media=round(registro.temperatura_media, 1),
        )

    registros = query.all()
    return EstatisticasResponse(cidades=[
        EstatisticaCidade(
            cidade=r.cidade,
            total_consultas=r.total_consultas,
            chance_chuva_media=round(r.chance_chuva_media, 1),
            vento_max_medio=round(r.vento_max_medio, 1),
            temperatura_media=round(r.temperatura_media, 1),
        )
        for r in registros
    ])


@app.get("/previsao/historico", response_model=list[ConsultaClimaOut])
def listar_historico(cidade: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ConsultaClima)
    if cidade:
        query = query.filter(models.ConsultaClima.cidade == cidade)
    return query.order_by(models.ConsultaClima.consultado_em.desc()).all()


@app.patch("/previsao/historico/{consulta_id}", response_model=ConsultaClimaOut)
def atualizar_consulta(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.ConsultaClima).filter(models.ConsultaClima.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")

    try:
        lat, lon = buscar_coordenadas(consulta.cidade)
    except CidadeNaoEncontrada:
        raise HTTPException(status_code=404, detail="Cidade não encontrada")
    except ServicoExternoIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço de geocodificação indisponível no momento")

    try:
        dados_previsao = buscar_previsao(lat, lon, consulta.data_consultada)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão indisponível para essa data")
    except ServicoExternoIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço de previsão indisponível no momento")

    consulta.temp_min = dados_previsao["temp_min"]
    consulta.temp_max = dados_previsao["temp_max"]
    consulta.chance_chuva = dados_previsao["chance_chuva"]
    consulta.vento_max = dados_previsao["vento_max"]
    consulta.consultado_em = datetime.utcnow()
    db.commit()
    db.refresh(consulta)

    return consulta


@app.delete("/previsao/historico/{consulta_id}", status_code=204)
def remover_consulta(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.ConsultaClima).filter(models.ConsultaClima.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    db.delete(consulta)
    db.commit()