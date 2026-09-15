from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base

class ConsultaClima(Base):
    __tablename__ = "consultas_clima"

    id = Column(Integer, primary_key=True, index=True)
    cidade = Column(String, nullable=False, index=True)
    data_consultada = Column(String, nullable=False)
    temp_min = Column(Float, nullable=False)
    temp_max = Column(Float, nullable=False)
    chance_chuva = Column(Integer, nullable=False)
    vento_max = Column(Float, nullable=False)
    consultado_em = Column(DateTime(timezone=True), server_default=func.now())


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    tipo_evento = Column(String, nullable=False)
    cidade = Column(String, nullable=False, index=True)
    data_evento = Column(String, nullable=False)
    hora = Column(String, nullable=True)
    descricao = Column(String, nullable=True)

    classificacao_geral = Column(String, nullable=False)
    recomendacao = Column(String, nullable=False)
    tipo_evento_reconhecido = Column(Boolean, nullable=False)
    melhor_horario_hora = Column(String, nullable=False)
    melhor_horario_motivo = Column(String, nullable=False)
    condicoes_horario_temperatura = Column(Float, nullable=True)
    condicoes_horario_chance_chuva = Column(Integer, nullable=True)
    condicoes_horario_vento = Column(Float, nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now())


class SugestaoMelhorData(Base):
    __tablename__ = "sugestoes_melhor_data"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=True)
    cidade = Column(String, nullable=False, index=True)
    tipo_evento = Column(String, nullable=False)
    datas_candidatas = Column(JSON, nullable=False)
    resultados = Column(JSON, nullable=False)
    melhor_data = Column(String, nullable=True)

    criado_em = Column(DateTime(timezone=True), server_default=func.now())