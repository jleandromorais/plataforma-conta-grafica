"""Auditoria CGR — mesmas regras da tela desktop (tela_auditoria.py), via
Src/Services/servicos_auditoria_lote.py.

A pasta enviada tem uma subpasta por empresa, com XMLs e/ou PDFs de NF-e e
CT-e. O navegador manda cada arquivo com o caminho relativo no nome
("EMPRESA/sub/arquivo.xml"); um .zip com a mesma estrutura também é aceito.
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from Src.api.uploads import MAX_ARQUIVOS, descer_pasta_unica, gravar_arquivo, gravar_envio
from Src.api.schemas.auditoria import (
    ComparacaoAuditoria,
    HistoricoAuditoriaLinha,
    ItemAuditoria,
    ProcessarAuditoriaResponse,
    SalvarAuditoriaRequest,
    SalvarAuditoriaResponse,
    TotaisAuditoria,
)
from Src.Services import servicos_auditoria_lote as lote
from Src.Services.comparador_conta_grafica import ComparadorContaGrafica
from Src.Services.excel_auditoria import ExcelAuditoria
from Src.Services.servicos_auditoria import XMLItem
from Src.common.periodos import is_periodo_valido, normalizar_periodo

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])

def _item_para_api(item: XMLItem, base: Path) -> ItemAuditoria:
    try:
        rel = Path(item.caminho).resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        rel = Path(item.caminho).name
    return ItemAuditoria(
        empresa=item.empresa, tipo=item.tipo, numero=str(item.numero), valor_total=item.valor_total,
        icms=item.icms, icms_taxa=item.icms_taxa, pis=item.pis, cofins=item.cofins,
        volume=int(item.volume or 0), status=item.status, volume_total=item.volume_total, caminho=rel,
        cgr_liquido=lote.cgr_liquido_item(item), integra_cgr=lote.integra_cgr(item), devolucao=lote.eh_devolucao(item),
    )


def _item_da_api(i: ItemAuditoria) -> XMLItem:
    return XMLItem(i.empresa, i.tipo, i.numero, i.valor_total, i.icms, i.icms_taxa, i.pis, i.cofins,
                   i.volume, i.status, i.volume_total, i.caminho)


def _comparar(itens: list[XMLItem], planilha: Path | None, periodo: str):
    """Comparação opcional com a planilha da Conta Gráfica."""
    if planilha is None:
        return None, "Envie a planilha da Conta Gráfica para comparar as notas."
    if not is_periodo_valido(periodo):
        return None, "Informe o mês/ano para comparar com a planilha."
    comp = ComparadorContaGrafica.comparar(
        resultados=itens, df_excel=lote.carregar_planilha_comparacao(str(planilha)), periodo=periodo,
    )
    return comp, ""


@router.post("/processar", response_model=ProcessarAuditoriaResponse)
async def processar(request: Request) -> ProcessarAuditoriaResponse:
    """Audita a pasta enviada. NÃO grava nada.

    Campos do formulário: `arquivos` (vários; nome = caminho relativo, ou um
    .zip), `modo` ("XML" padrão | "PDF"), `empresas` (JSON com a lista a
    auditar; vazio = todas), `pasta_raiz` (nome da pasta, para detectar o
    mês), `periodo` e `planilha` (opcionais, para a comparação).
    """
    form = await request.form(max_files=MAX_ARQUIVOS, max_fields=MAX_ARQUIVOS)
    tmp = Path(tempfile.mkdtemp(prefix="auditoria_"))
    try:
        envio = tmp / "envio"
        envio.mkdir()
        gravar_envio(form, envio, {".xml", ".pdf"})
        planilha = gravar_arquivo(form, "planilha", tmp, "planilha")
        base = descer_pasta_unica(envio)
        empresas_pasta = sorted(p.name for p in base.iterdir() if p.is_dir())
        if not empresas_pasta:
            raise ValueError("Nenhuma subpasta de empresa encontrada. A pasta enviada deve ter uma subpasta por empresa.")

        escolhidas = json.loads(str(form.get("empresas") or "[]")) or empresas_pasta
        empresas = [e for e in escolhidas if e in empresas_pasta]
        usar_pdf = str(form.get("modo") or "XML").upper() == "PDF"
        periodo_detectado = lote.periodo_do_caminho(str(form.get("pasta_raiz") or "") + "/" + base.name)
        periodo = str(form.get("periodo") or "") or periodo_detectado

        itens, n_xml, n_pdf = await run_in_threadpool(lote.auditar_pasta, base, empresas, usar_pdf)
        tot = lote.calcular_totais(itens)
        comp, aviso = await run_in_threadpool(_comparar, itens, planilha, periodo)

        return ProcessarAuditoriaResponse(
            periodo_detectado=periodo_detectado,
            qtd_xml_lidos=n_xml,
            qtd_pdf_lidos=n_pdf,
            itens=[_item_para_api(i, base) for i in itens],
            totais=TotaisAuditoria(**{k: tot[k] for k in TotaisAuditoria.model_fields}),
            comparacao=ComparacaoAuditoria(
                periodo=comp.periodo,
                qtd_em_ambas=comp.qtd_em_ambas,
                notas_apenas_auditoria=comp.notas_apenas_nossa,
                notas_apenas_planilha=comp.notas_apenas_conta_grafica,
                abas_planilha=list(comp.sheets_excel),
                abas_do_periodo=list(comp.sheets_periodo_match),
                avisos=list(comp.avisos),
            ) if comp else None,
            aviso_comparacao=aviso,
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.post("/salvar", response_model=SalvarAuditoriaResponse)
def salvar(payload: SalvarAuditoriaRequest) -> SalvarAuditoriaResponse:
    """Grava o CGR (recalculado aqui a partir das notas) e os itens do período."""
    if not is_periodo_valido(payload.periodo):
        raise ValueError("Período inválido. Use o formato Jan/2026.")
    return SalvarAuditoriaResponse(**lote.salvar(payload.periodo, [_item_da_api(i) for i in payload.itens]))


@router.post("/relatorio")
async def relatorio(request: Request) -> FileResponse:
    """Relatório Excel da auditoria (o mesmo que o desktop gera).

    Formulário: `itens` (JSON da lista retornada por /processar), `periodo`
    e `planilha` (opcional, inclui as abas de comparação).
    """
    form = await request.form()
    itens = [_item_da_api(ItemAuditoria(**d)) for d in json.loads(str(form.get("itens") or "[]"))]
    if not itens:
        raise ValueError("Nenhuma nota para gerar o relatório.")
    periodo = str(form.get("periodo") or "")
    tmp = Path(tempfile.mkdtemp(prefix="auditoria_rel_"))
    planilha = gravar_arquivo(form, "planilha", tmp, "planilha")
    comp, _ = await run_in_threadpool(_comparar, itens, planilha, periodo)
    nome = f"Auditoria_{(normalizar_periodo(periodo) or 'sem-periodo').replace('/', '-')}.xlsx"
    destino = tmp / nome
    await run_in_threadpool(
        ExcelAuditoria.gerar_relatorio_auditoria, itens, str(destino),
        lote.calcular_totais(itens)["cgr_liquido"], comp,
    )
    return FileResponse(
        destino, filename=nome,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        background=BackgroundTask(shutil.rmtree, tmp, ignore_errors=True),
    )


@router.get("/historico", response_model=list[HistoricoAuditoriaLinha])
def historico() -> list[HistoricoAuditoriaLinha]:
    return [HistoricoAuditoriaLinha(**h) for h in lote.historico()]
