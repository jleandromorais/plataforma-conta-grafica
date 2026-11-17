from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_pr
from Src.api.perfis import anotar_motivo
from Src.api.schemas.periodos import LimpezaPeriodoResponse
from Src.api.schemas.pr import (
    PRResultado,
    PRSalvarRequest,
    PRSalvarResponse,
    PRSrAnterior,
    PRTrimestralRequest,
)
from Src.Services.tarifa.servicos_pr import ServicosPR
from Src.Services.tarifa import servicos_cascata
from Src.Services.tarifa.servicos_pr import meses_da_chave_pr

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
    # O PR acabou de ser gravado; o PV do mesmo trimestre NÃO é regravado: a prévia vai em `cascata`.
    cascata = servicos_cascata.previa_sem_falhar(meses_da_chave_pr(payload.periodo), a_partir_de="pv")
    legado = servicos_cascata.pv_automatico_legado(cascata)
    return PRSalvarResponse(pr=pr, pv_automatico=legado[0] if legado else None, cascata=cascata)


@router.delete("", response_model=LimpezaPeriodoResponse)
def apagar(
    periodo: str,
    aplicar: bool = False,
    motivo: str | None = None,
    servico: ServicosPR = Depends(get_servicos_pr),
) -> LimpezaPeriodoResponse:
    """Apaga o PR salvo de um trimestre da tarifa (ex.: ?periodo=Fev - Abr/2026), para refazê-lo.

    Por padrão é só SIMULAÇÃO (aplicar=false): diz o que seria apagado e NÃO apaga nada.
    Só apaga com ?aplicar=true. O PV do trimestre não é tocado."""
    anotar_motivo(motivo)
    try:
        return LimpezaPeriodoResponse(**servico.apagar_pr(periodo, aplicar=aplicar))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
