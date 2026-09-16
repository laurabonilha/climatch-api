from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    EventoCreate, EventoOut, ResultadoEmRiscoEvento, EventosEmRiscoSalvosResponse,
    SugestaoMelhorDataCreate, SugestaoMelhorDataOut,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


def obter_previsao_cacheada(cidade: str, data: str, db: Session) -> tuple[dict, tuple[float, float] | None]:
    uma_hora_atras = datetime.utcnow() - timedelta(hours=1)

    registro = (
        db.query(models.ConsultaClima)
        .filter(
            func.lower(models.ConsultaClima.cidade) == cidade.strip().lower(),
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


def avaliar_evento_core(cidade: str, data: str, hora: str | None, tipo_evento: str, db: Session) -> dict:
    dados_diarios, coordenadas = obter_previsao_cacheada(cidade, data, db)

    limites = obter_limites_por_tipo(tipo_evento)
    reconhecido = tipo_evento_reconhecido(tipo_evento)
    classificacao_geral = classificar_risco(dados_diarios, limites["chance_chuva_limite"], limites["vento_limite"])
    recomendacao = gerar_recomendacao(tipo_evento, classificacao_geral, reconhecido)

    if coordenadas:
        lat, lon = coordenadas
    else:
        try:
            lat, lon = buscar_coordenadas(cidade)
        except CidadeNaoEncontrada:
            raise HTTPException(status_code=404, detail="Cidade não encontrada")
        except ServicoExternoIndisponivel:
            raise HTTPException(status_code=503, detail="Serviço de geocodificação indisponível no momento")

    try:
        dados_horarios = buscar_previsao_horaria(lat, lon, data)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão horária indisponível para essa data")
    except ServicoExternoIndisponivel:
        raise HTTPException(status_code=503, detail="Serviço de previsão indisponível no momento")

    melhor_horario_valor, motivo_horario = calcular_melhor_horario(
        dados_horarios["horarios"], dados_horarios["chance_chuva_horaria"]
    )

    condicoes_no_horario = None
    if hora:
        condicoes_no_horario = obter_condicoes_no_horario(
            dados_horarios["horarios"],
            dados_horarios["temperatura_horaria"],
            dados_horarios["chance_chuva_horaria"],
            dados_horarios["vento_horario"],
            hora,
        )

    return {
        "classificacao_geral": classificacao_geral,
        "recomendacao": recomendacao,
        "tipo_evento_reconhecido": reconhecido,
        "condicoes_no_horario_informado": condicoes_no_horario,
        "melhor_horario_hora": melhor_horario_valor,
        "melhor_horario_motivo": motivo_horario,
    }


@app.post("/previsao/avaliar-evento", response_model=AvaliarEventoResponse)
def avaliar_evento(pedido: AvaliarEventoRequest, db: Session = Depends(get_db)):
    resultado = avaliar_evento_core(pedido.cidade, pedido.data, pedido.hora, pedido.tipo_evento, db)

    return AvaliarEventoResponse(
        classificacao_geral=resultado["classificacao_geral"],
        recomendacao=resultado["recomendacao"],
        tipo_evento_reconhecido=resultado["tipo_evento_reconhecido"],
        condicoes_no_horario_informado=resultado["condicoes_no_horario_informado"],
        melhor_horario=MelhorHorario(
            hora=resultado["melhor_horario_hora"],
            motivo=resultado["melhor_horario_motivo"],
        ),
    )


def avaliar_lista_em_risco(itens: list[tuple[str, str, str | None]], db: Session) -> list[dict]:
    resultados = []
    for cidade, data, tipo_evento in itens:
        try:
            dados, _ = obter_previsao_cacheada(cidade, data, db)
            limites = obter_limites_por_tipo(tipo_evento)
            classificacao = classificar_risco(dados, limites["chance_chuva_limite"], limites["vento_limite"])
        except HTTPException:
            classificacao = "indisponivel"

        resultados.append({
            "cidade": cidade,
            "data": data,
            "classificacao": classificacao,
            "em_risco": classificacao == "arriscado",
        })

    return resultados


@app.post("/previsao/eventos-em-risco", response_model=EventosEmRiscoResponse)
def eventos_em_risco(pedido: EventosEmRiscoRequest, db: Session = Depends(get_db)):
    itens = [(evento.cidade, evento.data, evento.tipo_evento) for evento in pedido.eventos]
    resultados = avaliar_lista_em_risco(itens, db)

    return EventosEmRiscoResponse(
        resultados=[ResultadoEmRisco(**resultado) for resultado in resultados]
    )


def calcular_melhor_data_core(cidade: str, tipo_evento: str, datas: list[str], db: Session) -> dict:
    limites = obter_limites_por_tipo(tipo_evento)
    resultados = []
    for data in datas:
        try:
            dados, _ = obter_previsao_cacheada(cidade, data, db)
            classificacao = classificar_risco(dados, limites["chance_chuva_limite"], limites["vento_limite"])
            chance_chuva = dados["chance_chuva"]
        except HTTPException:
            classificacao = "indisponivel"
            chance_chuva = None

        resultados.append({"data": data, "classificacao": classificacao, "chance_chuva": chance_chuva})

    melhor = escolher_melhor(resultados)

    return {"resultados": resultados, "melhor_data": melhor["data"] if melhor else None}


@app.post("/previsao/melhor-data", response_model=MelhorDataResponse)
def melhor_data(pedido: MelhorDataRequest, db: Session = Depends(get_db)):
    resultado = calcular_melhor_data_core(pedido.cidade, pedido.tipo_evento, pedido.datas, db)

    return MelhorDataResponse(
        resultados=[ResultadoData(**item) for item in resultado["resultados"]],
        melhor_data=resultado["melhor_data"],
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
        registro = query.filter(func.lower(models.ConsultaClima.cidade) == cidade.strip().lower()).first()
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
        query = query.filter(func.lower(models.ConsultaClima.cidade) == cidade.strip().lower())
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


def _condicoes_para_evento(resultado: dict) -> tuple:
    condicoes = resultado["condicoes_no_horario_informado"]
    if not condicoes:
        return None, None, None
    return condicoes["temperatura"], condicoes["chance_chuva"], condicoes["vento"]


def _aplicar_avaliacao_no_evento(evento: models.Evento, resultado: dict) -> None:
    temperatura, chance_chuva, vento = _condicoes_para_evento(resultado)
    evento.classificacao_geral = resultado["classificacao_geral"]
    evento.recomendacao = resultado["recomendacao"]
    evento.tipo_evento_reconhecido = resultado["tipo_evento_reconhecido"]
    evento.melhor_horario_hora = resultado["melhor_horario_hora"]
    evento.melhor_horario_motivo = resultado["melhor_horario_motivo"]
    evento.condicoes_horario_temperatura = temperatura
    evento.condicoes_horario_chance_chuva = chance_chuva
    evento.condicoes_horario_vento = vento


@app.post("/eventos", response_model=EventoOut, status_code=201)
def criar_evento(pedido: EventoCreate, db: Session = Depends(get_db)):
    resultado = avaliar_evento_core(pedido.cidade, pedido.data_evento, pedido.hora, pedido.tipo_evento, db)

    novo_evento = models.Evento(
        nome=pedido.nome,
        tipo_evento=pedido.tipo_evento,
        cidade=pedido.cidade,
        data_evento=pedido.data_evento,
        hora=pedido.hora,
        descricao=pedido.descricao,
    )
    _aplicar_avaliacao_no_evento(novo_evento, resultado)

    db.add(novo_evento)
    db.commit()
    db.refresh(novo_evento)

    return novo_evento


@app.get("/eventos/em-risco", response_model=EventosEmRiscoSalvosResponse)
def eventos_salvos_em_risco(db: Session = Depends(get_db)):
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    eventos = (
        db.query(models.Evento)
        .filter(models.Evento.data_evento >= hoje)
        .order_by(models.Evento.data_evento)
        .all()
    )

    itens = [(evento.cidade, evento.data_evento, evento.tipo_evento) for evento in eventos]
    resultados = avaliar_lista_em_risco(itens, db)

    resultados_anotados = [
        ResultadoEmRiscoEvento(
            id=evento.id,
            nome=evento.nome,
            cidade=resultado["cidade"],
            data_evento=resultado["data"],
            classificacao=resultado["classificacao"],
            em_risco=resultado["em_risco"],
        )
        for evento, resultado in zip(eventos, resultados)
    ]

    return EventosEmRiscoSalvosResponse(resultados=resultados_anotados)


@app.get("/eventos", response_model=list[EventoOut])
def listar_eventos(cidade: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Evento)
    if cidade:
        query = query.filter(func.lower(models.Evento.cidade) == cidade.strip().lower())
    return query.order_by(models.Evento.data_evento).all()


@app.get("/eventos/{evento_id}", response_model=EventoOut)
def obter_evento(evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return evento


@app.put("/eventos/{evento_id}", response_model=EventoOut)
def atualizar_evento(evento_id: int, pedido: EventoCreate, db: Session = Depends(get_db)):
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    precisa_reavaliar = (
        pedido.cidade.strip().lower() != evento.cidade.strip().lower()
        or pedido.data_evento != evento.data_evento
        or pedido.hora != evento.hora
        or pedido.tipo_evento.strip().lower() != evento.tipo_evento.strip().lower()
    )

    evento.nome = pedido.nome
    evento.tipo_evento = pedido.tipo_evento
    evento.cidade = pedido.cidade
    evento.data_evento = pedido.data_evento
    evento.hora = pedido.hora
    evento.descricao = pedido.descricao

    if precisa_reavaliar:
        resultado = avaliar_evento_core(pedido.cidade, pedido.data_evento, pedido.hora, pedido.tipo_evento, db)
        _aplicar_avaliacao_no_evento(evento, resultado)

    db.commit()
    db.refresh(evento)

    return evento


@app.delete("/eventos/{evento_id}", status_code=204)
def remover_evento(evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(models.Evento).filter(models.Evento.id == evento_id).first()
    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    db.delete(evento)
    db.commit()


@app.post("/sugestoes-data", response_model=SugestaoMelhorDataOut, status_code=201)
def criar_sugestao_melhor_data(pedido: SugestaoMelhorDataCreate, db: Session = Depends(get_db)):
    resultado = calcular_melhor_data_core(pedido.cidade, pedido.tipo_evento, pedido.datas_candidatas, db)

    nova_sugestao = models.SugestaoMelhorData(
        nome=pedido.nome,
        cidade=pedido.cidade,
        tipo_evento=pedido.tipo_evento,
        datas_candidatas=pedido.datas_candidatas,
        resultados=resultado["resultados"],
        melhor_data=resultado["melhor_data"],
    )
    db.add(nova_sugestao)
    db.commit()
    db.refresh(nova_sugestao)

    return nova_sugestao


@app.get("/sugestoes-data", response_model=list[SugestaoMelhorDataOut])
def listar_sugestoes_melhor_data(cidade: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.SugestaoMelhorData)
    if cidade:
        query = query.filter(func.lower(models.SugestaoMelhorData.cidade) == cidade.strip().lower())
    return query.order_by(models.SugestaoMelhorData.criado_em.desc()).all()


@app.get("/sugestoes-data/{sugestao_id}", response_model=SugestaoMelhorDataOut)
def obter_sugestao_melhor_data(sugestao_id: int, db: Session = Depends(get_db)):
    sugestao = db.query(models.SugestaoMelhorData).filter(models.SugestaoMelhorData.id == sugestao_id).first()
    if not sugestao:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    return sugestao


@app.put("/sugestoes-data/{sugestao_id}", response_model=SugestaoMelhorDataOut)
def atualizar_sugestao_melhor_data(sugestao_id: int, pedido: SugestaoMelhorDataCreate, db: Session = Depends(get_db)):
    sugestao = db.query(models.SugestaoMelhorData).filter(models.SugestaoMelhorData.id == sugestao_id).first()
    if not sugestao:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")

    resultado = calcular_melhor_data_core(pedido.cidade, pedido.tipo_evento, pedido.datas_candidatas, db)

    sugestao.nome = pedido.nome
    sugestao.cidade = pedido.cidade
    sugestao.tipo_evento = pedido.tipo_evento
    sugestao.datas_candidatas = pedido.datas_candidatas
    sugestao.resultados = resultado["resultados"]
    sugestao.melhor_data = resultado["melhor_data"]

    db.commit()
    db.refresh(sugestao)

    return sugestao


@app.delete("/sugestoes-data/{sugestao_id}", status_code=204)
def remover_sugestao_melhor_data(sugestao_id: int, db: Session = Depends(get_db)):
    sugestao = db.query(models.SugestaoMelhorData).filter(models.SugestaoMelhorData.id == sugestao_id).first()
    if not sugestao:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    db.delete(sugestao)
    db.commit()