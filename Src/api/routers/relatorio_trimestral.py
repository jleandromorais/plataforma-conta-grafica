from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from Src.common.excel_final_destino import obter_periodos_trimestre
from Src.common.periodos import is_periodo_valido, normalizar_periodo
from Src.infrastructure.exporters import relatorio_trimestral

router = APIRouter(prefix="/relatorio-trimestral", tags=["Relatório trimestral"])

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/gerar")
async def gerar(periodo: str) -> Response:
    """Word do trimestre civil que contém `periodo` (ex.: Ago/2026 → Jul–Set/2026):
    resultado dos meses e incongruências, pelas provas reais. Não grava nada."""
    if not is_periodo_valido(periodo):
        raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
    meses = obter_periodos_trimestre(normalizar_periodo(periodo))
    conteudo = await run_in_threadpool(
        lambda: relatorio_trimestral.montar(relatorio_trimestral.dados_do_trimestre(meses)))
    nome = f"Relatorio_Trimestral_{meses[0].replace('/', '-')}_a_{meses[-1].replace('/', '-')}.docx"
    return Response(conteudo, media_type=_DOCX, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
