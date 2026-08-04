from __future__ import annotations

from typing import Iterator

from fastapi import APIRouter, Depends

from Src.api.schemas.dashboard import DashboardResponse
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
