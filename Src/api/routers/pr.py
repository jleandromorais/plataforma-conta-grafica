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
from Src.Services.tarifa.servicos_pr import ServicosPR
from Src.Services.tarifa.servicos_pr_automatico import atualizar_pv_do_pr

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
        raise HTTPException(status_code=404, detail=f"Ainda não há PR salvo para {periodo}. Calcule e salve o PR deste trimestre na tela PR.")
    return PRResultado(periodo=periodo, **dados)


@router.post("/apurar")
def apurar(
    payload: PRTrimestralRequest,
    servico: ServicosPR = Depends(get_servicos_pr),
) -> dict:
    """PR da Nota Técnica para os 3 meses do PR em `periodos` (ex.: Mai–Jul/2026):
    SCG e SR com SELIC do trimestre civil apurado (Jan–Mar/2026) ÷ VP."""
    return servico.apurar_trimestre(payload.periodos)


@router.post("/salvar", response_model=PRSalvarResponse)
def salvar(
    payload: PRSalvarRequest,
    servico: ServicosPR = Depends(get_servicos_pr),
) -> PRSalvarResponse:
    """Grava o PR do trimestre da tarifa `periodo` ("Fev - Abr/2026"). O servidor refaz a apuração
    (SCG com SELIC + SR do trimestre civil ÷ VP) e grava o valor DELE: scg/sr/vp do pedido são
    ignorados. Faltou SR, SCG, VP ou PMPV → 422 com as pendências, e nada é gravado."""
    pr = servico.salvar_apurado(payload.periodo)
    # PV do mesmo trimestre refeito com o PR recém-salvo (None se a chave não é de trimestre).
    return PRSalvarResponse(pr=pr, pv_automatico=atualizar_pv_do_pr(payload.periodo))
