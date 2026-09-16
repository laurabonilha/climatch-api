from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.database import Base, engine, get_db
from app import models
from app.schemas import (
    EventoCreate, EventoOut,
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


@app.get("/eventos", response_model=list[EventoOut])
def listar_eventos(cidade: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Evento)
    if cidade:
        query = query.filter(func.lower(models.Evento.cidade) == cidade.strip().lower())
    return query.order_by(models.Evento.data_evento).all()


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


@app.delete("/sugestoes-data/{sugestao_id}", status_code=204)
def remover_sugestao_melhor_data(sugestao_id: int, db: Session = Depends(get_db)):
    sugestao = db.query(models.SugestaoMelhorData).filter(models.SugestaoMelhorData.id == sugestao_id).first()
    if not sugestao:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    db.delete(sugestao)
    db.commit()