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
    completo: bool = True               # tem CGR e CGF
    pendencias: list[str] = []          # o que falta lançar no mês


class SeriePonto(BaseModel):
    periodo: str
    valor: float


class DashboardResponse(BaseModel):
    ano_filtro: str | None = None
    ultimo_mes: KpiMensal | None = None
    historico: list[KpiMensal]
    serie_pmpv: list[SeriePonto]
    serie_scg: list[SeriePonto]


class EmpresaCGR(BaseModel):
    empresa: str
    notas: int
    nfe: int
    cte: int
    valor_total: float
    icms: float
    pis_cofins: float
    cgr_liquido: float


class EmpresasDoMes(BaseModel):
    periodo: str                        # "Set/2026"
    empresas: list[EmpresaCGR]          # do maior CGR líquido para o menor


class DashboardEmpresas(BaseModel):
    ano_filtro: str | None = None
    empresas: list[EmpresaCGR]          # do maior CGR líquido para o menor
    total_cgr_liquido: float
    meses: list[EmpresasDoMes] = []     # as mesmas contas mês a mês, em ordem cronológica


class RetMes(BaseModel):
    periodo: str
    total: float
    por_tipo: dict[str, float]


class DashboardRet(BaseModel):
    ano_filtro: str | None = None
    tipos: list[str]                    # até 3 maiores + "Outros", na ordem de cores
    meses: list[RetMes]
    total: float


class VolumeMes(BaseModel):
    periodo: str
    volume_faturado: float
    volume_devolucoes: float
    volume_canceladas: float
    volume_consumo_proprio: float
    volume_final: float


class DashboardVolumes(BaseModel):
    ano_filtro: str | None = None
    meses: list[VolumeMes]
    totais: VolumeMes                   # soma do período filtrado
