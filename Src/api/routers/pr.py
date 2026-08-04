from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_pr
from Src.api.schemas.pr import (
    PRResultado,
    PRSalvarRequest,
    PRSalvarResponse,
    PRSrAnterior,
    PRTrimestralRequest,
)
from Src.Services.servicos_pr import ServicosPR

router = APIRouter(prefix="/pr", tags=["PR"])


@router.get("/periodos")
def listar_periodos(servico: ServicosPR = Depends(get_servicos_pr)) -> list[str]:
    return servico.obter_todos_periodos()


@router.get("/sr-anteriores", response_model=list[PRSrAnterior])
def listar_sr_anteriores(servico: ServicosPR = Depends(get_servicos_pr)) -> list[PRSrAnterior]:
    """Expõe PRRepository.listar_sr() — usado para popular os campos de SR
    anterior ao carregar um trimestre (ver Front_end/SPEC_PR.md §4-§5).
    Declarado antes de /{periodo} para não colidir com o path param."""
    linhas = servico._repo.listar_sr()
    return [PRSrAnterior(periodo=r.get("periodo", ""), sr=float(r.get("sr") or 0)) for r in linhas]


@router.get("", response_model=PRResultado)
def buscar_periodo(
    periodo: str,
    servico: ServicosPR = Depends(get_servicos_pr),
) -> PRResultado:
    """`periodo` via query string — path param quebraria com a barra do
    formato mês/ano (ex: 'Jan/2026'), igual ao caso resolvido em SR."""
    dados = servico.buscar_dados_periodo(periodo)
    if not dados:
        raise HTTPException(status_code=404, detail=f"Período '{periodo}' não encontrado")
    return PRResultado(periodo=periodo, **dados)


@router.post("/trimestral")
def buscar_trimestral(
    payload: PRTrimestralRequest,
    servico: ServicosPR = Depends(get_servicos_pr),
) -> dict:
    return servico.buscar_dados_trimestral(payload.periodos)


@router.post("/salvar", response_model=PRSalvarResponse)
def salvar(
    payload: PRSalvarRequest,
    servico: ServicosPR = Depends(get_servicos_pr),
) -> PRSalvarResponse:
    pr = servico.salvar_valores(payload.periodo, payload.scg, payload.sr, payload.vp)
    return PRSalvarResponse(pr=pr)
