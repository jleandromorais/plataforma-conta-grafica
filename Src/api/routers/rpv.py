from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_rpv
from Src.api.schemas.rpv import RPVResultado, RPVSalvarRequest, RPVSalvarResponse
from Src.Services.servicos_rpv import ServicosRPV

router = APIRouter(prefix="/rpv", tags=["RPV"])


@router.get("/periodos")
def listar_periodos(servico: ServicosRPV = Depends(get_servicos_rpv)) -> list:
    return servico.obter_periodos()


@router.get("", response_model=RPVResultado)
def buscar_periodo(
    periodo: str,
    servico: ServicosRPV = Depends(get_servicos_rpv),
) -> RPVResultado:
    """`periodo` via query string — path param quebraria com a barra do
    formato mês/ano (ex: 'Jan/2026'), igual ao caso resolvido em SR."""
    dados = servico.buscar_dados_periodo(periodo)
    if not dados:
        raise HTTPException(status_code=404, detail=f"Período '{periodo}' não encontrado")
    return RPVResultado(**dados)


@router.post("/salvar", response_model=RPVSalvarResponse)
def salvar(
    payload: RPVSalvarRequest,
    servico: ServicosRPV = Depends(get_servicos_rpv),
) -> RPVSalvarResponse:
    rpv = servico.salvar_valores(payload.periodo, payload.cgr, payload.cgf)
    return RPVSalvarResponse(rpv=rpv)
