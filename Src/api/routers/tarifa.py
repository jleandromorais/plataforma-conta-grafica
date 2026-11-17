"""Tarifa média do trimestre do ciclo (ver Src/Services/tarifa/servicos_tarifa_media.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from Src.api.deps import get_servicos_pv
from Src.api.schemas.tarifa import TarifaMediaResposta
from Src.Services.tarifa.servicos_pv import ServicosPV
from Src.Services.tarifa.servicos_tarifa_media import tarifa_media_do_trimestre

router = APIRouter(prefix="/tarifa", tags=["TARIFA"])


@router.get("/media", response_model=TarifaMediaResposta)
def media(
    trimestre: str = Query(..., description="Trimestre do ciclo: Nov/2025_Jan/2026, ou um mês dele (Dez/2025)"),
    servico_pv: ServicosPV = Depends(get_servicos_pv),
) -> TarifaMediaResposta:
    """Tarifa média (PV gravado + MB) do trimestre. Se o trimestre cruza o ano, devolve uma tarifa para a MB
    de cada ano e não escolhe qual vale. Faltando PV ou MB, a tarifa vem null com o motivo. NÃO grava nada."""
    return TarifaMediaResposta(**tarifa_media_do_trimestre(trimestre, servico_pv))
