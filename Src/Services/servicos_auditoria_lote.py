"""Auditoria CGR de uma pasta inteira (uma subpasta por empresa).

Orquestração que antes ficava dentro da tela desktop (tela_auditoria.py) e
agora é usada também pela API web. As regras fiscais continuam em
RegrasAuditoria (servicos_auditoria.py).

Duas correções em relação ao comportamento antigo da tela:
1. Devolução: era reconhecida só por "devolu" no caminho — pastas/arquivos
   "Devolvidas" escapavam e somavam no CGR em vez de subtrair;
2. Ao gravar os itens no banco, o CGR líquido de uma devolução ia POSITIVO,
   embora o total do CGR o subtraísse — a soma dos itens (usada pelo SCG
   "dos módulos") ficava maior que o CGR salvo.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Callable

from Src.Services.comparador_conta_grafica import _normalizar_numero_nota
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem, empresa_integra_cgr

_MESES_DETECT = {
    "JANEIRO": 1, "JAN": 1, "FEVEREIRO": 2, "FEV": 2, "MARÇO": 3, "MARCO": 3, "MAR": 3,
    "ABRIL": 4, "ABR": 4, "MAIO": 5, "MAI": 5, "JUNHO": 6, "JUN": 6,
    "JULHO": 7, "JUL": 7, "AGOSTO": 8, "AGO": 8, "SETEMBRO": 9, "SET": 9,
    "OUTUBRO": 10, "OUT": 10, "NOVEMBRO": 11, "NOV": 11, "DEZEMBRO": 12, "DEZ": 12,
}
_MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _sem_acento(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def periodo_do_caminho(caminho: str) -> str:
    """Detecta 'Jan/2026' a partir do nome das pastas no caminho."""
    tokens: list[str] = []
    for parte in Path(caminho).parts:
        tokens.extend(re.split(r'[\s\-_\.]+', parte.upper()))
    mes_num = 0
    for tok in reversed(tokens):  # do mais específico para o mais genérico
        if tok in _MESES_DETECT:
            mes_num = _MESES_DETECT[tok]
            break
    if not mes_num:
        return ""
    anos = re.findall(r'\b(20\d{2})\b', caminho)
    ano = int(anos[-1]) if anos else date.today().year
    return f"{_MESES_ABREV[mes_num - 1]}/{ano}"


# ── Regras por item ──────────────────────────────────────────────────────────

def eh_devolucao(item: XMLItem) -> bool:
    caminho = _sem_acento(item.caminho or "").lower()
    return "devolu" in caminho or "devolv" in caminho


def integra_cgr(item: XMLItem) -> bool:
    """NF-e (compra de gás) e CT-e da TAG/Mastergás (gasoduto) entram no CGR;
    CT-e das demais transportadoras é frete e fica fora."""
    return item.tipo == "NF-e" or empresa_integra_cgr(item.empresa)


def cgr_liquido_item(item: XMLItem) -> float:
    """Compra s/tributos do documento, NEGATIVA quando é devolução."""
    valor = RegrasAuditoria.calcular_s_tributos(item.valor_total, item.icms_taxa)
    return -valor if eh_devolucao(item) else valor


# ── Leitura dos arquivos ─────────────────────────────────────────────────────

def problema(arquivo: str, empresa: str | None, gravidade: str, codigo: str, mensagem: str,
             tecnico: str | None = None) -> dict:
    """Problema num arquivo, no formato de ProblemaArquivo (Src/api/schemas/comum.py)."""
    return {"arquivo": arquivo, "empresa": empresa, "gravidade": gravidade,
            "codigo": codigo, "mensagem": mensagem, "tecnico": tecnico}


def motivo_curto(texto: str, *caminhos: Path) -> str:
    """Motivo técnico sem caminho do servidor e com tamanho de uma linha."""
    for c in caminhos:
        texto = texto.replace(str(c), c.name)
    texto = " ".join(texto.split())
    return texto[:157] + "..." if len(texto) > 160 else texto


def _ler_xml(xml_path: Path, empresa: str) -> tuple[XMLItem | None, str, str]:
    """(item, código do problema, motivo). Sem problema: código ''."""
    tipo = RegrasAuditoria.detectar_tipo_xml(xml_path)
    if tipo == "nfe":
        dados = RegrasAuditoria.parse_nfe(xml_path)
    elif tipo == "cte":
        dados = RegrasAuditoria.parse_cte(xml_path)
    else:
        return None, "xml_tipo_desconhecido", ""
    if "erro" in dados:
        return None, "xml_invalido", motivo_curto(str(dados["erro"]), xml_path)
    vol_total = dados.get("volume_total", float(dados.get("volume", 0)))
    item = XMLItem(empresa, dados["tipo"], dados["numero"], dados["valor_total"],
                   dados["icms"], dados.get("icms_taxa", 0.0), dados["pis"], dados["cofins"],
                   int(vol_total), "OK", vol_total, str(xml_path))
    return item, "", ""


def auditar_xml(xml_path: Path, empresa: str) -> XMLItem | None:
    return _ler_xml(xml_path, empresa)[0]


def auditar_empresa(
    pasta_empresa: Path,
    empresa: str,
    usar_pdf: bool,
    progresso: Callable[[str], None] | None = None,
    problemas: list[dict] | None = None,
) -> tuple[list[XMLItem], int, int]:
    """Lê os XMLs (modo XML) e todos os PDFs da pasta de uma empresa.

    Todo PDF é lido (mesmo com XMLs presentes), para nunca descartar notas que
    só existem em PDF. A duplicata de um XML já lido só é descartada quando o
    número OU o valor total extraído do PDF batem com ele.
    Retorna (itens, qtd_xml_lidos, qtd_pdf_lidos). Se `problemas` for passada,
    recebe cada arquivo que não virou nota e o motivo (ver Front_end/SPEC_ERROS.md).
    """
    xmls = list({p.resolve() for p in pasta_empresa.rglob("*") if p.suffix.lower() == ".xml"})
    pdfs = list({p.resolve() for p in pasta_empresa.rglob("*") if p.suffix.lower() == ".pdf"})
    itens: list[XMLItem] = []
    notas_xml: set[str] = set()
    valores_xml: set[float] = set()
    n_xml = n_pdf = 0
    raiz = pasta_empresa.resolve()

    def anotar(arquivo: Path, gravidade: str, codigo: str, mensagem: str, tecnico: str = "") -> None:
        if problemas is not None:
            nome = arquivo.relative_to(raiz).as_posix() if arquivo.is_relative_to(raiz) else arquivo.name
            problemas.append(problema(nome, empresa, gravidade, codigo, mensagem, tecnico or None))

    if not xmls and not pdfs and problemas is not None:
        problemas.append(problema("", empresa, "aviso", "empresa_sem_notas",
                                  "A pasta da empresa não tem XML nem PDF; nada foi auditado."))

    if not usar_pdf:
        for i, xml_file in enumerate(xmls, start=1):
            n_xml += 1
            item, codigo, motivo = _ler_xml(xml_file, empresa)
            if codigo == "xml_invalido":
                anotar(xml_file, "aviso", codigo, "O XML não pôde ser lido; a nota não entrou no CGR. "
                       "Baixe o XML de novo do portal e reenvie a pasta.", motivo)
            elif codigo == "xml_tipo_desconhecido":
                anotar(xml_file, "info", codigo, "Não é NF-e nem CT-e (evento, cancelamento etc.); ignorado.")
            if item:
                itens.append(item)
                notas_xml.add(_normalizar_numero_nota(item.numero))
                valores_xml.add(round(item.valor_total, 2))
            if progresso and i % 25 == 0:
                progresso(f"{empresa}: {i}/{len(xmls)} XMLs")

    for i, pdf_file in enumerate(pdfs, start=1):
        n_pdf += 1
        dados = RegrasAuditoria.parse_pdf_ocr(pdf_file)
        if progresso and i % 10 == 0:
            progresso(f"{empresa}: {i}/{len(pdfs)} PDFs")
        if "erro" in dados:
            anotar(pdf_file, "aviso", "pdf_ocr_falhou", "Não consegui ler o PDF; a nota não entrou no CGR. "
                   "Se a nota importa, envie o XML dela.", motivo_curto(str(dados["erro"]), pdf_file))
            continue
        nota = _normalizar_numero_nota(dados.get("numero", ""))
        valor = round(float(dados.get("valor_total", 0.0) or 0.0), 2)
        if not usar_pdf and ((nota and nota in notas_xml) or (valor and valor in valores_xml)):
            continue  # já capturada via XML
        itens.append(XMLItem(
            empresa, dados.get("tipo", "NF-e"), dados.get("numero", "N/A"), dados.get("valor_total", 0.0),
            dados.get("icms", 0.0), dados.get("icms_taxa", 0.0), dados.get("pis", 0.0), dados.get("cofins", 0.0),
            dados.get("volume", 0), "OCR", dados.get("volume_total", 0.0), str(pdf_file),
        ))
    return itens, n_xml, n_pdf


def auditar_pasta(
    pasta: Path,
    empresas: list[str],
    usar_pdf: bool,
    progresso: Callable[[str], None] | None = None,
    problemas: list[dict] | None = None,
) -> tuple[list[XMLItem], int, int]:
    """Audita as subpastas `empresas` de `pasta`. Retorna itens deduplicados."""
    todos: list[XMLItem] = []
    n_xml = n_pdf = 0
    for idx, empresa in enumerate(empresas, start=1):
        if progresso:
            progresso(f"Auditando {empresa} ({idx}/{len(empresas)})...")
        itens, x, p = auditar_empresa(pasta / empresa, empresa, usar_pdf, progresso, problemas)
        todos.extend(itens)
        n_xml += x
        n_pdf += p
    return deduplicar(todos), n_xml, n_pdf


def deduplicar(itens: list[XMLItem]) -> list[XMLItem]:
    """Um item por (empresa, tipo, número) — segurança contra XMLs repetidos."""
    vistos: set[tuple] = set()
    unicos = []
    for item in itens:
        chave = (item.empresa, item.tipo, item.numero)
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(item)
    return unicos


# ── Totais ───────────────────────────────────────────────────────────────────

def calcular_totais(itens: list[XMLItem]) -> dict:
    nfes = [i for i in itens if i.tipo == "NF-e"]
    ctes = [i for i in itens if i.tipo == "CT-e"]
    do_cgr = [i for i in itens if integra_cgr(i)]

    por_empresa: dict[str, list[XMLItem]] = defaultdict(list)
    for i in itens:
        por_empresa[i.empresa].append(i)

    return {
        "qtd_nfe": len(nfes),
        "qtd_cte": len(ctes),
        "qtd_devolucoes": sum(1 for i in itens if eh_devolucao(i)),
        "valor_total_nfe": sum(i.valor_total for i in nfes),
        "valor_total_cte": sum(i.valor_total for i in ctes),
        "valor_total_geral": sum(i.valor_total for i in itens),
        "volume_total_geral": sum(i.volume_total for i in itens),
        "icms_cgr": sum(i.valor_total * i.icms_taxa for i in do_cgr),
        "cgr_liquido": sum(cgr_liquido_item(i) for i in do_cgr),
        "por_empresa": [
            {
                "empresa": emp,
                "qtd_nfe": sum(1 for i in lista if i.tipo == "NF-e"),
                "qtd_cte": sum(1 for i in lista if i.tipo == "CT-e"),
                "valor_total": sum(i.valor_total for i in lista),
                # Só o que entra no CGR — a soma das empresas bate com o total.
                "cgr_liquido": sum(cgr_liquido_item(i) for i in lista if integra_cgr(i)),
                "frete_fora_do_cgr": sum(i.valor_total for i in lista if not integra_cgr(i)),
            }
            for emp, lista in sorted(por_empresa.items())
        ],
    }


def carregar_planilha_comparacao(caminho: str):
    """Lê TODAS as abas da planilha da Conta Gráfica num único DataFrame, com
    a coluna `__sheet_name__` (usada pelo comparador para achar a aba do mês)."""
    import pandas as pd

    planilhas = pd.read_excel(caminho, sheet_name=None)
    frames = []
    for nome_aba, df_aba in planilhas.items():
        if df_aba is None or df_aba.empty:
            continue
        df_tmp = df_aba.copy()
        df_tmp["__sheet_name__"] = str(nome_aba)
        frames.append(df_tmp)
    if not frames:
        raise ValueError("A planilha selecionada não contém abas com dados.")
    return pd.concat(frames, ignore_index=True, sort=False)


def salvar(periodo: str, itens: list[XMLItem]) -> dict:
    """Grava o CGR líquido do período (consolidação → recalcula RPV) e
    substitui os itens auditados do período."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao

    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
    if not itens:
        raise ValueError("Nenhuma nota auditada para salvar.")
    cgr = calcular_totais(itens)["cgr_liquido"]
    with ServicosConsolidacao() as consolidacao:
        rpv = consolidacao.salvar_cgr(periodo, cgr)["rpv"]
    with DatabasePMPV() as db:
        db.salvar_auditoria_itens(periodo, itens_para_banco(itens))
    return {"cgr_liquido": cgr, "rpv": rpv, "qtd_itens": len(itens)}


def historico() -> list[dict]:
    """CGR gravado e quantidade de notas por período auditado."""
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        linhas = []
        for periodo in db.listar_periodos_auditoria():
            itens = db.listar_auditoria_itens(periodo) or []
            cons = db.buscar_consolidacao(periodo) or {}
            linhas.append({
                "periodo": periodo,
                "qtd_notas": len(itens),
                "cgr_gravado": float(cons.get("cgr") or 0.0),
                "data_atualizacao": (cons.get("data_atualizacao") or "")[:16],
            })
    from Src.common.periodos import ordenar_historico
    return ordenar_historico(linhas)


def itens_para_banco(itens: list[XMLItem]) -> list[dict]:
    """Formato de DatabasePMPV.salvar_auditoria_itens, com o CGR líquido
    negativo nas devoluções."""
    return [
        {
            "empresa": i.empresa,
            "tipo": i.tipo,
            "numero": i.numero,
            "valor_total": i.valor_total,
            "icms": i.icms,
            "pis": i.pis,
            "cofins": i.cofins,
            "volume_total": i.volume_total,
            "cgr_liquido": cgr_liquido_item(i),
        }
        for i in itens
    ]
