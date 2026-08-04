from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_pv
from Src.api.schemas.pv import (
    PVCriarPeriodoRequest,
    PVResultado,
    PVSalvarRequest,
    PVSalvarResponse,
)
from Src.Services.servicos_pv import ServicosPV

router = APIRouter(prefix="/pv", tags=["PV"])


@router.get("/periodos")
def listar_periodos(servico: ServicosPV = Depends(get_servicos_pv)) -> list[dict]:
    return servico.obter_periodos()


@router.post("/periodos", status_code=201)
def criar_periodo(
    payload: PVCriarPeriodoRequest,
    servico: ServicosPV = Depends(get_servicos_pv),
) -> dict:
    servico.criar_periodo(payload.nome)
    return {"nome": payload.nome.strip()}


@router.get("", response_model=PVResultado)
def buscar_periodo(
    periodo: str,
    servico: ServicosPV = Depends(get_servicos_pv),
) -> PVResultado:
    """`periodo` via query string — path param quebraria com a barra do
    formato mês/ano (ex: 'Jan/2026'), igual ao caso resolvido em SR."""
    dados = servico.buscar_dados_periodo(periodo)
    if not dados:
        raise HTTPException(status_code=404, detail=f"Período '{periodo}' não encontrado")
    return PVResultado(**dados)


@router.post("/salvar", response_model=PVSalvarResponse)
def salvar(
    payload: PVSalvarRequest,
    servico: ServicosPV = Depends(get_servicos_pv),
) -> PVSalvarResponse:
    pv = servico.salvar_valores(payload.periodo, payload.pmpv, payload.pr)
    return PVSalvarResponse(pv=pv)
