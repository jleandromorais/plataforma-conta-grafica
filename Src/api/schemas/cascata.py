"""Formato da cascata SR → PR → PV: a prévia (antes × novo) e o pedido de aprovação.

Nada aqui grava: a prévia só mostra o que mudaria. Quem grava é o POST /cascata/aplicar,
que recalcula tudo no servidor (os números da tela nunca são gravados).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# De onde a cascata parte: "sr" = recalcula SR, PR e PV; "pr" = só PR e PV (o SR acabou de ser salvo);
# "pv" = só o PV (o PMPV ou o PR acabou de ser salvo).
APartirDe = Literal["sr", "pr", "pv"]


class CascataTrimestre(BaseModel):
    """Um trimestre da cascata: SR (civil) → PR e PV (trimestre da tarifa)."""
    periodo: str                       # mês-guia deste trimestre: mande-o em /cascata/aplicar
    trimestre_sr: str | None = None    # "Jul/2026_Set/2026"; None quando a cascata não parte do SR
    sr_antes: float | None = None      # SR gravado hoje (None = nunca gravado)
    sr_novo: float | None = None       # SR recalculado (None = não calculado ou com pendência)
    meses_pr: list[str] = []           # os 3 meses do PR/PV deste trimestre
    chave_pr: str                      # "Nov - Jan/2027" (ano do último mês)
    pr_antes: float | None = None
    pr_novo: float | None = None
    chave_pv: str                      # "Nov - Jan/2026" (ano do 1º mês)
    pv_antes: float | None = None
    pv_novo: float | None = None
    desatualizado: bool = False        # algum valor novo difere do gravado (ou ainda não foi gravado)
    pendencias: list[str] = []         # o que falta; com pendência o /cascata/aplicar recusa (422)


class Cascata(BaseModel):
    """A prévia da cascata. Mande `periodos` e `a_partir_de` de volta em POST /cascata/aplicar."""
    periodos: list[str] = []
    a_partir_de: APartirDe = "sr"
    ate: APartirDe | None = None       # onde a aprovação para; None = vai até o PV (comportamento antigo)
    desatualizado: bool = False        # algum trimestre está desatualizado
    trimestres: list[CascataTrimestre] = []
    pendencias: list[str] = []         # todas as pendências dos trimestres, em uma lista


class CascataEsperado(BaseModel):
    """O que o analista viu na prévia de um trimestre (devolva `periodo`, `sr_novo`, `pr_novo`, `pv_novo`)."""
    periodo: str
    sr_novo: float | None = Field(default=None, allow_inf_nan=False)
    pr_novo: float | None = Field(default=None, allow_inf_nan=False)
    pv_novo: float | None = Field(default=None, allow_inf_nan=False)


class CascataAplicarRequest(BaseModel):
    periodos: list[str] = Field(min_length=1)
    a_partir_de: APartirDe = "sr"
    # Etapa final da aprovação: "sr" grava só o SR; "pr" até o PR; "pv" até o PV. Sem ele, vai até o PV.
    ate: APartirDe | None = None
    # Trava 409: os valores que o analista viu. Se o cálculo de agora difere, nada é gravado.
    esperado: list[CascataEsperado] | None = None
