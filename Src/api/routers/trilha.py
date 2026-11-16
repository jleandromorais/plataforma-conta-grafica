"""Trilha de alterações dos valores gravados (SCG, SR, PR, PV e PMPV)."""
from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends, Query

from Src.api.schemas.trilha import TrilhaLinha
from Src.Services.apuracao.servicos_trilha import LIMITE_PADRAO, ServicosTrilha

router = APIRouter(prefix="/trilha", tags=["TRILHA"])


def get_servicos_trilha() -> Iterator[ServicosTrilha]:
    servico = ServicosTrilha()
    try:
        yield servico
    finally:
        servico.fechar()


@router.get("", response_model=list[TrilhaLinha])
def listar(
    periodo: str | None = None,
    tabela: str | None = None,
    limite: int = Query(LIMITE_PADRAO, ge=1, le=1000),
    servico: ServicosTrilha = Depends(get_servicos_trilha),
) -> list[TrilhaLinha]:
    """O que mudou nos valores gravados, da alteração mais recente para a mais antiga. Só lê.

    Filtros opcionais: `periodo` (Jul/2026 ou Fev - Abr/2026) e `tabela` (consolidacao, sr_resultados,
    pr_resultados, pv_resultados, pmpv_mensal). Não identifica quem alterou."""
    return [TrilhaLinha(**l) for l in servico.listar(periodo, tabela, limite)]
