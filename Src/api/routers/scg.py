from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_scg
from Src.api.schemas.scg import RPVResponse, SCGPeriodo, SalvarManualRequest
from Src.Services.servicos_scg import ServicosSCG

router = APIRouter(prefix="/scg", tags=["SCG"])


@router.get("/periodos")
def listar_periodos(servico: ServicosSCG = Depends(get_servicos_scg)) -> list:
    return servico.obter_periodos()


@router.get("", response_model=SCGPeriodo)
def buscar_periodo(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> SCGPeriodo:
    """`periodo` via query string — path param quebraria com a barra do
    formato mês/ano (ex: 'Jan/2026'), igual ao caso resolvido em SR."""
    dados = servico.buscar_dados_periodo(periodo)
    if not dados:
        raise HTTPException(status_code=404, detail=f"Período '{periodo}' não encontrado")
    return SCGPeriodo(periodo=periodo, **dados)


@router.post("/calcular", response_model=SCGPeriodo)
def calcular(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> SCGPeriodo:
    dados = servico.calcular_scg_oficial(periodo)
    dados.setdefault("periodo", periodo)
    return SCGPeriodo(**dados)


@router.post("/manual", response_model=RPVResponse)
def salvar_manual(
    payload: SalvarManualRequest,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> RPVResponse:
    rpv = servico.salvar_valores_manuais(
        payload.periodo, payload.cgr, payload.cgf, payload.ret, payload.rp
    )
    return RPVResponse(rpv=rpv)


@router.delete("", status_code=204)
def apagar_periodo(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> None:
    servico.apagar_periodo(periodo)


# TODO(spec §4.6/§8): modo Trimestral (tabela mensal CGR/CGF/RPV/RET/RP/SCG)
# e /scg/trimestre-ativo (compartilha tabela `config` com /pmpv/trimestre-ativo,
# depende do mesmo trabalho de extração pendente no PMPVRepository).
