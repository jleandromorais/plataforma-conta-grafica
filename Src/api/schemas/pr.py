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


class PRAutomatico(BaseModel):
    """PR e PV regravados ao salvar o SCG ou o SR (servicos_pr_automatico)."""
    meses_pr: list[str]
    atualizado: bool              # False = nada gravado; ver `pendencias`
    pr_antes: float | None
    pr: float | None
    pv_antes: float | None
    pv: float | None
    pendencias: list[str]
