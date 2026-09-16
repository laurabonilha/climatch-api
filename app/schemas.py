from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints
from datetime import datetime

DATA_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
HORA_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

DataStr = Annotated[str, StringConstraints(pattern=DATA_PATTERN)]

class ResultadoData(BaseModel):
    data: str
    classificacao: str
    chance_chuva: int | None = None


class EventoCreate(BaseModel):
    nome: str
    tipo_evento: str
    cidade: str
    data_evento: DataStr
    hora: str | None = Field(default=None, pattern=HORA_PATTERN)
    descricao: str | None = None


class EventoOut(BaseModel):
    id: int
    nome: str
    tipo_evento: str
    cidade: str
    data_evento: str
    hora: str | None
    descricao: str | None
    classificacao_geral: str
    recomendacao: str
    tipo_evento_reconhecido: bool
    melhor_horario_hora: str
    melhor_horario_motivo: str
    condicoes_horario_temperatura: float | None
    condicoes_horario_chance_chuva: int | None
    condicoes_horario_vento: float | None
    criado_em: datetime

    class Config:
        from_attributes = True


class SugestaoMelhorDataCreate(BaseModel):
    nome: str | None = None
    cidade: str
    tipo_evento: str
    datas_candidatas: list[DataStr]


class SugestaoMelhorDataOut(BaseModel):
    id: int
    nome: str | None
    cidade: str
    tipo_evento: str
    datas_candidatas: list[str]
    resultados: list[ResultadoData]
    melhor_data: str | None
    criado_em: datetime

    class Config:
        from_attributes = True