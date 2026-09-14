from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import Base, engine, get_db
from app import models
from app.schemas import (
    ConsultaClimaOut, AvaliarEventoRequest, AvaliarEventoResponse,
    LoteRequest, LoteResponse, ResultadoLote,
)
from app.services.openmeteo import (
    buscar_coordenadas, buscar_previsao, buscar_previsao_horaria,
    CidadeNaoEncontrada, PrevisaoIndisponivel,
)
from app.services.risco import (
    classificar_risco, obter_limites_por_tipo, gerar_recomendacao, calcular_melhor_horario,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Climatch API")


@app.get("/health")
def health_check():
    return {"status": "ok"}


def obter_previsao_cacheada(cidade: str, data: str, db: Session) -> dict:
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
        return {
            "temp_min": registro.temp_min,
            "temp_max": registro.temp_max,
            "chance_chuva": registro.chance_chuva,
            "vento_max": registro.vento_max,
        }

    try:
        lat, lon = buscar_coordenadas(cidade)
    except CidadeNaoEncontrada:
        raise HTTPException(status_code=404, detail="Cidade não encontrada")

    try:
        dados_previsao = buscar_previsao(lat, lon, data)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão indisponível para essa data")

    classificacao_padrao = classificar_risco(dados_previsao)

    novo_registro = models.ConsultaClima(
        cidade=cidade,
        data_consultada=data,
        temp_min=dados_previsao["temp_min"],
        temp_max=dados_previsao["temp_max"],
        chance_chuva=dados_previsao["chance_chuva"],
        vento_max=dados_previsao["vento_max"],
        classificacao=classificacao_padrao,
    )
    db.add(novo_registro)
    db.commit()

    return dados_previsao


@app.post("/previsao/avaliar-evento", response_model=AvaliarEventoResponse)
def avaliar_evento(pedido: AvaliarEventoRequest, db: Session = Depends(get_db)):
    dados = obter_previsao_cacheada(pedido.cidade, pedido.data, db)

    limites = obter_limites_por_tipo(pedido.tipo_evento)
    classificacao = classificar_risco(dados, limites["chance_chuva_limite"], limites["vento_limite"])
    recomendacao = gerar_recomendacao(pedido.tipo_evento, classificacao)

    try:
        lat, lon = buscar_coordenadas(pedido.cidade)
    except CidadeNaoEncontrada:
        raise HTTPException(status_code=404, detail="Cidade não encontrada")

    try:
        dados_horarios = buscar_previsao_horaria(lat, lon, pedido.data)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão horária indisponível para essa data")

    melhor_horario, motivo_horario = calcular_melhor_horario(
        dados_horarios["horarios"], dados_horarios["chance_chuva_horaria"]
    )

    return AvaliarEventoResponse(
        classificacao=classificacao,
        recomendacao=recomendacao,
        melhor_horario=melhor_horario,
        motivo_horario=motivo_horario,
    )


@app.post("/previsao/lote", response_model=LoteResponse)
def avaliar_lote(pedido: LoteRequest, db: Session = Depends(get_db)):
    resultados = []
    for item in pedido.consultas:
        try:
            dados = obter_previsao_cacheada(item.cidade, item.data, db)
            classificacao = classificar_risco(dados)
        except HTTPException:
            classificacao = "indisponivel"

        resultados.append(ResultadoLote(cidade=item.cidade, data=item.data, classificacao=classificacao))

    return LoteResponse(resultados=resultados)


@app.get("/previsao/historico", response_model=list[ConsultaClimaOut])
def listar_historico(cidade: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ConsultaClima)
    if cidade:
        query = query.filter(models.ConsultaClima.cidade == cidade)
    return query.order_by(models.ConsultaClima.consultado_em.desc()).all()


@app.delete("/previsao/historico/{consulta_id}", status_code=204)
def remover_consulta(consulta_id: int, db: Session = Depends(get_db)):
    consulta = db.query(models.ConsultaClima).filter(models.ConsultaClima.id == consulta_id).first()
    if not consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    db.delete(consulta)
    db.commit()