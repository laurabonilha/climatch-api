from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import Base, engine, get_db
from app import models
from app.schemas import PrevisaoResponse
from app.services.openmeteo import buscar_coordenadas, buscar_previsao, CidadeNaoEncontrada, PrevisaoIndisponivel
from app.services.risco import classificar_risco

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Climatch API")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/previsao", response_model=PrevisaoResponse)
def calcular_previsao(cidade: str, data: str, db: Session = Depends(get_db)):
    uma_hora_atras = datetime.utcnow() - timedelta(hours=1)

    registro_existente = (
        db.query(models.ConsultaClima)
        .filter(
            models.ConsultaClima.cidade == cidade,
            models.ConsultaClima.data_consultada == data,
            models.ConsultaClima.consultado_em >= uma_hora_atras,
        )
        .order_by(models.ConsultaClima.consultado_em.desc())
        .first()
    )

    if registro_existente:
        return PrevisaoResponse(
            cidade=registro_existente.cidade,
            data=registro_existente.data_consultada,
            temp_min=registro_existente.temp_min,
            temp_max=registro_existente.temp_max,
            chance_chuva=registro_existente.chance_chuva,
            classificacao=registro_existente.classificacao,
        )

    try:
        lat, lon = buscar_coordenadas(cidade)
    except CidadeNaoEncontrada:
        raise HTTPException(status_code=404, detail="Cidade não encontrada")

    try:
        dados_previsao = buscar_previsao(lat, lon, data)
    except PrevisaoIndisponivel:
        raise HTTPException(status_code=400, detail="Previsão indisponível para essa data")

    classificacao = classificar_risco(dados_previsao)

    novo_registro = models.ConsultaClima(
        cidade=cidade,
        data_consultada=data,
        temp_min=dados_previsao["temp_min"],
        temp_max=dados_previsao["temp_max"],
        chance_chuva=dados_previsao["chance_chuva"],
        classificacao=classificacao,
    )
    db.add(novo_registro)
    db.commit()
    db.refresh(novo_registro)

    return PrevisaoResponse(
        cidade=cidade,
        data=data,
        temp_min=dados_previsao["temp_min"],
        temp_max=dados_previsao["temp_max"],
        chance_chuva=dados_previsao["chance_chuva"],
        classificacao=classificacao,
    )