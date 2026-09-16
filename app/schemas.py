from typing import Annotated
from pydantic import BaseModel, Field, StringConstraints, field_validator, field_serializer
from datetime import datetime

DATA_PATTERN_BR = r"^\d{2}-\d{2}-\d{4}$"
HORA_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

DataStrBR = Annotated[str, StringConstraints(pattern=DATA_PATTERN_BR)]


def data_br_para_iso(data_br: str) -> str:
    dia, mes, ano = data_br.split("-")
    return f"{ano}-{mes}-{dia}"


def data_iso_para_br(data_iso: str) -> str:
    ano, mes, dia = data_iso.split("-")
    return f"{dia}-{mes}-{ano}"


class ResultadoData(BaseModel):
    data: str
    classificacao: str
    chance_chuva: int | None = None

    @field_serializer("data")
    def _data_para_br(self, v: str) -> str:
        return data_iso_para_br(v)


class EventoCreate(BaseModel):
    nome: str
    tipo_evento: str
    cidade: str
    data_evento: DataStrBR = Field(description="Data no formato DD-MM-AAAA")
    hora: str | None = Field(default=None, pattern=HORA_PATTERN)
    descricao: str | None = None

    @field_validator("data_evento")
    @classmethod
    def _data_para_iso(cls, v: str) -> str:
        return data_br_para_iso(v)


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

    @field_serializer("data_evento")
    def _data_para_br(self, v: str) -> str:
        return data_iso_para_br(v)


class SugestaoMelhorDataCreate(BaseModel):
    nome: str | None = None
    cidade: str
    tipo_evento: str
    datas_candidatas: list[DataStrBR] = Field(description="Datas no formato DD-MM-AAAA")

    @field_validator("datas_candidatas")
    @classmethod
    def _datas_para_iso(cls, v: list[str]) -> list[str]:
        return [data_br_para_iso(data) for data in v]


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

    @field_serializer("datas_candidatas")
    def _datas_para_br(self, v: list[str]) -> list[str]:
        return [data_iso_para_br(data) for data in v]

    @field_serializer("melhor_data")
    def _melhor_data_para_br(self, v: str | None) -> str | None:
        return data_iso_para_br(v) if v else None
