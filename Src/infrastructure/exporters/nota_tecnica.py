"""Minuta da Nota Técnica de repasse (formato da NT CTEEF da ARPE) ao fim do ciclo.

Usa como modelo a NT 15/2026 sem o conteúdo (`modelos/modelo_nota_tecnica.docx`:
estilos, numeração dos títulos e rodapé da ARPE) e preenche o que o sistema
calcula: SCG (Quadro 5), SR (Quadro 6), PR (Quadro 7), PV (Quadro 8), PMPV e o
Anexo A. O que depende do pleito ou do analista sai destacado em amarelo.

`montar(dados)` só desenha; `dados_do_ciclo(meses)` busca os números nos
serviços (fonte única dos cálculos).
"""
from __future__ import annotations

import calendar
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

_MODELOS = Path(__file__).parent / "modelos"
_ABREVS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
_NOMES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]
_NUM_TITULOS = "1"  # numeração dos títulos (Heading 1, níveis 0–2) no modelo
_CINZA = "D9D9D9"


# ── Formatação ────────────────────────────────────────────────────────────────

def _num(v: float, casas: int = 2) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v: float) -> str:
    return ("-" if v < 0 else "") + "R$ " + _num(abs(v))


def com_sinal(v: float, casas: int = 2, sufixo: str = "") -> str:
    """Como a NT escreve resultados: "[+] R$ 0,0135/m³", "[-] R$ 30.299,75"."""
    return f"[{'+' if v >= 0 else '-'}] R$ {_num(abs(v), casas)}{sufixo}"


def _idx(periodo: str) -> tuple[int, int]:
    mes, ano = periodo.split("/")
    return _ABREVS.index(mes[:3].capitalize()), int(ano)


def curto(periodo: str) -> str:
    """"Abr/2026" → "abr/26"."""
    i, ano = _idx(periodo)
    return f"{_ABREVS[i].lower()}/{str(ano)[-2:]}"


def por_extenso(meses: list[str]) -> str:
    """["Abr/2026", …, "Jun/2026"] → "1º de abril de 2026 a 30 de junho de 2026"."""
    i0, a0 = _idx(meses[0])
    i1, a1 = _idx(meses[-1])
    fim = calendar.monthrange(a1, i1 + 1)[1]
    return f"1º de {_NOMES[i0]} de {a0} a {fim} de {_NOMES[i1]} de {a1}"


def faixa(meses: list[str]) -> str:
    """"abr/26-jun/26"."""
    return f"{curto(meses[0])}-{curto(meses[-1])}"


def mes_ano(periodo: str) -> str:
    i, ano = _idx(periodo)
    return f"{_NOMES[i]}/{ano}"


def _desloca(periodo: str, n: int) -> str:
    i, ano = _idx(periodo)
    t = ano * 12 + i + n
    return f"{_ABREVS[t % 12]}/{t // 12}"


def meses_do_pr(meses_apurados: list[str]) -> list[str]:
    """Trimestre do PR alimentado pelo trimestre civil apurado (Abr–Jun → Ago–Out)."""
    return [_desloca(meses_apurados[-1], k) for k in (2, 3, 4)]


def trimestre_pr_do_mes(periodo: str) -> list[str]:
    """Trimestre do PR (Nov–Jan, Fev–Abr, Mai–Jul, Ago–Out) que contém o mês."""
    i, _ = _idx(periodo)
    inicio = _desloca(periodo, -((i + 2) % 3))
    return [_desloca(inicio, k) for k in range(3)]


# ── Peças do documento ────────────────────────────────────────────────────────

def _titulo(doc, texto: str, nivel: int):
    p = doc.add_paragraph(texto, style="Heading 1")
    num = OxmlElement("w:numPr")
    for tag, val in (("w:ilvl", str(nivel)), ("w:numId", _NUM_TITULOS)):
        el = OxmlElement(tag)
        el.set(qn("w:val"), val)
        num.append(el)
    p._p.get_or_add_pPr().append(num)
    return p


def _par(doc, *partes, estilo="Normal", alinhar=WD_ALIGN_PARAGRAPH.JUSTIFY):
    """Parágrafo com trechos: str, ("sigla", "PR", "ago/26-out/26") com subscrito,
    ("manual", texto) destacado em amarelo, ou ("negrito", texto)."""
    p = doc.add_paragraph(style=estilo)
    p.alignment = alinhar
    for parte in partes:
        if isinstance(parte, str):
            p.add_run(parte)
        elif parte[0] == "sigla":
            p.add_run(parte[1])
            p.add_run(parte[2]).font.subscript = True
        elif parte[0] == "manual":
            r = p.add_run(parte[1])
            r.font.highlight_color = WD_COLOR_INDEX.YELLOW
        elif parte[0] == "negrito":
            p.add_run(parte[1]).bold = True
    return p


def _citacao(doc, *linhas):
    for t in linhas:
        p = doc.add_paragraph(t, style="Normal")
        p.paragraph_format.left_indent = Cm(2)
        for r in p.runs:
            r.italic, r.font.size = True, Pt(10)


def _legenda(doc, texto: str):
    p = doc.add_paragraph(texto, style="Caption")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def _sombra(celula, cor: str):
    tc = celula._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor)
    tc.append(shd)


def _tabela(doc, cabecalho: list[str], linhas: list[list[str]], destaque: set[int] = frozenset(), larguras=None):
    """Tabela no padrão das NTs: cabeçalho cinza, 9 pt, valores à direita;
    `destaque` = índices das linhas em negrito com fundo cinza (totais)."""
    t = doc.add_table(rows=1 + len(linhas), cols=len(cabecalho))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, linha in enumerate([cabecalho] + linhas):
        total = i == 0 or (i - 1) in destaque
        for j, texto in enumerate(linha):
            c = t.cell(i, j)
            c.text = ""
            p = c.paragraphs[0]
            p.alignment = (WD_ALIGN_PARAGRAPH.CENTER if i == 0 or j == 1
                           else WD_ALIGN_PARAGRAPH.LEFT if j == 0 else WD_ALIGN_PARAGRAPH.RIGHT)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(texto)
            r.font.size, r.bold = Pt(9), total
            if total:
                _sombra(c, _CINZA)
            if larguras:
                c.width = Cm(larguras[j])
    doc.add_paragraph()
    return t


def _manual(doc, texto: str):
    _par(doc, ("manual", f"[{texto}]"))


# ── Documento ─────────────────────────────────────────────────────────────────

def montar(d: dict) -> bytes:
    """Monta a minuta a partir de `dados_do_ciclo` e devolve o .docx em bytes."""
    doc = Document(str(_MODELOS / "modelo_nota_tecnica.docx"))
    ma, mp = d["meses_apurados"], d["meses_pr"]
    pr, pv, sr, scg = d["pr"], d["pv"], d["sr"], d["scg"]
    ano_pr = _idx(mp[0])[1]
    pr_txt, scg_selic, sr_total = pr["pr"], pr["scg_selic"], pr["sr"]

    # Capa
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(_MODELOS / "logo_arpe.png"), width=Cm(6))
    for _ in range(3):
        doc.add_paragraph()
    _par(doc, ("negrito", "NOTA TÉCNICA CTEEF No "), ("manual", "[XX]"), ("negrito", f"/{ano_pr}"),
         alinhar=WD_ALIGN_PARAGRAPH.CENTER)
    _par(doc, ("negrito", "PROCESSO SEI No "), ("manual", "[informar]"), alinhar=WD_ALIGN_PARAGRAPH.CENTER)
    for _ in range(3):
        doc.add_paragraph()
    _par(doc, ("negrito", "REPASSE DO CUSTO DO GÁS NATURAL E\nAPLICAÇÃO DO MECANISMO DA CONTA GRÁFICA"),
         alinhar=WD_ALIGN_PARAGRAPH.CENTER)
    _par(doc, ("negrito", f"{mes_ano(mp[0]).upper()} – {mes_ano(mp[-1]).upper()}"), alinhar=WD_ALIGN_PARAGRAPH.CENTER)
    for _ in range(6):
        doc.add_paragraph()
    i_cap, a_cap = _idx(_desloca(mp[0], -1))
    _par(doc, f"Recife, {_NOMES[i_cap]} de {a_cap}", alinhar=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # 1. Objetivo
    _titulo(doc, "Objetivo", 0)
    _par(doc, "Esta Nota Técnica tem por objetivo registrar a análise dos pleitos apresentados pela Companhia "
              f"Pernambucana de Gás S.A. (COPERGÁS), com vigência para o período de {por_extenso(mp)}, "
              "referentes aos seguintes itens:")
    _par(doc, "Repasse do Preço Médio Ponderado de aquisição do Gás para compor o valor da Tarifa Média "
              "Operacional (Mercado Cativo);", estilo="List Paragraph")
    _par(doc, f"Resultado da Aplicação do Mecanismo da Conta Gráfica, apurado no período de {por_extenso(ma)}; e",
         estilo="List Paragraph")
    _par(doc, ("manual", "[Incluir os demais itens do pleito, se houver (Tarifa Verde, Tabela Tarifária, Mercado Livre).]"),
         estilo="List Paragraph")
    _par(doc, "Registra-se que para o Repasse do Preço Médio Ponderado de aquisição do Gás, é aplicada a metodologia "
              "prevista no Anexo Único do Decreto Estadual nº 49.226 de 27 de julho de 2020, e que para a aplicação "
              "do mecanismo da Conta Gráfica foram observadas as disposições da Resolução ARPE nº 304, de 25 de "
              "agosto de 2025, que regulamenta o mecanismo da Conta Gráfica instituído pela Lei nº 17.641, de 5 de "
              "janeiro de 2022 e acrescido à Lei 15.900, de 11 de outubro de 2016, aplicável às tarifas dos serviços "
              "de distribuição de gás canalizado do mercado cativo no Estado de Pernambuco.")

    # 2. Pleito
    _titulo(doc, "Pleito Copergás", 0)
    _manual(doc, "Descrever o pleito: carta CT. COPERGÁS/PRE nº, data, Nota Técnica Copergás nº e documentos SEI; "
                 "supridores e comunicações de preço e volume do trimestre.")
    _par(doc, "Para a Tarifa Média Operacional (Mercado Cativo), registra o Preço Médio Ponderado de Venda do gás "
              f"(PMPV) no valor de R$ {_num(pv['pmpv'], 4)}/m³, o valor da Parcela de Recuperação (PR) referente ao "
              f"período de {faixa(ma)} no valor de {com_sinal(pr_txt, 4, '/m³')}, que resulta no Preço de Venda "
              f"(PV) no valor de R$ {_num(pv['pv'], 4)}/m³.")
    _manual(doc, "Conferir com os valores do pleito da Copergás.")

    # 3. Legislação
    _titulo(doc, "Legislação Básica e Outros Dispositivos Regulamentares", 0)
    _manual(doc, "Copiar da NT anterior e atualizar: Lei nº 15.900/2016, Lei nº 17.641/2022, Decreto nº 49.226/2020, "
                 "Resolução ARPE nº 304/2025 e demais resoluções aplicáveis.")

    # 4. Análise
    _titulo(doc, "Análise da ARPE", 0)
    _titulo(doc, "Análise Preliminar", 1)
    _manual(doc, "Registrar a análise preliminar dos dados do pleito (divergências, variações relevantes de QDC "
                 "ou de preço por supridor).")

    _titulo(doc, "Preço Médio Ponderado de Venda", 1)
    _manual(doc, "Quadros 1 a 4 (preço e volume contratado por supridor e cálculo do PMPV): incluir a partir da "
                 "sessão de PMPV do trimestre.")
    _par(doc, f"Considerando os novos preços do gás a serem aplicados pelos supridores da Copergás no período de "
              f"{por_extenso(mp)}, a ARPE confirmou o Preço Médio Ponderado de Venda de R$ {_num(pv['pmpv'], 4)}/m³ "
              "para o período (", ("sigla", "PMPV", faixa(mp)), ").")
    if d.get("pv_anterior") and d["pv_anterior"]["pmpv"]:
        ant = d["pv_anterior"]["pmpv"]
        var = pv["pmpv"] / ant - 1
        _par(doc, f"Constata-se, portanto, {'um aumento' if var >= 0 else 'uma redução'} de "
                  f"{_num(abs(var) * 100)}% entre o Preço Médio Ponderado de Venda atual R$ {_num(ant, 4)}/m³ "
                  f"(período de {por_extenso(d['meses_pr_anterior'])}), e o Preço Médio Ponderado de Venda que "
                  f"vigorará no período de {por_extenso(mp)}, no valor de R$ {_num(pv['pmpv'], 4)}/m³.")

    _titulo(doc, "Aplicação do Mecanismo da Conta Gráfica", 1)
    _par(doc, "A Resolução ARPE nº 304, de 25 de agosto de 2025, revogou a Resolução ARPE nº 216, de 13 de julho de "
              "2022, e passou a regulamentar o mecanismo de Conta Gráfica instituído pela Lei nº 17.641, de 5 de "
              "janeiro de 2022, para apuração e recuperação dos saldos de variação do custo do gás.")
    _par(doc, f"A Parcela de Recuperação a ser aplicada no período de {por_extenso(mp)} (",
         ("sigla", "PR", faixa(mp)), ") será composta pelas seguintes parcelas:")
    _par(doc, "Saldo da Conta Gráfica (", ("sigla", "SCG", faixa(ma)), f"), apurado no período de {por_extenso(ma)};",
         estilo="List Paragraph")
    _par(doc, "Saldo Remanescente (", ("sigla", "SR", faixa(ma)), f"), apurado no período de {por_extenso(ma)}.",
         estilo="List Paragraph")

    # 4.3-1 SCG
    _titulo(doc, "Saldo da Conta Gráfica", 2)
    _par(doc, f"O Saldo da Conta Gráfica apurado no período de {por_extenso(ma)} (", ("sigla", "SCG", faixa(ma)),
         "), que é composto pelo somatório das parcelas de Recuperação de Preço de Venda (RPV), Recuperação de "
         "Encargos de Transporte (RET) e Recuperação das Penalidades (RP), conforme Quadro 5 e Anexo A, resultou no "
         f"valor {'positivo' if scg_selic >= 0 else 'negativo'} de {brl(abs(scg_selic))} a ser "
         f"{'acrescido à' if scg_selic >= 0 else 'deduzido da'} tarifa cobrada aos usuários da Copergás, já incluída "
         "a atualização pela variação mensal da taxa de juros do Sistema Especial de Liquidação e Custódia (SELIC) "
         "nos termos do §5º do artigo 11 da Resolução ARPE nº 304/2025.")
    _citacao(doc, "Art. 11", "[...]", "§ 5º Os valores apurados mensalmente no Saldo da Conta Gráfica (SCG) e no Saldo "
             "Remanescente (SR) serão atualizados pela variação mensal da taxa de juros do Sistema Especial de "
             "Liquidação e Custódia (SELIC), até o último dia do mês anterior ao que se processa a recomposição tarifária.")
    _legenda(doc, f"Quadro 5 – Apuração do Saldo da Conta Gráfica – {mes_ano(ma[0])}-{mes_ano(ma[-1])}")
    sel = {m["periodo"]: m["selic"] for m in pr["meses"]}
    linhas = []
    for rot, k in (("RPV", "rpv"), ("RET", "ret"), ("RP", "rp"), ("SCG", "scg")):
        vs = [scg[m].get(k, 0.0) for m in ma]
        linhas.append([rot, "R$"] + [_num(v) for v in vs] + [_num(sum(vs))])
    linhas.append(["Variação (SELIC)", "%"] + [f"{_num(sel.get(m, 0.0), 6)}%" for m in ma] + ["–"])
    com = [m["scg_selic"] for m in pr["meses"]]
    linhas.append(["SCG-(SELIC)", "R$"] + [_num(v) for v in com] + [_num(sum(com))])
    _tabela(doc, ["DADOS", "UNIDADE"] + [curto(m) for m in ma] + ["TOTAL"], linhas, destaque={3, 5},
            larguras=[3.2, 1.8, 2.8, 2.8, 2.8, 3])

    # 4.3-2 SR
    _titulo(doc, "Saldo Remanescente", 2)
    _par(doc, "Para a aplicação do mecanismo da Conta Gráfica, faz-se necessário verificar o Saldo Remanescente, "
              "conforme previsto nos §4º e §5º do artigo 11 da Resolução ARPE nº 304/2025.")
    _citacao(doc, "Art. 11", "[...]", "§ 4º Serão calculados mensalmente os Saldos Remanescentes das parcelas de "
             "recuperação aplicadas, obtidos pela diferença entre o Volume Prospectivo (VP) utilizado na Parcela de "
             "Recuperação (PR) e o Volume Faturado (VF) do mês apurado, multiplicada pela respectiva PR.")
    _par(doc, "O Saldo Remanescente é apurado mensalmente da seguinte forma: SR = (VP − VF) × PR, onde VP = Volume "
              "Prospectivo; VF = Volume Faturado e PR = Parcela de Recuperação.")
    grupos: dict[tuple, list[str]] = {}
    for m in ma:
        grupos.setdefault(tuple(trimestre_pr_do_mes(m)), []).append(m)
    itens = [f"saldo remanescente de {' e de '.join(mes_ano(m) for m in ms)} referente a PR{faixa(list(t))}"
             for t, ms in grupos.items()]
    _par(doc, f"Ressalta-se que no período de {mes_ano(ma[0])} a {mes_ano(ma[-1])} foram apurados: "
              + "; e, ".join(itens) + ".")
    _par(doc, "Assim, o Saldo Remanescente (", ("sigla", "SR", faixa(ma)), ") que integra a Parcela de Recuperação a "
              f"ser aplicada no período de {por_extenso(mp)}, resultou no valor de {com_sinal(sr_total)}, já incluída "
              "a atualização pela variação mensal da SELIC nos termos do §5º do artigo 11 da Resolução ARPE nº "
              "304/2025, conforme demonstrado no Quadro 6, a seguir.")
    _legenda(doc, f"Quadro 6 – Apuração do Saldo Remanescente – {faixa(ma)}")
    por_mes = {r["mes"]: r for r in sr}
    v = lambda m, k: float((por_mes.get(m) or {}).get(k) or 0.0)  # noqa: E731
    linhas = [
        ["Volume Prospectivo - (VP)", "m³"] + [_num(v(m, "vp")) for m in ma],
        ["Volume Faturado - (VF)", "m³"] + [_num(v(m, "vf")) for m in ma],
        ["Diferença de Volumes - (VP-VF)", "m³"] + [_num(v(m, "diferenca")) for m in ma],
        ["Parcela de Recuperação do Período", "R$/m³"] + [_num(v(m, "pr"), 4) for m in ma],
        ["Saldo Remanescente", "R$"] + [_num(v(m, "sr_parcela")) for m in ma],
        ["Variação (SELIC)", "%"] + [f"{_num(v(m, 'selic_mensal'), 6)}%" for m in ma],
        ["Saldo Remanescente (SELIC)", "R$"] + [_num(v(m, "sr_selic")) for m in ma],
        ["Total", "R$", "", "", _num(sr_total)],
    ]
    _tabela(doc, ["DESCRIÇÃO", "UNIDADE"] + [curto(m) for m in ma], linhas, destaque={4, 6, 7},
            larguras=[5.6, 1.8, 3, 3, 3])

    # 4.3-3 PR
    _titulo(doc, "Resultado da Parcela de Recuperação", 2)
    _par(doc, f"Por fim, o Quadro 7, a seguir, apresenta o cálculo da Parcela de Recuperação a ser aplicada no período "
              f"de {por_extenso(mp)} (", ("sigla", "PR", faixa(mp)), f"), que resultou no valor "
              f"{'positivo' if pr_txt >= 0 else 'negativo'} de {com_sinal(pr_txt, 4, '/m³')}.")
    _legenda(doc, f"Quadro 7 – Parcela de Recuperação de {mes_ano(mp[0])}-{mes_ano(mp[-1])} (PR{faixa(mp)})")
    _tabela(doc, ["DESCRIÇÃO", "VALOR"], [
        ["Saldo da Conta Gráfica - SCG (com variação SELIC)", brl(scg_selic)],
        ["Saldo Remanescente - SR (com variação SELIC)", brl(sr_total)],
        ["Saldo Total a Recuperar", brl(pr["saldo_total"])],
        [f"VP - Volume Prospectivo Contratado {faixa(mp)}", f"{_num(pr['vp'], 0)} m³"],
        [f"Parcela de Recuperação (PR{faixa(mp)}) R$/m³", _num(pr_txt, 4)],
    ], destaque={2, 4}, larguras=[11, 5])

    # 4.4 PV
    _titulo(doc, "Cálculo do Preço de Venda", 1)
    _par(doc, "O Preço de Venda (PV) é obtido pela soma do Preço Médio Ponderado de Venda (PMPV) com a Parcela de "
              f"Recuperação (PR), resultando no valor de R$ {_num(pv['pv'], 4)}/m³ para o período de {por_extenso(mp)}, "
              "conforme Quadro 8.")
    _legenda(doc, f"Quadro 8 – Cálculo do Preço de Venda (PV) – {mes_ano(mp[0])}-{mes_ano(mp[-1])}")
    _tabela(doc, ["DESCRIÇÃO", "VALOR (R$/m³)"], [
        [f"PMPV{faixa(mp)}", _num(pv["pmpv"], 4)],
        [f"PR{faixa(mp)}", _num(pv["pr"], 4)],
        [f"PV{faixa(mp)} = PMPV + PR", _num(pv["pv"], 4)],
    ], destaque={2}, larguras=[11, 5])

    _titulo(doc, "Impacto do Repasse do Preço do GN e da aplicação do mecanismo da conta gráfica na Tarifa Média "
                 "Operacional", 1)
    _manual(doc, "Quadro 9 – Impacto na Tarifa Média (PMPV, PR, PV, Margem Regulatória e Tarifa Média, trimestre "
                 "atual × anterior) e impacto por supridor.")

    # 5. Considerações finais
    _titulo(doc, "Considerações Finais", 0)
    _par(doc, f"Diante do exposto, para o período de {por_extenso(mp)}, a CTEEF apurou o Preço Médio Ponderado de Venda "
              f"de R$ {_num(pv['pmpv'], 4)}/m³, a Parcela de Recuperação de {com_sinal(pr_txt, 4, '/m³')} e o Preço "
              f"de Venda de R$ {_num(pv['pv'], 4)}/m³.")
    _manual(doc, "Registrar as recomendações e o encaminhamento da Nota Técnica.")
    if pr.get("pendencias") or (pv.get("avisos")):
        _manual(doc, "Pendências do sistema ao gerar esta minuta: " + " ".join(pr.get("pendencias", []) + pv.get("avisos", [])))

    # Anexo A
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    _par(doc, ("negrito", f"ANEXO A – Apuração Mensal do Saldo da Conta Gráfica – {mes_ano(ma[0]).capitalize()} – "
                          f"{mes_ano(ma[-1]).capitalize()}"), alinhar=WD_ALIGN_PARAGRAPH.CENTER)
    linhas = []
    for rot, un, k, casas in (("PMPV", "R$/m³", "pmpv", 4), ("VF", "m³", "vf", 2), ("CGR", "R$", "cgr", 2),
                              ("CGF", "R$", "cgf", 2), ("RPV", "R$", "rpv", 2), ("RET", "R$", "ret", 2),
                              ("RP", "R$", "rp", 2), ("SCG", "R$", "scg", 2)):
        linhas.append([rot, un] + [_num(scg[m].get(k, 0.0), casas) for m in ma])
    _tabela(doc, ["DADOS", "UNIDADE"] + [curto(m) for m in ma], linhas, destaque={7},
            larguras=[3.2, 1.8, 3.5, 3.5, 3.5])

    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def dados_do_ciclo(meses_apurados: list[str]) -> dict:
    """Busca nos serviços tudo o que a minuta usa para o trimestre civil apurado."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_pr import ServicosPR
    from Src.Services.servicos_pv import ServicosPV
    from Src.common.periodos import TRIMESTRES_FISCAIS_ABREVS

    mp = meses_do_pr(meses_apurados)
    mp_ant = [_desloca(m, -3) for m in mp]

    def label(meses):
        return next(lb for lb, ms in TRIMESTRES_FISCAIS_ABREVS if ms[0] == meses[0].split("/")[0])

    with DatabasePMPV() as db:
        scg = {}
        for m in meses_apurados:
            cons = db.buscar_consolidacao(m) or {}
            cgf = db.buscar_cgf_resumo(m) or {}
            scg[m] = {**{k: float(cons.get(k) or 0.0) for k in ("cgr", "cgf", "rpv", "ret", "rp", "scg")},
                      "vf": float(cgf.get("volume_final") or 0.0),
                      "pmpv": float(db.buscar_pmpv_mensal(m) or 0.0)}
        sr = db.buscar_sr_trimestre(f"{meses_apurados[0]}_{meses_apurados[-1]}") or []

    servico = ServicosPR()
    try:
        pr = servico.apurar_trimestre(mp)
        pv = ServicosPV(servico._repo).buscar_trimestre(label(mp), _idx(mp[0])[1])
        pv_ant = ServicosPV(servico._repo).buscar_trimestre(label(mp_ant), _idx(mp_ant[0])[1])
    finally:
        servico._repo.fechar()
    # A NT usa o PR apurado neste ciclo, não o que estiver salvo no módulo PR.
    avisos = [a for a in pv.get("avisos", []) if "PR de" not in a]
    if abs(pv["pr"] - pr["pr"]) > 1e-9:
        avisos.append(f"O PR salvo no módulo PR ({_num(pv['pr'], 4)}) difere do apurado ({_num(pr['pr'], 4)}); "
                      "a minuta usa o apurado — salve o PR na plataforma.")
    pv = {"pmpv": pv["pmpv"], "pr": pr["pr"], "pv": round(pv["pmpv"] + pr["pr"], 4), "avisos": avisos}
    return {"meses_apurados": meses_apurados, "meses_pr": mp, "meses_pr_anterior": mp_ant,
            "scg": scg, "sr": sr, "pr": pr, "pv": pv, "pv_anterior": pv_ant}
