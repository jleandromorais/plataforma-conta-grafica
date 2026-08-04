from __future__ import annotations

from fastapi import APIRouter, Depends

from Src.api.deps import get_pmpv_use_cases
from Src.api.schemas.pmpv import (
    CalcularPMPVRequest,
    PMPVMensalRequest,
    PMPVMensalResponse,
    SalvarPMPVRequest,
    SalvarPMPVResponse,
)
from Src.application.use_cases.pmpv_use_cases import PMPVUseCases

router = APIRouter(prefix="/pmpv", tags=["PMPV"])


@router.post("/calcular")
def calcular(payload: CalcularPMPVRequest) -> dict:
    return PMPVUseCases.calcular_resultados(
        dados_extraidos=payload.dados_extraidos,
        valor_cg=payload.valor_cg,
        dias_config=payload.dias_config,
        lista_meses=payload.lista_meses,
        idx_start=payload.idx_start,
    )


@router.post("/salvar", response_model=SalvarPMPVResponse)
def salvar(
    payload: SalvarPMPVRequest,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> SalvarPMPVResponse:
    sessao_id = uc.salvar_sessao_completa(
        nome=payload.nome,
        dados_por_mes=payload.dados_por_mes,
        resultado=payload.resultado,
    )
    return SalvarPMPVResponse(sessao_id=sessao_id)


@router.get("/mensal/{periodo}", response_model=PMPVMensalResponse)
def buscar_mensal(
    periodo: str,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> PMPVMensalResponse:
    pmpv = uc.repo.buscar_pmpv_mensal(periodo)
    return PMPVMensalResponse(pmpv=pmpv or 0.0)


@router.post("/mensal/{periodo}", status_code=204)
def salvar_mensal(
    periodo: str,
    payload: PMPVMensalRequest,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> None:
    uc.salvar_pmpv_mensal(periodo, payload.pmpv)


@router.get("/periodos")
def listar_periodos(uc: PMPVUseCases = Depends(get_pmpv_use_cases)) -> list:
    return uc.repo.listar_periodos()


# TODO(spec §5.6): /pmpv/trimestre-ativo requer estender PMPVRepository com
# buscar_trimestre_ativo/salvar_trimestre_ativo (hoje só em DatabasePMPV,
# chamado direto pela View de PMPV e SCG).
# TODO(spec §4.1): /pmpv/importar-memoria requer wrapper de use case para
# ExcelPMPV.ler_dados_memoria_calculo recebendo UploadFile (multipart).
