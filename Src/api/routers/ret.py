"""RET — Recuperação de Encargos de Transporte. Mesmas regras da tela desktop
(tela_ret.py) via RegrasRET e servicos_ret_lote: RET = Σ EAT × (1 − PIS/COFINS)
+ Σ EC, por mês de referência."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

from Src.api.schemas.ret import (
    DocumentoRET,
    HistoricoRETLinha,
    ProcessarRETResponse,
    RETMes,
    RETSalvo,
    SalvarRETRequest,
)
from Src.api.uploads import MAX_ARQUIVOS, descer_pasta_unica, gravar_envio
from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Services import servicos_ret_lote as lote_ret
from Src.Services.servicos_ret import PIS_COFINS_RATE, RegrasRET

router = APIRouter(prefix="/ret", tags=["RET"])


def _resumo_mes(periodo: str, docs: list[dict]) -> RETMes:
    calc = RegrasRET.calcular_ret(docs)
    return RETMes(
        periodo=periodo, qtd_documentos=len(docs), eat_bruto=calc["eat_bruto"],
        ec_docs_total=calc["ec_docs_total"], ret=calc["ret"], qtd_outros=len(calc["outros_docs"]),
    )


@router.post("/processar", response_model=ProcessarRETResponse)
async def processar(request: Request) -> ProcessarRETResponse:
    """Lê os PDFs da pasta enviada (`arquivos`, com o caminho relativo no nome,
    ou um .zip). NÃO grava nada. O tipo (EAT/EC) e o mês vêm dos nomes das pastas."""
    form = await request.form(max_files=MAX_ARQUIVOS, max_fields=MAX_ARQUIVOS)
    tmp = Path(tempfile.mkdtemp(prefix="ret_"))
    try:
        # A pasta raiz entra no caminho: o mês pode estar nela (ex.: "EAT fev26").
        raiz = str(form.get("pasta_raiz") or "").strip().replace("/", "_") or "envio"
        envio = tmp / raiz
        envio.mkdir()
        if not gravar_envio(form, envio, {".pdf"}):
            raise ValueError("A pasta enviada não tem nenhum PDF. Escolha a pasta com os PDFs das NDs e faturas "
                             "de transporte do mês.")
        base = descer_pasta_unica(envio)
        docs, lidos, ignorados = await run_in_threadpool(lote_ret.processar_pasta, base)
        for d in docs:
            d["caminho"] = Path(d["caminho"]).resolve().relative_to(tmp.resolve()).as_posix()
        grupos = lote_ret.agrupar_por_mes(docs)
        return ProcessarRETResponse(
            periodo_detectado=lote_ret.periodo_mais_comum(docs),
            qtd_lidos=lidos,
            qtd_ignorados=ignorados,
            pis_cofins_rate=PIS_COFINS_RATE,
            meses=[_resumo_mes(p, ds) for p, ds in sorted(grupos.items())],
            documentos=[DocumentoRET(**d) for d in docs],
            ocr_disponivel=OCR_ENABLED,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.post("/salvar", response_model=list[RETSalvo])
def salvar(payload: SalvarRETRequest) -> list[RETSalvo]:
    """Grava o RET de cada mês (recalculado aqui) e os documentos do mês."""
    if not payload.documentos:
        raise ValueError("Não há documentos na lista para salvar. Processe a pasta do mês primeiro.")
    docs = [d.model_dump() for d in payload.documentos]
    grupos = lote_ret.agrupar_por_mes(docs, periodo_padrao=payload.periodo_padrao)
    return [RETSalvo(**s) for s in lote_ret.salvar_meses(grupos)]


@router.get("/historico", response_model=list[HistoricoRETLinha])
def historico() -> list[HistoricoRETLinha]:
    return [HistoricoRETLinha(**h) for h in lote_ret.historico()]
