"""Conciliação RP — penalidades. RP = Σ despesas − Σ receitas (planilha
oficial, linha "Saldo de penalidade"). Regras de leitura dos PDFs em
RegrasConcilia; orquestração em servicos_concilia_lote."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from Src.api import erros_ciclo
from Src.api.schemas.conciliacao import (
    HistoricoConciliacaoLinha,
    ItemConciliacao,
    ProcessarConciliacaoResponse,
    ProvaRealRP,
    SalvarConciliacaoRequest,
    SalvarConciliacaoResponse,
    TotaisConciliacao,
)
from Src.api.schemas.duplicatas import RemoverNotaRequest, RemoverNotaResponse
from Src.common.periodos import normalizar_periodo
from Src.api.uploads import MAX_ARQUIVOS, gravar_envio
from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Services import servicos_concilia_lote as lote_concilia
from Src.Services import servicos_pr_automatico
from Src.infrastructure.exporters.excel_concilia import ExcelConcilia
from Src.Services.servicos_concilia import PdfItem

router = APIRouter(prefix="/conciliacao", tags=["Conciliação"])


def _item_da_api(i: ItemConciliacao) -> PdfItem:
    return PdfItem(file_name=i.arquivo, file_path=i.caminho, category=i.categoria,
                   amount=i.valor, status=i.status, method=i.metodo)


@router.post("/processar", response_model=ProcessarConciliacaoResponse)
async def processar(request: Request) -> ProcessarConciliacaoResponse:
    """Lê os PDFs das pastas enviadas nos campos `receitas` e `despesas`
    (caminho relativo no nome; ZIPs dentro das pastas também são lidos).
    NÃO grava nada."""
    form = await request.form(max_files=MAX_ARQUIVOS, max_fields=MAX_ARQUIVOS)
    # Nome neutro: RegrasConcilia classifica caminhos com "TOP" como receita.
    tmp = Path(tempfile.mkdtemp(prefix="concilia_"))
    try:
        pastas: dict[str, Path | None] = {}
        for campo in ("receitas", "despesas"):
            destino = tmp / campo
            destino.mkdir()
            pastas[campo] = destino if gravar_envio(form, destino, {".pdf"}, campo=campo) else None
        if not any(pastas.values()):
            raise ValueError("Envie a pasta de receitas e/ou a de despesas, com os PDFs das notas.")

        logs: list[str] = []
        itens = await run_in_threadpool(lote_concilia.processar, pastas["receitas"], pastas["despesas"], logs.append)
        return ProcessarConciliacaoResponse(
            itens=[
                ItemConciliacao(
                    arquivo=i.file_name, caminho=Path(i.file_path).resolve().relative_to(tmp.resolve()).as_posix(),
                    categoria=i.category, valor=i.amount, status=i.status, metodo=i.method,
                )
                for i in itens
            ],
            totais=TotaisConciliacao(**lote_concilia.totais(itens)),
            logs=logs,
            ocr_disponivel=OCR_ENABLED,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.post("/salvar", response_model=SalvarConciliacaoResponse)
def salvar(payload: SalvarConciliacaoRequest) -> SalvarConciliacaoResponse:
    """Grava o RP (recalculado aqui) e os itens do período."""
    salvo = lote_concilia.salvar(payload.periodo, [_item_da_api(i) for i in payload.itens])
    # O RP mudou o SCG do mês: o PR e o PV que o usam são regravados (em silêncio).
    servicos_pr_automatico.atualizar_dos_meses([payload.periodo])
    return SalvarConciliacaoResponse(**salvo)


@router.post("/remover-nota", response_model=RemoverNotaResponse)
def remover_nota(payload: RemoverNotaRequest) -> RemoverNotaResponse:
    """Tira UMA nota gravada do mês (o aviso "Possível duplicata" da prova real) e regrava o RP sem ela."""
    periodo = normalizar_periodo(payload.periodo) or payload.periodo
    salvo = lote_concilia.remover_nota(periodo, payload.id)
    # O RP mudou o SCG do mês: o PR e o PV que o usam são regravados (em silêncio).
    servicos_pr_automatico.atualizar_dos_meses([periodo])
    return RemoverNotaResponse(**salvo)


@router.post("/relatorio")
def relatorio(payload: SalvarConciliacaoRequest) -> FileResponse:
    """Relatório Excel da conciliação (o mesmo layout detalhado do desktop)."""
    itens = [_item_da_api(i) for i in payload.itens]
    if not itens:
        raise ValueError("Não há notas na lista para gerar o relatório. Processe as pastas de receitas e despesas primeiro.")
    tmp = Path(tempfile.mkdtemp(prefix="concilia_rel_"))
    nome = f"Conciliacao_{payload.periodo.replace('/', '-') or 'sem-periodo'}.xlsx"
    ExcelConcilia.gerar_relatorio(tmp / nome, itens, layout_bonito=True)
    return FileResponse(
        tmp / nome, filename=nome,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True),
    )


@router.get("/prova-real", response_model=ProvaRealRP)
def prova_real(periodo: str) -> ProvaRealRP:
    """A conta do RP gravado do mês, item a item, avisando notas repetidas. NÃO grava nada."""
    r = lote_concilia.prova_real(normalizar_periodo(periodo) or periodo)
    return ProvaRealRP(**r, erros=erros_ciclo.erros_prova_real_rp(r))


@router.get("/historico",response_model=list[HistoricoConciliacaoLinha])
def historico() -> list[HistoricoConciliacaoLinha]:
    return [HistoricoConciliacaoLinha(**h) for h in lote_concilia.historico()]

