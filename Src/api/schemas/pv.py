from __future__ import annotations

from pydantic import BaseModel, Field


class PVResultado(BaseModel):
    pmpv: float
    pr: float
    pv: float


class PVSalvarRequest(BaseModel):
    periodo: str
    pmpv: float
    pr: float


class PVSalvarResponse(BaseModel):
    pv: float


class PVCriarPeriodoRequest(BaseModel):
    nome: str


class PVSalvo(BaseModel):
    pmpv: float
    pr: float
    pv: float
    data: str = ""


class PVTrimestreResultado(BaseModel):
    chave: str              # "Fev - Abr/2026"
    periodos: list[str]     # ["Fev/2026", "Mar/2026", "Abr/2026"]
    pmpv: float             # valores atuais dos módulos PMPV e PR
    pr: float
    pv: float
    salvo: PVSalvo | None = None  # PV já gravado (o que o Excel Final usa)
    avisos: list[str] = []


class PVTrimestreSalvarRequest(BaseModel):
    trimestre: str          # "Fev - Abr"
    ano: int = Field(ge=2000, le=2098)  # ano do 1º mês (Nov – Jan/2098 termina em 2099)
    pmpv: float = Field(allow_inf_nan=False)
    pr: float = Field(allow_inf_nan=False)


class PVTrimestreSalvarResponse(BaseModel):
    pv: float
    gravado_em: list[str]   # chave do trimestre + os 3 meses
