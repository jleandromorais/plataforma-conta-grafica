from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from Src.common.excel_final_destino import obter_periodos_trimestre
from Src.common.periodos import is_periodo_valido, normalizar_periodo
from Src.infrastructure.exporters import nota_tecnica

router = APIRouter(prefix="/nota-tecnica", tags=["Nota Técnica"])

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/gerar")
async def gerar(periodo: str) -> Response:
    """Minuta da Nota Técnica do ciclo cujo trimestre civil apurado contém
    `periodo` (ex.: Jun/2026 → apura Abr–Jun/2026, PR de Ago–Out/2026)."""
    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
    meses = obter_periodos_trimestre(normalizar_periodo(periodo))
    conteudo = await run_in_threadpool(lambda: nota_tecnica.montar(nota_tecnica.dados_do_ciclo(meses)))
    mp = nota_tecnica.meses_do_pr(meses)
    nome = f"Minuta_NT_Repasse_{mp[0].replace('/', '-')}_a_{mp[-1].replace('/', '-')}.docx"
    return Response(conteudo, media_type=_DOCX, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
