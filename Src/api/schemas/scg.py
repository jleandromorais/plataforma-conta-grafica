from __future__ import annotations

from pydantic import BaseModel


class SCGPeriodo(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    rpv: float
    ret: float
    rp: float
    scg: float


class SalvarManualRequest(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    ret: float
    rp: float


class RPVResponse(BaseModel):
    rpv: float


class SCGValores(BaseModel):
    cgr: float
    cgf: float
    rpv: float
    ret: float
    rp: float
    scg: float


class SCGComparacao(BaseModel):
    """Os dois lados que podem divergir num mês (ver ServicosSCG.buscar_dados_fontes)."""
    periodo: str
    modulos: SCGValores          # recalculado dos itens de Auditoria/Conciliação
    gravado: SCGValores | None   # consolidação (o que o Excel Final usa); None = período novo


class SCGHistoricoLinha(SCGValores):
    periodo: str
    diverge: bool  # módulos ≠ gravado em algum valor
