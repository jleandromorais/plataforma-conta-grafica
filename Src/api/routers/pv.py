from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from Src.api.deps import get_servicos_pv
from Src.api.schemas.pv import (
    PVCriarPeriodoRequest,
    PVHistoricoTrimestre,
    PVResultado,
    PVSalvarRequest,
    PVSalvarResponse,
    PVTrimestreResultado,
    PVTrimestreSalvarRequest,
    PVTrimestreSalvarResponse,
    ProvaRealPV,
)
from Src.Services.tarifa.servicos_pv import ServicosPV

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
        raise HTTPException(status_code=404, detail=f"Ainda não há PV salvo para {periodo}. Salve o PV deste trimestre na tela PV.")
    return PVResultado(**dados)


@router.post("/salvar", response_model=PVSalvarResponse)
def salvar(
    payload: PVSalvarRequest,
    servico: ServicosPV = Depends(get_servicos_pv),
) -> PVSalvarResponse:
    pv = servico.salvar_valores(payload.periodo, payload.pmpv, payload.pr)
    return PVSalvarResponse(pv=pv)


# ── Trimestral (tela do site) ─────────────────────────────────────────────────
# Os endpoints mensais acima continuam: o desktop (tela_pv.py) usa o mesmo serviço.

@router.get("/historico", response_model=list[PVHistoricoTrimestre])
def historico(servico: ServicosPV = Depends(get_servicos_pv)) -> list[PVHistoricoTrimestre]:
    """PVs gravados por trimestre fiscal, do mais recente ao mais antigo."""
    return [PVHistoricoTrimestre(**h) for h in servico.historico_trimestres()]


@router.get("/prova-real", response_model=ProvaRealPV)
def prova_real(
    trimestre: str,
    ano: int = Query(ge=2000, le=2098),
    servico: ServicosPV = Depends(get_servicos_pv),
) -> ProvaRealPV:
    """A conta do PV gravado do trimestre (PMPV + PR) e se ainda bate com os módulos. Não grava nada."""
    return ProvaRealPV(**servico.prova_real_trimestre(trimestre, ano))


@router.get("/trimestre", response_model=PVTrimestreResultado)
def buscar_trimestre(
    trimestre: str,
    ano: int = Query(ge=2000, le=2098),
    servico: ServicosPV = Depends(get_servicos_pv),
) -> PVTrimestreResultado:
    """PV do trimestre fiscal: PMPV + PR do mesmo trimestre (ex.: trimestre="Fev - Abr", ano=2026)."""
    return PVTrimestreResultado(**servico.buscar_trimestre(trimestre, ano))


@router.post("/trimestre/salvar", response_model=PVTrimestreSalvarResponse)
def salvar_trimestre(
    payload: PVTrimestreSalvarRequest,
    servico: ServicosPV = Depends(get_servicos_pv),
) -> PVTrimestreSalvarResponse:
    return PVTrimestreSalvarResponse(**servico.salvar_trimestre(payload.trimestre, payload.ano, payload.pmpv, payload.pr))
