from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints
from datetime import datetime

DATA_PATTERN = r"^\d{4}-\d{2}-\d{2}$"
HORA_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

DataStr = Annotated[str, StringConstraints(pattern=DATA_PATTERN)]

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


class EventoItem(BaseModel):
    cidade: str
    data: DataStr
    tipo_evento: str | None = None


class EventosEmRiscoRequest(BaseModel):
    eventos: list[EventoItem]


class ResultadoEmRisco(BaseModel):
    cidade: str
    data: str
    classificacao: str
    em_risco: bool


class EventosEmRiscoResponse(BaseModel):
    resultados: list[ResultadoEmRisco]


class MelhorDataRequest(BaseModel):
    cidade: str
    tipo_evento: str
    datas: list[DataStr]


class ResultadoData(BaseModel):
    data: str
    classificacao: str
    chance_chuva: int | None = None


class MelhorDataResponse(BaseModel):
    resultados: list[ResultadoData]
    melhor_data: str | None = None


class EstatisticaCidade(BaseModel):
    cidade: str
    total_consultas: int
    chance_chuva_media: float | None = None
    vento_max_medio: float | None = None
    temperatura_media: float | None = None


class EstatisticasResponse(BaseModel):
    cidades: list[EstatisticaCidade]


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


class ResultadoEmRiscoEvento(BaseModel):
    id: int
    nome: str
    cidade: str
    data_evento: str
    classificacao: str
    em_risco: bool


class EventosEmRiscoSalvosResponse(BaseModel):
    resultados: list[ResultadoEmRiscoEvento]


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