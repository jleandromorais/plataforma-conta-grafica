from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from Src.api.uploads import gravar_arquivo
from Src.common.excel_final_destino import obter_periodos_trimestre
from Src.common.periodos import is_periodo_valido, normalizar_periodo
from Src.infrastructure.exporters import relatorio_trimestral

router = APIRouter(prefix="/relatorio-trimestral", tags=["Relatório trimestral"])

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.post("/gerar")
async def gerar(request: Request, periodo: str) -> Response:
    """Word do trimestre civil que contém `periodo` (ex.: Ago/2026 → Jul–Set/2026):
    resultado dos meses e incongruências, pelas provas reais. Não grava nada.

    Opcional: formulário com `planilha` (.xlsx da Conta Gráfica). Com ela, as notas gravadas de
    cada mês também são comparadas com a planilha (o que falta, o que sobra, o que difere)."""
    if not is_periodo_valido(periodo):
        raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
    meses = obter_periodos_trimestre(normalizar_periodo(periodo))
    form = await request.form()  # vazio quando não vem formulário
    tmp = Path(tempfile.mkdtemp(prefix="relatorio_trimestral_"))
    try:
        planilha = gravar_arquivo(form, "planilha", tmp, "planilha")
        caminho = str(planilha) if planilha else None
        conteudo = await run_in_threadpool(
            lambda: relatorio_trimestral.montar(relatorio_trimestral.dados_do_trimestre(meses, caminho)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    nome = f"Relatorio_Trimestral_{meses[0].replace('/', '-')}_a_{meses[-1].replace('/', '-')}.docx"
    return Response(conteudo, media_type=_DOCX, headers={"Content-Disposition": f'attachment; filename="{nome}"'})
