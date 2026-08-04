from __future__ import annotations

from pydantic import BaseModel


class PRResultado(BaseModel):
    periodo: str | None = None
    scg: float
    sr: float
    vp: float
    pr: float


class PRTrimestralRequest(BaseModel):
    periodos: list[str]


class PRSalvarRequest(BaseModel):
    periodo: str
    scg: float
    sr: float
    vp: float


class PRSalvarResponse(BaseModel):
    pr: float


class PRSrAnterior(BaseModel):
    periodo: str
    sr: float
