"""Cascata SR → PR → PV: prévia, pendências e aprovação (ver Src/Services/tarifa/servicos_cascata.py)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from Src.api.deps import get_servicos_cascata
from Src.api.schemas.cascata import APartirDe, Cascata, CascataAplicarRequest
from Src.Services.tarifa.servicos_cascata import ServicosCascata

router = APIRouter(prefix="/cascata", tags=["CASCATA"])


@router.get("/previa", response_model=Cascata)
def previa(
    periodos: list[str] = Query(..., description="Meses que mudaram, ex.: periodos=Jul/2026&periodos=Ago/2026"),
    a_partir_de: APartirDe = "sr",
    servico: ServicosCascata = Depends(get_servicos_cascata),
) -> Cascata:
    """Mostra, por trimestre, o SR, o PR e o PV de hoje ao lado dos novos. NÃO grava nada."""
    return Cascata(**servico.previa(periodos, a_partir_de))


@router.get("/pendente", response_model=Cascata)
def pendente(servico: ServicosCascata = Depends(get_servicos_cascata)) -> Cascata:
    """Só os trimestres recentes cujo SR, PR ou PV está desatualizado (aviso geral). NÃO grava nada."""
    return Cascata(**servico.pendente())


@router.post("/aplicar", response_model=Cascata)
def aplicar(
    payload: CascataAplicarRequest,
    servico: ServicosCascata = Depends(get_servicos_cascata),
) -> Cascata:
    """Depois da aprovação: o servidor recalcula tudo e grava SR → PR → PV. Os números da tela não
    entram. Com qualquer pendência responde 422 e nada é gravado."""
    return Cascata(**servico.aplicar(payload.periodos, payload.a_partir_de))
