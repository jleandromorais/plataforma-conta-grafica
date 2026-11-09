from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from Src.api.schemas.pr import PRAutomatico
from Src.common.precisao import arredondar_tarifa


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
    sessao_id: int = 0  # não usado: o VP vem do PMPV que cobre cada mês
    labels_meses: list[str]  # ex: ["Jan/2026", "Fev/2026", "Mar/2026"]


class SRTrimestreLinhaCarregada(BaseModel):
    mes: str
    vp: float
    vf: float
    pr: float
    pr_origem: Literal["salvo", "estimado", "ausente"] = "salvo"

    _pr_4_casas = field_validator("pr")(lambda v: arredondar_tarifa(v))


class SRTrimestreLinhaEntrada(BaseModel):
    mes: str
    vp: float
    vf: float
    pr: float  # usado com 4 casas, como no desktop (campo PR da tela)

    _pr_4_casas = field_validator("pr")(lambda v: arredondar_tarifa(v))
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
    pr_automatico: PRAutomatico | None = None  # PR e PV do trimestre, regravados junto


class SRPropostaRequest(BaseModel):
    labels_meses: list[str] = Field(min_length=3, max_length=3)  # os 3 meses do trimestre civil


class SRPropostaGravado(BaseModel):
    vp: float
    vf: float
    pr: float
    selic_mensal: float
    sr_selic: float
    sr_anterior: float


class SRPropostaAlerta(BaseModel):
    codigo: str
    mensagem: str


class SRPropostaLinha(BaseModel):
    mes: str
    vp: float
    vf: float
    pr: float
    pr_origem: Literal["salvo", "estimado", "ausente"]
    pr_chave: str
    selic_mensal: float
    sr_anterior: float
    diferenca: float
    sr_parcela: float
    sr_selic: float
    total: float
    gravado: SRPropostaGravado | None = None
    alertas: list[SRPropostaAlerta] = []


class SRPropostaSelic(BaseModel):
    disponivel: bool
    fecha_em: str
    fonte: str
    mensagem: str


class SRPropostaResponse(BaseModel):
    labels_meses: list[str]
    linhas: list[SRPropostaLinha]
    total: float
    total_gravado: float | None = None
    diferenca_total: float | None = None
    selic: SRPropostaSelic
    bloqueios: list[str] = []
    pode_gravar: bool


class SRSelicResponse(BaseModel):
    disponivel: bool  # False: o trimestre ainda não fechou (ver fecha_em)
    valores: dict[str, float]  # {"Jan/2026": 3.411174, ...} — % acumulada até o fim do trimestre
    fecha_em: str  # último dia do trimestre, aaaa-mm-dd
    fonte: str
