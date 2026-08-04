from __future__ import annotations

from pydantic import BaseModel


class KpiMensal(BaseModel):
    periodo: str
    cgr: float
    ret: float
    cgf: float
    rp: float
    rpv: float
    scg: float
    variacao_scg_pct: float | None = None


class SeriePonto(BaseModel):
    periodo: str
    valor: float


class DashboardResponse(BaseModel):
    ano_filtro: str | None = None
    ultimo_mes: KpiMensal | None = None
    historico: list[KpiMensal]
    serie_pmpv: list[SeriePonto]
    serie_scg: list[SeriePonto]
