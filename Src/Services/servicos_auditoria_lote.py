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

import logging
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Callable

from Src.common.periodos import ano_do_caminho
from Src.common.duplicatas import possiveis_duplicatas_por_valor
from Src.Services.comparador_conta_grafica import _normalizar_numero_nota
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem, empresa_integra_cgr

logger = logging.getLogger(__name__)

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
    """Detecta 'Jan/2026' a partir do nome das pastas no caminho ("" se o mês ou o ano não aparecem)."""
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
    ano = ano_do_caminho(caminho)
    return f"{_MESES_ABREV[mes_num - 1]}/{ano}" if ano else ""


# Pastas que vêm junto no .zip do mês mas são de OUTRA etapa do ciclo (mesmas
# palavras do Front_end/src/utils/pastaCiclo.ts): encargos (RET/EAT), penalidades
# (RP/TOP) e CGF. Não são empresas; se entrassem, viravam "notas" do CGR.
_PASTA_OUTRA_ETAPA = re.compile(
    r"^ret\b|\beat\b|encargos? de transporte|^rp\b|penalidade|\btop\b|receita|despesa|\bcgf\b|total mensal"
)
# Pasta que só embrulha as empresas ("Nota Fiscal", "Notas Fiscais", "NFs", "NF-e").
_PASTA_DE_NOTAS = re.compile(r"\bnotas? fisca|\bnfs?\b|\bnf-?e\b")


def pasta_das_empresas(base: Path) -> tuple[Path, list[str], list[str]]:
    """Acha a pasta cujas subpastas são as empresas.

    O .zip original do mês às vezes traz "EAT/", "Penalidade (…)/" e
    "Nota Fiscal/<Empresa>/…" lado a lado: sem isso, "Nota Fiscal" e "EAT"
    viravam empresas. As pastas de outra etapa são deixadas de fora e, se sobra
    uma única pasta de notas com subpastas, desce nela.
    Retorna (pasta, empresas, pastas de outra etapa ignoradas).
    """
    atual = base
    ignoradas: list[str] = []
    while True:
        subpastas = sorted(p for p in atual.iterdir() if p.is_dir())
        fora = [p for p in subpastas if _PASTA_OUTRA_ETAPA.search(_sem_acento(p.name).lower())]
        restantes = [p for p in subpastas if p not in fora]
        ignoradas += [p.relative_to(base).as_posix() for p in fora]
        unica = restantes[0] if len(restantes) == 1 else None
        if unica and _PASTA_DE_NOTAS.search(_sem_acento(unica.name).lower()) and any(c.is_dir() for c in unica.iterdir()):
            atual = unica
            continue
        return atual, [p.name for p in restantes], ignoradas


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
        raise ValueError("A planilha de comparação não tem nenhuma aba com dados. Confira se escolheu o arquivo certo.")
    return pd.concat(frames, ignore_index=True, sort=False)


def comparar_com_planilha(itens: list[XMLItem], caminho: str, periodo: str):
    """Compara as notas auditadas com a planilha da Conta Gráfica.

    Usa o primeiro modelo conhecido que reconhece a planilha (Src/Services/
    comparacao_registro.py); se nenhum reconhece, o comparador genérico (só presença)."""
    from Src.Services.comparacao_registro import comparar_com_modelo
    from Src.Services.comparador_conta_grafica import ComparadorContaGrafica

    resultado = comparar_com_modelo(itens, caminho, periodo)
    if resultado is not None:
        return resultado
    return ComparadorContaGrafica.comparar(
        resultados=itens, df_excel=carregar_planilha_comparacao(caminho), periodo=periodo,
    )


ROTULO_GENERICO = "Planilha sem modelo conhecido (confere só se a nota está lá)"
AVISO_PLANILHA_ILEGIVEL = ("Não consegui abrir esta planilha. Confira se é a planilha da Conta Gráfica em .xlsx "
                           "(sem senha) e tente de novo.")


def conferir_planilha(caminho: str, meses: list[str]) -> dict:
    """Abre a planilha da Conta Gráfica e diz se cada mês está nela. NÃO audita notas nem grava nada.

    Usa a mesma detecção de modelo da comparação (comparacao_registro); sem modelo conhecido,
    procura o mês no nome das abas, como o comparador genérico. Planilha que não abre
    vira `ok: False` com o motivo, nunca exceção."""
    from Src.Services.comparacao_registro import reconhecer_modelo
    from Src.Services.comparador_conta_grafica import _sheet_corresponde_periodo

    try:
        achado = reconhecer_modelo(caminho)
        if achado is not None:
            m, lido = achado
            tipo, rotulo = m.tipo, m.rotulo
            linhas = [{"periodo": p, **m.conferir_mes(lido, p)} for p in meses]
        else:
            abas = sorted({str(n) for n in carregar_planilha_comparacao(caminho)["__sheet_name__"]})
            tipo, rotulo = "generico", ROTULO_GENERICO
            linhas = []
            for p in meses:
                do_mes = [a for a in abas if _sheet_corresponde_periodo(a, p)]
                linhas.append({"periodo": p, "tem": bool(do_mes), "abas": do_mes, "qtd_notas": None})
    except Exception:  # noqa: BLE001 — arquivo corrompido, sem senha certa, não-xlsx: vira aviso, não 500
        logger.warning("Planilha de comparação ilegível na conferência", exc_info=True)
        return {"ok": False, "modelo": None, "modelo_rotulo": None,
                "meses": [{"periodo": p, "tem": False, "abas": [], "qtd_notas": None} for p in meses],
                "aviso": AVISO_PLANILHA_ILEGIVEL}

    if tipo == "generico" and not any(x["tem"] for x in linhas):
        return {"ok": False, "modelo": tipo, "modelo_rotulo": rotulo, "meses": linhas,
                "aviso": "Abri o arquivo, mas ele não parece a planilha da Conta Gráfica: não achei nenhuma aba de "
                         f"{', '.join(meses)}. Confira se escolheu a planilha certa."}
    faltam = [x["periodo"] for x in linhas if not x["tem"]]
    if not faltam:
        aviso = None
    elif len(faltam) == len(linhas):
        aviso = f"A planilha abriu, mas não tem {', '.join(faltam)}. Confira se é a planilha deste trimestre."
    else:
        aviso = f"A planilha não tem {', '.join(faltam)}. Dá para comparar os outros meses."
    return {"ok": True, "modelo": tipo, "modelo_rotulo": rotulo, "meses": linhas, "aviso": aviso}


def salvar(periodo: str, itens: list[XMLItem]) -> dict:
    """Grava o CGR líquido do período (consolidação → recalcula RPV) e
    substitui os itens auditados do período."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao

    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: “{periodo}”. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.")
    if not itens:
        raise ValueError("Não há notas auditadas na lista para salvar. Audite a pasta do mês primeiro.")
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


TOL_PROVA_REAL = 1.0  # R$: abaixo disso é arredondamento


def _integra_cgr_gravado(g: dict) -> bool:
    """Item gravado que entra no CGR: NF-e, ou CT-e de gasoduto (`empresa_integra_cgr`); o resto é frete."""
    return g.get("tipo") == "NF-e" or empresa_integra_cgr(g.get("empresa", ""))


def remover_nota(periodo: str, item_id: int) -> dict:
    """Tira UMA nota gravada do mês (a cópia repetida, por exemplo) e regrava o CGR sem ela
    (e o RPV, que sai do CGR). O CGR novo é a soma do `cgr_liquido` gravado das notas que entram
    no CGR, a MESMA conta da prova real. O chamador atualiza o SCG/PR (atualizar_dos_meses)."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: “{periodo}”. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.")
    with DatabasePMPV() as db:
        atuais = db.listar_auditoria_itens(periodo) or []
        if not any(g.get("id") == item_id for g in atuais):
            raise ValueError("Essa nota não está mais gravada neste mês. Atualize a página e confira a lista.")
        if len(atuais) == 1:
            raise ValueError("Essa é a única nota gravada do mês, então não dá para tirá-la. "
                             "Para refazer o mês, audite e grave de novo.")
        db.remover_item_do_periodo("auditoria_itens", periodo, item_id)
        restantes = [g for g in atuais if g.get("id") != item_id]
    cgr = sum(float(g.get("cgr_liquido") or 0.0) for g in restantes if _integra_cgr_gravado(g))
    with ServicosConsolidacao() as consolidacao:
        consolidacao.salvar_cgr(periodo, cgr)
    return {"periodo": periodo, "valor_gravado": cgr, "qtd_itens": len(restantes)}


ORIGEM_DIGITADA = "digitada"


def incluir_nota(periodo: str, *, empresa: str, numero: str, cgr_liquido: float, motivo: str,
                 valor_total: float | None = None, volume_total: float | None = None,
                 linha_excel: int | None = None, tipo: str | None = None) -> dict:
    """Inclui no mês UMA nota que não veio nos arquivos (ex.: o fornecedor não mandou), com o CGR
    da planilha, marcada como "digitada" e com o motivo. Regrava o CGR (e o RPV) com a MESMA conta
    da prova real. O chamador atualiza o SCG/PR (atualizar_dos_meses).

    Se o mês for auditado e gravado de novo pelos arquivos, a nota digitada sai (o salvar substitui
    as notas do mês): aí é preciso incluí-la outra vez."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: “{periodo}”. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.")
    empresa, numero, motivo = (empresa or "").strip(), (numero or "").strip(), (motivo or "").strip()
    if not empresa or not numero:
        raise ValueError("Informe a empresa e o número da nota.")
    if len(motivo) < 5:
        raise ValueError("Escreva o motivo de incluir a nota à mão (ex.: o fornecedor não mandou a nota).")
    if not cgr_liquido:
        raise ValueError("O CGR da nota não pode ser zero.")
    # Sem o tipo, vale o fornecedor: gasoduto (TAG, Mastergás) emite CT-e; os demais, NF-e. Os dois entram no CGR.
    tipo = tipo or ("CT-e" if empresa_integra_cgr(empresa) else "NF-e")
    if motivo and linha_excel:
        motivo = f"{motivo} (planilha, linha {linha_excel})"

    chave = (empresa.casefold(), _normalizar_numero_nota(numero))
    with DatabasePMPV() as db:
        atuais = db.listar_auditoria_itens(periodo) or []
        if any((str(g.get("empresa") or "").casefold(), _normalizar_numero_nota(g.get("numero") or "")) == chave for g in atuais):
            raise ValueError(f"A nota {numero} de {empresa} já está gravada em {periodo}.")
        nova = {"empresa": empresa, "tipo": tipo, "numero": numero, "valor_total": float(valor_total or 0.0),
                "volume_total": float(volume_total or 0.0), "cgr_liquido": float(cgr_liquido),
                "origem": ORIGEM_DIGITADA, "motivo": motivo}
        db.incluir_auditoria_item(periodo, nova)
    todas = [*atuais, nova]
    cgr = sum(float(g.get("cgr_liquido") or 0.0) for g in todas if _integra_cgr_gravado(g))
    with ServicosConsolidacao() as consolidacao:
        consolidacao.salvar_cgr(periodo, cgr)
    return {"periodo": periodo, "valor_gravado": cgr, "qtd_itens": len(todas)}


def prova_real(periodo: str) -> dict:
    """A conta do CGR gravado do mês, aberta por empresa, a partir das notas gravadas.

    Refaz a soma que `calcular_totais` fez na hora de gravar, só com o que o banco
    guarda (`auditoria_itens.cgr_liquido`, já negativo nas devoluções): entra no CGR
    o que é NF-e ou CT-e de gasoduto (`empresa_integra_cgr`); o resto é frete e fica
    fora. Compara a soma com o CGR da consolidação. Não grava nada.
    """
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        itens = db.listar_auditoria_itens(periodo) or []
        cons = db.buscar_consolidacao(periodo) or {}

    integra = _integra_cgr_gravado
    por_empresa: dict[str, dict] = {}
    for g in itens:
        e = por_empresa.setdefault(g.get("empresa") or "(sem empresa)", {
            "empresa": g.get("empresa") or "(sem empresa)", "qtd_nfe": 0, "qtd_cte": 0, "qtd_devolucoes": 0,
            "compras": 0.0, "devolucoes": 0.0, "frete_fora_do_cgr": 0.0, "cgr": 0.0,
        })
        e["qtd_nfe" if g.get("tipo") == "NF-e" else "qtd_cte"] += 1
        if not integra(g):
            e["frete_fora_do_cgr"] += float(g.get("valor_total") or 0.0)
            continue
        cgr = float(g.get("cgr_liquido") or 0.0)
        if cgr < 0:
            e["devolucoes"] += cgr
            e["qtd_devolucoes"] += 1
        else:
            e["compras"] += cgr
        e["cgr"] += cgr

    empresas = sorted(por_empresa.values(), key=lambda e: e["empresa"])
    cgr_das_notas = sum(e["cgr"] for e in empresas)
    gravado = cons.get("cgr")
    cgr_gravado = float(gravado) if gravado is not None else None
    diferenca = cgr_das_notas - cgr_gravado if cgr_gravado is not None else None
    return {
        "periodo": periodo,
        "qtd_notas": len(itens),
        "por_empresa": empresas,
        "compras": sum(e["compras"] for e in empresas),
        "devolucoes": sum(e["devolucoes"] for e in empresas),
        "frete_fora_do_cgr": sum(e["frete_fora_do_cgr"] for e in empresas),
        "cgr_das_notas": cgr_das_notas,
        "cgr_gravado": cgr_gravado,
        "diferenca": diferenca,
        # Sem notas gravadas (mês gravado só com o total) não há o que provar.
        "confere": bool(itens) and diferenca is not None and abs(diferenca) <= TOL_PROVA_REAL,
        # Mesmo valor + mesma empresa + mesmo tipo (NF-e/CT-e) com números diferentes = possível cópia.
        "possiveis_duplicatas_valor": possiveis_duplicatas_por_valor(
            itens,
            grupo=lambda g: f"{g.get('tipo') or '?'} · {g.get('empresa') or '(sem empresa)'}",
            valor=lambda g: g.get("valor_total"),
            nome=lambda g: f"{g.get('tipo') or 'Nota'} {g.get('numero') or '(sem número)'}",
        ),
        # Notas incluídas à mão (não vieram nos arquivos): a tela mostra com o motivo e deixa tirar.
        "notas_digitadas": [
            {"id": g.get("id"), "empresa": g.get("empresa") or "", "tipo": g.get("tipo") or "",
             "numero": g.get("numero") or "", "cgr_liquido": float(g.get("cgr_liquido") or 0.0),
             "motivo": g.get("motivo") or ""}
            for g in itens if g.get("origem") == ORIGEM_DIGITADA
        ],
        "data_atualizacao": (cons.get("data_atualizacao") or "")[:16],
    }


def itens_gravados_como_xml(gravados: list[dict]) -> list[XMLItem]:
    """Remonta as notas gravadas do mês como XMLItem, para os mesmos comparadores da tela.

    O banco não guarda a alíquota de ICMS nem o caminho do arquivo, mas guarda o CGR de cada nota
    (negativo na devolução). A alíquota sai desse CGR, então `cgr_liquido_item` devolve
    exatamente o valor gravado; a devolução vira um caminho com "devolucao". Nota digitada sem
    valor com tributos ganha um valor que dá o mesmo CGR, com alíquota 0."""
    from Src.Services.servicos_auditoria import PIS_COFINS_RATE

    itens = []
    for g in gravados:
        cgr = float(g.get("cgr_liquido") or 0.0)
        valor = float(g.get("valor_total") or 0.0)
        base = valor * (1.0 - PIS_COFINS_RATE)
        if base > 0 and abs(cgr) <= base:
            taxa = 1.0 - abs(cgr) / base
        else:
            valor, taxa = abs(cgr) / (1.0 - PIS_COFINS_RATE), 0.0
        vol = float(g.get("volume_total") or 0.0)
        itens.append(XMLItem(
            empresa=g.get("empresa") or "", tipo=g.get("tipo") or "NF-e", numero=str(g.get("numero") or ""),
            valor_total=valor, icms=float(g.get("icms") or 0.0), icms_taxa=taxa,
            pis=float(g.get("pis") or 0.0), cofins=float(g.get("cofins") or 0.0),
            volume=int(round(vol)), status="", volume_total=vol,
            caminho="devolucao" if cgr < 0 else "",
        ))
    return itens


def comparar_gravado_com_planilha(periodo: str, caminho: str) -> dict:
    """As notas GRAVADAS do mês contra a planilha da Conta Gráfica, com o mesmo comparador da tela
    da Auditoria. Resumo para o relatório; nunca levanta (erro vira `erro`). Não grava nada."""
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        gravados = db.listar_auditoria_itens(periodo) or []
    base = {"periodo": periodo, "erro": None, "tem_mes": False, "modelo_rotulo": "", "cgr_notas": None,
            "fontes_cgr": [], "qtd_em_ambas": 0, "so_na_planilha": [], "so_gravadas": [], "divergencias": [],
            "supridores": []}
    if not gravados:
        return {**base, "erro": "Sem notas gravadas neste mês: não dá para comparar com a planilha."}
    try:
        r = comparar_com_planilha(itens_gravados_como_xml(gravados), caminho, periodo)
    except Exception as e:  # noqa: BLE001 — planilha ilegível vira aviso no relatório
        logger.warning("Relatório: comparação com a planilha falhou em %s", periodo, exc_info=True)
        return {**base, "erro": f"Não consegui comparar com a planilha: {e}"}
    tem_mes = bool(r.notas_mes_na_planilha or r.qtd_em_ambas or r.notas_apenas_conta_grafica
                   or any(f.get("valor") is not None for f in (r.fontes_cgr or [])))
    return {
        **base,
        "tem_mes": tem_mes,
        "modelo_rotulo": r.modelo_rotulo or "",
        "cgr_notas": r.cgr_auditoria,
        "fontes_cgr": [f for f in (r.fontes_cgr or []) if f.get("valor") is not None],
        "qtd_em_ambas": r.qtd_em_ambas,
        "so_na_planilha": [
            {"empresa": n.get("empresa") or n.get("supridor") or "", "numero": str(n.get("numero") or ""),
             "linha_excel": n.get("linha_excel"), "cgr_planilha": n.get("cgr_planilha")}
            for n in r.notas_apenas_conta_grafica],
        "so_gravadas": [
            {"empresa": n.get("empresa") or "", "tipo": n.get("tipo") or "", "numero": str(n.get("numero") or ""),
             "cgr_liquido": n.get("cgr_liquido")}
            for n in r.notas_apenas_nossa],
        "divergencias": [
            {"empresa": d.get("empresa") or "", "numero": str(d.get("numero") or ""), "linha_excel": d.get("linha_excel"),
             "motivos": list(d.get("motivos") or []), "diferenca_cgr": d.get("diferenca_cgr"),
             "explicacao": d.get("explicacao") or ""}
            for d in r.divergencias_valor],
        # Modelo por supridor (NT): só totais por empresa.
        "supridores": [
            {"empresa": s.get("empresa") or "", "diferenca": s.get("diferenca"), "confere": bool(s.get("confere"))}
            for s in (r.por_empresa or []) if r.tipo == "por_supridor"],
    }


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
