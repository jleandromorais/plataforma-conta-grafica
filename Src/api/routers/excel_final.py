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
from Src.Services.servicos_cgf import ServicosCGF

router = APIRouter(prefix="/excel-final", tags=["Excel Final"])


class TrimestreExcelFinal(BaseModel):
    periodo: str
    meses: list[str]  # meses de Auditoria/RET/Conciliação agregados no arquivo


class CoberturaExcelFinal(BaseModel):
    anos: list[str]
    periodos: list[str]  # do mais antigo ao mais recente
    total: int


_ORDEM_MES = {m: i for i, m in enumerate(["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"])}


def _chave_periodo(p: str) -> tuple[int, int]:
    mes, ano = p.split("/")
    return int(ano), _ORDEM_MES.get(mes[:3].capitalize(), 0)


@router.get("/cobertura", response_model=CoberturaExcelFinal)
def cobertura() -> CoberturaExcelFinal:
    """Períodos com dados gravados: o que o Excel Final geral vai conter."""
    periodos = sorted({normalizar_periodo(p) for p in ServicosCGF().obter_periodos() if is_periodo_valido(p)}, key=_chave_periodo)
    anos = sorted({p.split("/")[1] for p in periodos})
    return CoberturaExcelFinal(anos=anos, periodos=periodos, total=len(periodos))


@router.post("/gerar-geral")
async def gerar_geral() -> FileResponse:
    """Excel Final com TODOS os períodos e anos gravados (sem filtro de mês)."""
    tmp = Path(tempfile.mkdtemp(prefix="excel_final_"))
    nome = "Excel_Final_ContaGrafica_Geral.xlsx"
    destino = tmp / nome
    await run_in_threadpool(
        lambda: ExcelConsolidado.exportar(periodo=None, nome_arquivo=str(destino), periodos_trimestre=None, abrir=False)
    )
    return FileResponse(
        destino, filename=nome,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True),
    )


@router.get("/trimestre", response_model=TrimestreExcelFinal)
def trimestre(periodo: str) -> TrimestreExcelFinal:
    """Quais meses entram no Excel Final gerado para `periodo`."""
    if not is_periodo_valido(periodo):
        raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
    norm = normalizar_periodo(periodo)
    return TrimestreExcelFinal(periodo=norm, meses=obter_periodos_trimestre(norm))


@router.post("/gerar")
async def gerar(periodo: str) -> FileResponse:
    """Gera o Excel Final do período e devolve o arquivo para download."""
    if not is_periodo_valido(periodo):
        raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
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
