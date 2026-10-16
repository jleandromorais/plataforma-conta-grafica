from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends

from Src.api import dashboard_extra
from Src.api.schemas.dashboard import DashboardEmpresas, DashboardResponse, DashboardRet, DashboardVolumes
from Src.application.use_cases.dashboard_use_cases import DashboardUseCases

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_use_cases() -> Iterator[DashboardUseCases]:
    with DashboardUseCases() as uc:
        yield uc


@router.get("", response_model=DashboardResponse)
def resumo(
    ano: str | None = None,
    uc: DashboardUseCases = Depends(get_dashboard_use_cases),
) -> DashboardResponse:
    return DashboardResponse(**uc.montar_resumo(ano))


@router.get("/empresas", response_model=DashboardEmpresas)
def por_empresa(ano: str | None = None) -> DashboardEmpresas:
    """CGR líquido, notas e impostos por empresa (Auditoria)."""
    return DashboardEmpresas(**dashboard_extra.empresas(ano))


@router.get("/ret", response_model=DashboardRet)
def encargos_ret(ano: str | None = None) -> DashboardRet:
    """Encargos RET por mês, separados por tipo de encargo."""
    return DashboardRet(**dashboard_extra.ret(ano))


@router.get("/volumes", response_model=DashboardVolumes)
def volumes_cgf(ano: str | None = None) -> DashboardVolumes:
    """Volumes do CGF por mês (faturado, devoluções, volume final) e totais."""
    return DashboardVolumes(**dashboard_extra.volumes(ano))
