"""Excel Final (Módulo 9) — a mesma planilha consolidada do desktop
(ExcelConsolidado), gerada no servidor e baixada por quem pediu.

Diferente do desktop, não grava num arquivo fixo em Downloads: cada pessoa
recebe a sua cópia, então "o arquivo está aberto no Excel" deixa de ser
problema.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from Src.common.excel_final_destino import obter_periodos_trimestre
from Src.common.periodos import is_periodo_valido, normalizar_periodo
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

router = APIRouter(prefix="/excel-final", tags=["Excel Final"])


class TrimestreExcelFinal(BaseModel):
    periodo: str
    meses: list[str]  # meses de Auditoria/RET/Conciliação agregados no arquivo


@router.get("/trimestre", response_model=TrimestreExcelFinal)
def trimestre(periodo: str) -> TrimestreExcelFinal:
    """Quais meses entram no Excel Final gerado para `periodo`."""
    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
    norm = normalizar_periodo(periodo)
    return TrimestreExcelFinal(periodo=norm, meses=obter_periodos_trimestre(norm))


@router.post("/gerar")
async def gerar(periodo: str) -> FileResponse:
    """Gera o Excel Final do período e devolve o arquivo para download."""
    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
    norm = normalizar_periodo(periodo)
    tmp = Path(tempfile.mkdtemp(prefix="excel_final_"))
    nome = f"Excel_Final_ContaGrafica_{norm.replace('/', '-')}.xlsx"
    destino = tmp / nome
    await run_in_threadpool(
        lambda: ExcelConsolidado.exportar(
            periodo=norm, nome_arquivo=str(destino), periodos_trimestre=obter_periodos_trimestre(norm), abrir=False,
        )
    )
    return FileResponse(
        destino, filename=nome,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True),
    )
