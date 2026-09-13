from pydantic import BaseModel, Field
from datetime import datetime

class PrevisaoResponse(BaseModel):
    cidade: str
    data: str
    temp_min: float
    temp_max: float
    chance_chuva: int
    classificacao: str

class ConsultaClimaOut(BaseModel):
    id: int
    cidade: str
    data_consultada: str
    temp_min: float
    temp_max: float
    chance_chuva: int
    classificacao: str
    consultado_em: datetime

    class Config:
        from_attributes = True

class LimiteCreate(BaseModel):
    chance_chuva_limite: int = Field(..., ge=0, le=100)
    vento_limite: float = Field(..., ge=0)