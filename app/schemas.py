from pydantic import BaseModel, Field
from datetime import datetime

DATA_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
HORA_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

class ConsultaClimaOut(BaseModel):
    id: int
    cidade: str
    data_consultada: str
    temp_min: float
    temp_max: float
    chance_chuva: int
    vento_max: float
    consultado_em: datetime

    class Config:
        from_attributes = True


class AvaliarEventoRequest(BaseModel):
    cidade: str
    data: str = Field(pattern=DATA_PATTERN, description="Data no formato AAAA-MM-DD")
    hora: str | None = Field(default=None, pattern=HORA_PATTERN, description="Hora no formato HH:MM (24h)")
    tipo_evento: str


class CondicoesHorario(BaseModel):
    hora: str
    temperatura: float
    chance_chuva: int
    vento: float


class MelhorHorario(BaseModel):
    hora: str
    motivo: str


class AvaliarEventoResponse(BaseModel):
    classificacao_geral: str
    recomendacao: str
    tipo_evento_reconhecido: bool
    condicoes_no_horario_informado: CondicoesHorario | None = None
    melhor_horario: MelhorHorario


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