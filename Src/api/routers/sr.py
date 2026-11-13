from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from Src.api.deps import get_servicos_sr, get_sr_use_cases
from Src.api.schemas.sr import (
    SRCalcularRequest,
    SRCalcularResponse,
    SRHistoricoTrimestre,
    SRProvaReal,
    SRPropostaRequest,
    SRPropostaResponse,
    SRSelicResponse,
    SRSessao,
    SRTrimestreCalcularRequest,
    SRTrimestreCalcularResponse,
    SRTrimestreCarregarRequest,
    SRTrimestreLinhaCarregada,
    SRTrimestreSalvarRequest,
    SRTrimestreSalvarResponse,
    SRVpVfResponse,
)
from Src.application.use_cases.sr_use_cases import SRUseCases
from Src.Services.tarifa import servicos_pr_automatico, servicos_selic
from Src.Services.apuracao.servicos_sr import ServicosSR

router = APIRouter(prefix="/sr", tags=["SR"])


@router.get("/sessoes", response_model=list[SRSessao])
def listar_sessoes(servico: ServicosSR = Depends(get_servicos_sr)) -> list[SRSessao]:
    return [SRSessao(**s) for s in servico.listar_sessoes()]


@router.get("/sessoes/{sessao_id}/vp-vf", response_model=SRVpVfResponse)
def buscar_vp_vf(
    sessao_id: int,
    servico: ServicosSR = Depends(get_servicos_sr),
) -> SRVpVfResponse:
    dados = servico.buscar_vp_vf(sessao_id)
    if not dados:
        raise HTTPException(status_code=404, detail=f"A sessão de PMPV nº {sessao_id} não existe mais. Recarregue a lista de sessões e escolha outra.")
    return SRVpVfResponse(**dados)


@router.post("/calcular", response_model=SRCalcularResponse)
def calcular(payload: SRCalcularRequest) -> SRCalcularResponse:
    sr = ServicosSR.calcular_sr(payload.vp, payload.vf, payload.pr)
    return SRCalcularResponse(sr=sr)


# ── SR trimestral (VP/VF/PR/SELIC/SR-anterior por mês) ──────────────────────
# Ver Front_end/SPEC_SR.md — é o cálculo real de SR; não confundir com o
# breakdown por CGR/CGF/RPV que o front mockado usava antes desta task.


@router.post("/trimestre/carregar", response_model=list[SRTrimestreLinhaCarregada])
def carregar_trimestre(
    payload: SRTrimestreCarregarRequest,
    uc: SRUseCases = Depends(get_sr_use_cases),
) -> list[SRTrimestreLinhaCarregada]:
    linhas = uc.carregar_vp_vf_pr(payload.sessao_id, payload.labels_meses)
    return [SRTrimestreLinhaCarregada(**l) for l in linhas]


@router.post("/trimestre/proposta", response_model=SRPropostaResponse)
def propor_trimestre(
    payload: SRPropostaRequest,
    uc: SRUseCases = Depends(get_sr_use_cases),
) -> SRPropostaResponse:
    """Calcula o SR do trimestre sozinho (VP, VF, PR, SELIC) e compara com o gravado.
    NÃO grava nada: quem grava é o /trimestre/salvar, depois que o analista confirma."""
    resultado = uc.propor_trimestre(payload.labels_meses, buscar=servicos_selic.buscar_bcb)
    return SRPropostaResponse(**resultado)


@router.post("/trimestre/calcular",response_model=SRTrimestreCalcularResponse)
def calcular_trimestre(payload: SRTrimestreCalcularRequest) -> SRTrimestreCalcularResponse:
    resultado = SRUseCases.calcular_trimestre([l.model_dump() for l in payload.linhas])
    return SRTrimestreCalcularResponse(**resultado)


@router.post("/trimestre/salvar", response_model=SRTrimestreSalvarResponse)
def salvar_trimestre(
    payload: SRTrimestreSalvarRequest,
    uc: SRUseCases = Depends(get_sr_use_cases),
) -> SRTrimestreSalvarResponse:
    """Grava o SR do trimestre civil. O servidor recalcula cada mês a partir de VP, VF, PR, SELIC
    e SR anterior e grava a conta DELE. PR ou VP zerado, ou SELIC 0% → 422, e nada é gravado."""
    total = uc.salvar_trimestre_conferido(
        payload.labels_meses,
        payload.periodo_referencia,
        [l.model_dump() for l in payload.linhas],
    )
    # O PR (e o PV) do trimestre usa este SR: regrava junto.
    pr = servicos_pr_automatico.atualizar_sem_falhar(payload.labels_meses[0]) if payload.labels_meses else None
    return SRTrimestreSalvarResponse(total=total, pr_automatico=pr)


@router.get("/selic", response_model=SRSelicResponse)
def selic(meses: list[str] = Query(..., description="Os 3 meses do trimestre civil, ex.: Jan/2026")) -> SRSelicResponse:
    """SELIC acumulada de cada mês até o fim do trimestre, calculada com os dados do Banco Central."""
    try:
        return SRSelicResponse(**servicos_selic.selic_do_trimestre(meses, buscar=servicos_selic.buscar_bcb))
    except servicos_selic.SelicIndisponivel as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/historico", response_model=list[SRHistoricoTrimestre])
def historico(uc: SRUseCases = Depends(get_sr_use_cases)) -> list[SRHistoricoTrimestre]:
    """Trimestres de SR gravados, do mais recente ao mais antigo."""
    return [SRHistoricoTrimestre(**h) for h in uc.historico_trimestres()]


@router.get("/prova-real", response_model=SRProvaReal)
def prova_real(trimestre: str, uc: SRUseCases = Depends(get_sr_use_cases)) -> SRProvaReal:
    """Refaz a conta do SR gravado do trimestre (ex.: Jan/2026_Mar/2026) e mostra o que VP, VF,
    PR e SELIC dizem hoje. NÃO grava nada."""
    return SRProvaReal(**uc.prova_real(trimestre, buscar=servicos_selic.buscar_bcb))


@router.get("/trimestre", response_model=list[dict])
def buscar_trimestre(
    label: str,
    uc: SRUseCases = Depends(get_sr_use_cases),
) -> list[dict]:
    """`label` é o trimestre_label completo (ex: 'Jan/2026_Mar/2026'), passado
    como query string — path param quebraria com as barras do formato mês/ano."""
    linhas = uc.repo.buscar_sr_trimestre(label)
    if not linhas:
        raise HTTPException(status_code=404, detail=f"Ainda não há SR salvo para {label.replace('_', ' a ')}. Salve o SR deste trimestre na tela SR.")
    return linhas
