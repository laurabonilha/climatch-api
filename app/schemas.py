from pydantic import BaseModel
from datetime import datetime

class ConsultaClimaOut(BaseModel):
    id: int
    cidade: str
    data_consultada: str
    temp_min: float
    temp_max: float
    chance_chuva: int
    vento_max: float
    classificacao: str
    consultado_em: datetime

    class Config:
        from_attributes = True


class AvaliarEventoRequest(BaseModel):
    cidade: str
    data: str
    tipo_evento: str


class AvaliarEventoResponse(BaseModel):
    classificacao: str
    recomendacao: str
    melhor_horario: str
    motivo_horario: str


class ConsultaItem(BaseModel):
    cidade: str
    data: str


class LoteRequest(BaseModel):
    consultas: list[ConsultaItem]


class ResultadoLote(BaseModel):
    cidade: str
    data: str
    classificacao: str


class LoteResponse(BaseModel):
    resultados: list[ResultadoLote]