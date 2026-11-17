"""Situação do ciclo: o roteiro de 5 passos de um trimestre (ver Src/Services/tarifa/servicos_ciclo.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from Src.api.deps import get_servicos_ciclo
from Src.api.schemas.ciclo import CicloSituacao
from Src.Services.tarifa.servicos_ciclo import ServicosCiclo

router = APIRouter(prefix="/ciclo", tags=["CICLO"])


@router.get("/situacao", response_model=CicloSituacao)
def situacao(
    trimestre: str = Query(..., description="Trimestre civil: Jul/2026_Set/2026, ou um mês dele (Ago/2026)"),
    servico: ServicosCiclo = Depends(get_servicos_ciclo),
) -> CicloSituacao:
    """Estado de cada um dos 5 passos do trimestre, com o motivo e a rota do link; se a SELIC já fechou
    (e quando libera) e se o PMPV do trimestre novo existe. NÃO grava nada (consulta o Banco Central)."""
    return CicloSituacao(**servico.situacao(trimestre))
