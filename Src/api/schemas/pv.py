from __future__ import annotations

from pydantic import BaseModel


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
