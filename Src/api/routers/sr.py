from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_sr, get_sr_use_cases
from Src.api.schemas.sr import (
    SRCalcularRequest,
    SRCalcularResponse,
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
from Src.Services.servicos_sr import ServicosSR

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
        raise HTTPException(status_code=404, detail=f"Sessão '{sessao_id}' não encontrada")
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


@router.post("/trimestre/calcular", response_model=SRTrimestreCalcularResponse)
def calcular_trimestre(payload: SRTrimestreCalcularRequest) -> SRTrimestreCalcularResponse:
    resultado = SRUseCases.calcular_trimestre([l.model_dump() for l in payload.linhas])
    return SRTrimestreCalcularResponse(**resultado)


@router.post("/trimestre/salvar", response_model=SRTrimestreSalvarResponse)
def salvar_trimestre(
    payload: SRTrimestreSalvarRequest,
    uc: SRUseCases = Depends(get_sr_use_cases),
) -> SRTrimestreSalvarResponse:
    total = uc.salvar_trimestre(
        payload.labels_meses,
        payload.periodo_referencia,
        [l.model_dump() for l in payload.linhas],
    )
    return SRTrimestreSalvarResponse(total=total)


@router.get("/trimestre", response_model=list[dict])
def buscar_trimestre(
    label: str,
    uc: SRUseCases = Depends(get_sr_use_cases),
) -> list[dict]:
    """`label` é o trimestre_label completo (ex: 'Jan/2026_Mar/2026'), passado
    como query string — path param quebraria com as barras do formato mês/ano."""
    linhas = uc.repo.buscar_sr_trimestre(label)
    if not linhas:
        raise HTTPException(status_code=404, detail=f"Trimestre '{label}' não encontrado")
    return linhas
