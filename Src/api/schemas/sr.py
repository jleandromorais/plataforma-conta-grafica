from __future__ import annotations

from pydantic import BaseModel


class SRSessao(BaseModel):
    id: int
    nome: str
    data_criacao: str | None = None
    vp: float
    vf: float


class SRVpVfResponse(BaseModel):
    vp: float
    vf: float


class SRCalcularRequest(BaseModel):
    vp: float
    vf: float
    pr: float


class SRCalcularResponse(BaseModel):
    sr: float


# ── SR trimestral (VP/VF/PR/SELIC/SR-anterior por mês) ──────────────────────

class SRTrimestreCarregarRequest(BaseModel):
    sessao_id: int
    labels_meses: list[str]  # ex: ["Jan/2026", "Fev/2026", "Mar/2026"]


class SRTrimestreLinhaCarregada(BaseModel):
    mes: str
    vp: float
    vf: float
    pr: float


class SRTrimestreLinhaEntrada(BaseModel):
    mes: str
    vp: float
    vf: float
    pr: float
    selic_mensal: float = 0.0
    sr_anterior: float = 0.0


class SRTrimestreLinhaCalculada(SRTrimestreLinhaEntrada):
    diferenca: float
    sr_parcela: float
    sr_selic: float
    total: float


class SRTrimestreCalcularRequest(BaseModel):
    linhas: list[SRTrimestreLinhaEntrada]


class SRTrimestreCalcularResponse(BaseModel):
    linhas: list[SRTrimestreLinhaCalculada]
    total: float


class SRTrimestreSalvarRequest(BaseModel):
    labels_meses: list[str]
    periodo_referencia: str
    linhas: list[SRTrimestreLinhaCalculada]


class SRTrimestreSalvarResponse(BaseModel):
    total: float
