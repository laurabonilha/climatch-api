from sqlalchemy import Column, Integer, String, Float, DateTime
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
    classificacao = Column(String, nullable=False)
    consultado_em = Column(DateTime(timezone=True), server_default=func.now())