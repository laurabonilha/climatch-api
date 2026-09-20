from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, field_serializer
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
    """Resultado da avaliação climática de uma data candidata."""

    data: str = Field(examples=["29-09-2026"], description="Data avaliada, no formato DD-MM-AAAA")
    classificacao: str = Field(
        examples=["favoravel"],
        description="'favoravel', 'moderado', 'arriscado' ou 'indisponivel' (quando a previsão não pôde ser obtida)",
    )
    chance_chuva: int | None = Field(default=None, examples=[10], description="Chance de chuva (%) nessa data")

    @field_serializer("data")
    def _data_para_br(self, v: str) -> str:
        return data_iso_para_br(v)


class EventoCreate(BaseModel):
    """Dados para cadastrar um novo evento. A avaliação climática é calculada automaticamente no momento da criação."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nome": "Maratona de Sorocaba",
                "tipo_evento": "corrida",
                "cidade": "Sorocaba",
                "data_evento": "29-09-2026",
                "hora": "07:00",
                "descricao": "Prova de rua de 10km com largada na Praça da Matriz",
            }
        }
    )

    nome: str = Field(examples=["Maratona de Sorocaba"], description="Nome do evento")
    tipo_evento: str = Field(
        examples=["corrida"],
        description=(
            "Tipo do evento. Tipos reconhecidos (com limites de chuva/vento próprios): casamento, corrida, "
            "piquenique, praia, churrasco, futebol, show_ao_ar_livre, festa_infantil, trilha, acampamento, "
            "feira_ao_ar_livre, formatura_externa. Outros valores usam critérios genéricos."
        ),
    )
    cidade: str = Field(examples=["Sorocaba"], description="Cidade onde o evento ocorrerá")
    data_evento: DataStrBR = Field(examples=["29-09-2026"], description="Data do evento, no formato DD-MM-AAAA")
    hora: str | None = Field(
        default=None, pattern=HORA_PATTERN, examples=["07:00"], description="Horário do evento, formato HH:MM (24h)"
    )
    descricao: str | None = Field(
        default=None,
        examples=["Prova de rua de 10km com largada na Praça da Matriz"],
        description="Observações livres sobre o evento",
    )

    @field_validator("data_evento")
    @classmethod
    def _data_para_iso(cls, v: str) -> str:
        return data_br_para_iso(v)


class EventoAtualizar(BaseModel):
    """
    Dados para refinar um evento já existente. Cidade, data e tipo de evento não podem ser
    alterados por aqui (mudar esses dados equivaleria a outro evento — remova e recrie o evento
    se for o caso). Toda atualização força uma nova consulta de previsão do tempo, o que é
    útil para reavaliar o clima conforme a data do evento se aproxima.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nome": "Maratona de Sorocaba",
                "hora": "09:00",
                "descricao": "Horário alterado devido à previsão de calor mais cedo",
            }
        }
    )

    nome: str | None = Field(default=None, examples=["Maratona de Sorocaba"], description="Novo nome do evento")
    hora: str | None = Field(
        default=None, pattern=HORA_PATTERN, examples=["09:00"], description="Novo horário do evento, formato HH:MM (24h)"
    )
    descricao: str | None = Field(
        default=None,
        examples=["Horário alterado devido à previsão de calor mais cedo"],
        description="Novas observações sobre o evento",
    )


class EventoOut(BaseModel):
    """Evento cadastrado, incluindo o resultado mais recente da avaliação climática."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "nome": "Maratona de Sorocaba",
                "tipo_evento": "corrida",
                "cidade": "Sorocaba",
                "data_evento": "29-09-2026",
                "hora": "07:00",
                "descricao": "Prova de rua de 10km com largada na Praça da Matriz",
                "classificacao_geral": "favoravel",
                "recomendacao": "Condições favoráveis para corrida.",
                "tipo_evento_reconhecido": True,
                "melhor_horario_hora": "07:00",
                "melhor_horario_motivo": "menor chance de chuva no período da manhã",
                "condicoes_horario_temperatura": 21.4,
                "condicoes_horario_chance_chuva": 5,
                "condicoes_horario_vento": 12.3,
                "criado_em": "2026-09-19T10:30:00Z",
            }
        },
    )

    id: int = Field(examples=[1])
    nome: str = Field(examples=["Maratona de Sorocaba"])
    tipo_evento: str = Field(examples=["corrida"])
    cidade: str = Field(examples=["Sorocaba"])
    data_evento: str = Field(examples=["29-09-2026"], description="Data do evento, no formato DD-MM-AAAA")
    hora: str | None = Field(examples=["07:00"])
    descricao: str | None = Field(examples=["Prova de rua de 10km com largada na Praça da Matriz"])
    classificacao_geral: str = Field(
        examples=["favoravel"], description="'favoravel', 'moderado' ou 'arriscado'"
    )
    recomendacao: str = Field(examples=["Condições favoráveis para corrida."])
    tipo_evento_reconhecido: bool = Field(
        examples=[True], description="Se o tipo de evento tem limites de risco próprios mapeados"
    )
    melhor_horario_hora: str = Field(examples=["07:00"], description="Horário do dia com menor chance de chuva")
    melhor_horario_motivo: str = Field(examples=["menor chance de chuva no período da manhã"])
    condicoes_horario_temperatura: float | None = Field(examples=[21.4], description="Temperatura (°C) prevista para o horário informado")
    condicoes_horario_chance_chuva: int | None = Field(examples=[5], description="Chance de chuva (%) prevista para o horário informado")
    condicoes_horario_vento: float | None = Field(examples=[12.3], description="Velocidade do vento (km/h) prevista para o horário informado")
    criado_em: datetime

    @field_serializer("data_evento")
    def _data_para_br(self, v: str) -> str:
        return data_iso_para_br(v)


class SugestaoMelhorDataCreate(BaseModel):
    """Compara datas candidatas para o mesmo evento (cidade + tipo) e aponta a melhor delas."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nome": "Casamento ao ar livre",
                "cidade": "Campos do Jordão",
                "tipo_evento": "casamento",
                "datas_candidatas": ["20-09-2026", "21-09-2026", "22-09-2026"],
            }
        }
    )

    nome: str | None = Field(default=None, examples=["Casamento ao ar livre"], description="Nome opcional para identificar a consulta")
    cidade: str = Field(examples=["Campos do Jordão"])
    tipo_evento: str = Field(examples=["casamento"])
    datas_candidatas: list[DataStrBR] = Field(
        examples=[["20-09-2026", "21-09-2026", "22-09-2026"]],
        description="Datas candidatas a avaliar, no formato DD-MM-AAAA",
    )

    @field_validator("datas_candidatas")
    @classmethod
    def _datas_para_iso(cls, v: list[str]) -> list[str]:
        return [data_br_para_iso(data) for data in v]


class SugestaoMelhorDataOut(BaseModel):
    """Resultado da comparação entre as datas candidatas, com a melhor data apontada."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "nome": "Casamento ao ar livre",
                "cidade": "Campos do Jordão",
                "tipo_evento": "casamento",
                "datas_candidatas": ["20-09-2026", "21-09-2026", "22-09-2026"],
                "resultados": [
                    {"data": "20-09-2026", "classificacao": "moderado", "chance_chuva": 35},
                    {"data": "21-09-2026", "classificacao": "favoravel", "chance_chuva": 10},
                    {"data": "22-09-2026", "classificacao": "arriscado", "chance_chuva": 70},
                ],
                "melhor_data": "21-09-2026",
                "criado_em": "2026-09-19T10:30:00Z",
            }
        },
    )

    id: int = Field(examples=[1])
    nome: str | None = Field(examples=["Casamento ao ar livre"])
    cidade: str = Field(examples=["Campos do Jordão"])
    tipo_evento: str = Field(examples=["casamento"])
    datas_candidatas: list[str] = Field(examples=[["20-09-2026", "21-09-2026", "22-09-2026"]])
    resultados: list[ResultadoData]
    melhor_data: str | None = Field(examples=["21-09-2026"], description="Data candidata com a melhor previsão")
    criado_em: datetime

    @field_serializer("datas_candidatas")
    def _datas_para_br(self, v: list[str]) -> list[str]:
        return [data_iso_para_br(data) for data in v]

    @field_serializer("melhor_data")
    def _melhor_data_para_br(self, v: str | None) -> str | None:
        return data_iso_para_br(v) if v else None
