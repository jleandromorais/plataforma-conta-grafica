from __future__ import annotations

from pydantic import BaseModel

from Src.api.schemas.pv import PVAutomatico


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
    pv_automatico: PVAutomatico | None = None  # PV do mesmo trimestre, regravado junto


class PRSrAnterior(BaseModel):
    periodo: str
    sr: float


class SRAutomatico(BaseModel):
    """SR do trimestre civil recalculado sozinho depois de salvar o SCG ou um módulo."""
    trimestre: str                # ex.: "Jul/2026_Set/2026"
    atualizado: bool              # False = nada gravado; ver `pendencias`
    sr_antes: float | None = None
    sr: float | None = None
    pendencias: list[str] = []


class PRAutomatico(BaseModel):
    """PR e PV regravados ao salvar o SCG ou o SR (servicos_pr_automatico)."""
    meses_pr: list[str]
    atualizado: bool              # False = nada gravado; ver `pendencias`
    pr_antes: float | None
    pr: float | None
    pv_antes: float | None
    pv: float | None
    pendencias: list[str]
    sr_automatico: SRAutomatico | None = None  # None = o SR não foi recalculado nesta chamada
