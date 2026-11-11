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

from Src.api.schemas.comum import ProblemaArquivo
from Src.api.schemas.duplicatas import RemoverNotaRequest, RemoverNotaResponse
from Src.api.uploads import MAX_ARQUIVOS, descer_pasta_unica, gravar_arquivo, gravar_envio
from Src.api.schemas.auditoria import (
    ComparacaoAuditoria,
    DiferencasAuditoriaResponse,
    HistoricoAuditoriaLinha,
    IncluirNotaRequest,
    ItemAuditoria,
    ProcessarAuditoriaResponse,
    ProvaRealAuditoria,
    SalvarAuditoriaRequest,
    SalvarAuditoriaResponse,
    TotaisAuditoria,
)
from Src.Services import servicos_auditoria_lote as lote
from Src.Services import servicos_pr_automatico
from Src.Services.diferencas_auditoria import comparar_com_gravado
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


def _comparar(itens: list[XMLItem], planilha: Path | None, periodo: str,
              nome_planilha: str = "planilha", problemas: list[dict] | None = None):
    """Comparação opcional com a planilha da Conta Gráfica.

    Planilha que não abre (ou não dá para comparar) não derruba a auditoria:
    vira problema e a resposta segue sem comparação.
    """
    if planilha is None:
        return None, "Envie a planilha da Conta Gráfica para comparar as notas."
    if not is_periodo_valido(periodo):
        return None, "Informe o mês/ano para comparar com a planilha."
    try:
        return lote.comparar_com_planilha(itens, str(planilha), periodo), ""
    except Exception as e:  # noqa: BLE001 — qualquer falha de leitura vira mensagem, não 500
        if problemas is None:
            raise ValueError(f"Não consegui abrir a planilha de comparação “{nome_planilha}”. Abra no Excel, salve como .xlsx "
                             "(sem senha) e tente de novo.") from e
        problemas.append(lote.problema(
            nome_planilha, None, "erro", "planilha_comparacao_ilegivel",
            "Não consegui ler ou comparar a planilha. A auditoria foi feita, mas sem comparação. "
            "Confira se é a planilha da Conta Gráfica em .xlsx e tente de novo.",
            lote.motivo_curto(f"{type(e).__name__}: {e}", planilha),
        ))
        return None, "A planilha de comparação não pôde ser aberta (veja os problemas)."


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
        # Desce a pasta única e, no .zip original do mês, pula "EAT/", "Penalidade…/" e entra em "Nota Fiscal/".
        base, empresas_pasta, outras_etapas = lote.pasta_das_empresas(descer_pasta_unica(envio))
        if not empresas_pasta:
            raise ValueError("A pasta enviada não tem subpastas de empresa. Escolha a pasta “pai” do mês, que tem uma subpasta "
                             "por empresa (Petrobras, TAG, …) com os XML e PDF das notas.")

        problemas: list[dict] = [
            lote.problema(
                pasta, None, "aviso", "pasta_de_outra_etapa",
                "Esta pasta é de outra etapa do ciclo (encargos RET/EAT, penalidades RP ou CGF), não de notas de compra; "
                "ficou fora do CGR.",
            )
            for pasta in outras_etapas
        ]
        escolhidas = json.loads(str(form.get("empresas") or "[]")) or empresas_pasta
        empresas = [e for e in escolhidas if e in empresas_pasta]
        for e in escolhidas:
            if e not in empresas_pasta:
                problemas.append(lote.problema(
                    "", e, "aviso", "empresa_nao_encontrada",
                    "A empresa foi marcada, mas não há subpasta com esse nome na pasta enviada; ela não foi auditada.",
                ))
        usar_pdf = str(form.get("modo") or "XML").upper() == "PDF"
        # O caminho inteiro até as empresas: quando a pasta delas é "Nota Fiscal", o mês está na de cima.
        periodo_detectado = lote.periodo_do_caminho(str(form.get("pasta_raiz") or "") + "/" + base.relative_to(envio).as_posix())
        periodo = str(form.get("periodo") or "") or periodo_detectado

        itens, n_xml, n_pdf = await run_in_threadpool(lote.auditar_pasta, base, empresas, usar_pdf, None, problemas)
        tot = lote.calcular_totais(itens)
        up_planilha = form.get("planilha")
        nome_planilha = Path(getattr(up_planilha, "filename", "") or "planilha").name
        comp, aviso = await run_in_threadpool(_comparar, itens, planilha, periodo, nome_planilha, problemas)

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
                modelo=comp.modelo,
                modelo_rotulo=comp.modelo_rotulo,
                tipo=comp.tipo,
                fontes_cgr=comp.fontes_cgr,
                notas_mes_na_planilha=comp.notas_mes_na_planilha,
                cgr_auditoria=comp.cgr_auditoria,
                cgr_planilha_notas=comp.cgr_planilha_notas,
                cgr_planilha_conta_grafica=comp.cgr_planilha_conta_grafica,
                divergencias_valor=comp.divergencias_valor,
                por_empresa=comp.por_empresa,
            ) if comp else None,
            aviso_comparacao=aviso,
            problemas=[ProblemaArquivo(**p) for p in problemas],
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@router.post("/salvar", response_model=SalvarAuditoriaResponse)
def salvar(payload: SalvarAuditoriaRequest) -> SalvarAuditoriaResponse:
    """Grava o CGR (recalculado aqui a partir das notas) e os itens do período."""
    if not is_periodo_valido(payload.periodo):
        raise ValueError("Período inválido. Escolha o mês e o ano, por exemplo Jan/2026.")
    salvo = lote.salvar(payload.periodo, [_item_da_api(i) for i in payload.itens])
    # O CGR mudou o SCG do mês: o PR e o PV que o usam são regravados (em silêncio).
    servicos_pr_automatico.atualizar_dos_meses([payload.periodo])
    return SalvarAuditoriaResponse(**salvo)


@router.post("/remover-nota", response_model=RemoverNotaResponse)
def remover_nota(payload: RemoverNotaRequest) -> RemoverNotaResponse:
    """Tira UMA nota gravada do mês (o aviso "Possível duplicata" da prova real) e regrava o CGR sem ela."""
    periodo = normalizar_periodo(payload.periodo) or payload.periodo
    salvo = lote.remover_nota(periodo, payload.id)
    # O CGR mudou o SCG do mês: o PR e o PV que o usam são regravados (em silêncio).
    servicos_pr_automatico.atualizar_dos_meses([periodo])
    return RemoverNotaResponse(**salvo)


@router.post("/incluir-nota", response_model=RemoverNotaResponse)
def incluir_nota(payload: IncluirNotaRequest) -> RemoverNotaResponse:
    """Inclui no CGR do mês UMA nota que só está na planilha (o fornecedor não mandou), com o motivo."""
    periodo = normalizar_periodo(payload.periodo) or payload.periodo
    salvo = lote.incluir_nota(
        periodo, empresa=payload.empresa, numero=payload.numero, cgr_liquido=payload.cgr_liquido,
        motivo=payload.motivo, valor_total=payload.valor_total, volume_total=payload.volume_total,
        linha_excel=payload.linha_excel, tipo=payload.tipo,
    )
    # O CGR mudou o SCG do mês: o PR e o PV que o usam são regravados (em silêncio).
    servicos_pr_automatico.atualizar_dos_meses([periodo])
    return RemoverNotaResponse(**salvo)


@router.post("/diferencas", response_model=DiferencasAuditoriaResponse)
def diferencas(payload: SalvarAuditoriaRequest) -> DiferencasAuditoriaResponse:
    """Onde as notas recém-auditadas diferem das gravadas no mês. Não grava nada."""
    if not is_periodo_valido(payload.periodo):
        raise ValueError("Período inválido. Escolha o mês e o ano, por exemplo Jan/2026.")
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        gravados = db.listar_auditoria_itens(payload.periodo) or []
        cgr = (db.buscar_consolidacao(payload.periodo) or {}).get("cgr")
    itens = [_item_da_api(i) for i in payload.itens]
    return DiferencasAuditoriaResponse(**comparar_com_gravado(itens, gravados, float(cgr) if cgr is not None else None))


@router.post("/relatorio")
async def relatorio(request: Request) -> FileResponse:
    """Relatório Excel da auditoria (o mesmo que o desktop gera).

    Formulário: `itens` (JSON da lista retornada por /processar), `periodo`
    e `planilha` (opcional, inclui as abas de comparação).
    """
    form = await request.form()
    itens = [_item_da_api(ItemAuditoria(**d)) for d in json.loads(str(form.get("itens") or "[]"))]
    if not itens:
        raise ValueError("Não há notas na lista para gerar o relatório. Audite a pasta do mês primeiro.")
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


@router.get("/prova-real", response_model=ProvaRealAuditoria)
def prova_real(periodo: str) -> ProvaRealAuditoria:
    """A conta do CGR gravado do mês, aberta por empresa, com o selo "confere". Não grava nada."""
    if not is_periodo_valido(periodo):
        raise ValueError("Período inválido. Escolha o mês e o ano, por exemplo Jan/2026.")
    return ProvaRealAuditoria(**lote.prova_real(normalizar_periodo(periodo) or periodo))


@router.get("/historico", response_model=list[HistoricoAuditoriaLinha])
def historico() -> list[HistoricoAuditoriaLinha]:
    return [HistoricoAuditoriaLinha(**h) for h in lote.historico()]
