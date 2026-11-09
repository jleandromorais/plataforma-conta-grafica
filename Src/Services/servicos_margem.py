"""Margem regulatória e Tarifa Média (Quadro 9 da Nota Técnica).

A margem regulatória é definida pelo regulador, uma vez por ano (R$/m³): não dá para calculá-la
a partir dos dados do sistema. O sistema conhece a de alguns anos (`MARGEM_PADRAO_POR_ANO`);
para os demais o analista informa o valor, que fica salvo no banco (tabela `config`). O valor
que o analista salvou vale mais que o padrão.

Tarifa Média = PV + Margem Regulatória, com PV = PMPV + PR.
"""
from __future__ import annotations

from Src.Database.database import DatabasePMPV

# Margem regulatória conhecida por ano (R$/m³).
MARGEM_PADRAO_POR_ANO: dict[int, float] = {2026: 0.5410}


def _chave(ano: int) -> str:
    return f"margem_regulatoria:{ano}"


def _validar_ano(ano: int) -> int:
    if not isinstance(ano, int) or not 2000 <= ano <= 2100:
        raise ValueError("O ano da margem regulatória precisa estar entre 2000 e 2100.")
    return ano


def buscar_margem(ano: int) -> dict:
    """Margem do ano e de onde ela vem: "salva" (o analista informou), "padrao" (o sistema conhece)
    ou "ausente" (ninguém informou ainda: o analista precisa digitar)."""
    _validar_ano(ano)
    with DatabasePMPV() as db:
        salva = db.buscar_config_numero(_chave(ano))
    if salva is not None:
        return {"ano": ano, "margem": salva, "origem": "salva"}
    if ano in MARGEM_PADRAO_POR_ANO:
        return {"ano": ano, "margem": MARGEM_PADRAO_POR_ANO[ano], "origem": "padrao"}
    return {"ano": ano, "margem": None, "origem": "ausente"}


def salvar_margem(ano: int, margem: float) -> dict:
    _validar_ano(ano)
    if margem is None or margem < 0:
        raise ValueError("A margem regulatória precisa ser um valor igual ou maior que zero (R$/m³).")
    with DatabasePMPV() as db:
        db.salvar_config_numero(_chave(ano), float(margem))
    return buscar_margem(ano)


def tarifa_media(pv: float, margem: float | None) -> float | None:
    """Tarifa Média = PV + Margem Regulatória. Sem margem, não há tarifa média."""
    return None if margem is None else float(pv) + float(margem)
