"""Relatório trimestral da Conta Gráfica em Word (.docx).

Gerado pelo sistema no fim do ciclo, só com o que as provas reais já sabem:
veredito ("está tudo batendo?"), resultado de cada mês (CGR, CGF, RPV, RET,
RP, SCG), quadro de conferência colorido, a Auditoria do CGR aberta por
empresa e cada incongruência com o que fazer. Não grava nada no banco.

`dados_do_trimestre` lê (provas reais), `achados` interpreta (texto das
incongruências) e `montar` escreve o Word. As três são separadas para testar
sem banco.

O SCG de cada mês é sempre a conta refeita com os valores do fechamento
(RPV + RET + RP), a mesma que as telas mostram. A coluna `scg` crua do banco só
serve para avisar quando está ausente ou diferente.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from Src.infrastructure.exporters.nota_tecnica import brl, curto, mes_ano

_COMPONENTES = [("cgr", "CGR · custo do gás realizado"), ("cgf", "CGF · custo do gás faturado"),
                ("rpv", "RPV · CGR menos CGF"), ("ret", "RET · encargos de transporte"),
                ("rp", "RP · saldo de penalidades"), ("scg", "SCG · saldo da conta gráfica")]
_MODULOS = [("cgr", "CGR (Auditoria)", "valor_das_notas", "as notas"),
            ("cgf", "CGF", "valor_calculado", "o resumo de volumes"),
            ("ret", "RET", "valor_calculado", "os documentos"),
            ("rp", "RP", "valor_calculado", "as notas")]
_ACAO_MODULO = {
    "cgr": "Abrir a Prova real da Auditoria do mês e ver por empresa onde a soma das notas difere do gravado.",
    "cgf": "Abrir a Prova real do CGF e reprocessar o mês com o resumo de volumes completo.",
    "ret": "Abrir a Prova real do RET e reprocessar o mês com todos os documentos.",
    "rp": "Abrir a Prova real do RP e reprocessar o mês com todas as notas de penalidade.",
}
TOL = 1.0  # R$: abaixo disso é arredondamento

_LARGURA = 16.6  # cm úteis da página A4 com margens de 2,2 cm
_AZUL, _AZUL_HEX = RGBColor(0x1F, 0x38, 0x64), "1F3864"
_CINZA_TEXTO = RGBColor(0x59, 0x59, 0x59)
# tom → (fundo, cor do texto)
_TONS = {
    "ok": ("E2F0D9", "375623"),
    "erro": ("FBE4E4", "C00000"),
    "atencao": ("FFF2CC", "7F6000"),
    "neutro": ("F2F2F2", "595959"),
    "info": ("DEEAF6", "1F3864"),
}


# ── Leitura ───────────────────────────────────────────────────────────────────

def dados_do_trimestre(meses: list[str], planilha: str | None = None) -> dict:
    """Provas reais dos meses (nada é gravado). A de cada mês traz os valores
    gravados, se cada parte (CGR, CGF, RET, RP) confere com as suas notas e a
    prova real da Auditoria inteira (CGR por empresa).

    Com `planilha` (caminho da planilha da Conta Gráfica), as notas gravadas de
    cada mês também são comparadas com ela, pelo mesmo comparador da Auditoria."""
    from Src.Services import servicos_auditoria_lote
    from Src.Services.servicos_scg import ServicosSCG

    scg = ServicosSCG()
    lista = []
    for m in meses:
        prova = scg.prova_real(m)
        aud = servicos_auditoria_lote.prova_real(m)
        prova["auditoria"] = aud
        prova["notas_digitadas"] = aud.get("notas_digitadas") or []
        prova["possiveis_duplicatas_valor"] = aud.get("possiveis_duplicatas_valor") or []
        if planilha and prova["gravado"]:
            prova["planilha"] = servicos_auditoria_lote.comparar_gravado_com_planilha(m, planilha)
        lista.append(prova)
    return {"meses": meses, "provas": lista, "com_planilha": bool(planilha)}


# ── Interpretação ─────────────────────────────────────────────────────────────

def _scg_do_mes(p: dict) -> float:
    """SCG do mês pela conta refeita com os valores do fechamento (o que as telas mostram)."""
    if p.get("scg_calculado") is not None:
        return float(p["scg_calculado"])
    return (p["cgr"] - p["cgf"]) + p["ret"] + p["rp"]


def _tem(o: dict) -> bool:
    return bool(o.get("tem_itens", o.get("tem_resumo")))


def _estado(p: dict, chave: str) -> str:
    """"ok", "erro" ou "sem" (sem notas para provar) de uma parte do mês."""
    o = p["origens"][chave]
    if not _tem(o):
        return "sem"
    return "ok" if o["confere"] else "erro"


def _estado_planilha(pl: dict | None) -> str:
    """"ok", "erro", "sem_mes", "falhou" ou "" (sem planilha) da comparação do mês com a planilha."""
    if not pl:
        return ""
    if pl.get("erro"):
        return "falhou"
    if not pl.get("tem_mes"):
        return "sem_mes"
    cgr = pl.get("cgr_notas")
    total_difere = cgr is not None and any(abs(cgr - f["valor"]) > TOL for f in pl.get("fontes_cgr") or [])
    problemas = (pl.get("so_na_planilha") or pl.get("so_gravadas")
                 or any(abs(x.get("diferenca_cgr") or 0) > TOL for x in pl.get("divergencias") or [])
                 or any(not s["confere"] for s in pl.get("supridores") or []))
    return "erro" if total_difere or problemas else "ok"


def _achados_planilha(m: str, pl: dict, add) -> None:
    if pl.get("erro"):
        add(m, "Planilha", "atencao", pl["erro"], "Conferir se a planilha é a da Conta Gráfica (.xlsx, sem senha).")
        return
    if not pl.get("tem_mes"):
        add(m, "Planilha", "atencao", "A planilha escolhida não tem este mês, então ele não foi comparado.",
            "Gerar de novo com a planilha que tem este mês.")
        return
    cgr = pl.get("cgr_notas")
    for f in pl.get("fontes_cgr") or []:
        dif = (cgr or 0.0) - f["valor"]
        if cgr is not None and abs(dif) > TOL:
            lado = "a menos" if dif < 0 else "a mais"
            add(m, "Planilha", "alta",
                f"O CGR das notas gravadas ({brl(cgr)}) difere da planilha · {f['rotulo']} ({brl(f['valor'])}): "
                f"{brl(abs(dif))} {lado} no sistema.",
                "Ver as notas abaixo (só na planilha, só no sistema, valor diferente): elas explicam a diferença.")
    for n in pl.get("so_na_planilha") or []:
        linha = f"linha {n['linha_excel']}, " if n.get("linha_excel") else ""
        valor = f"CGR {brl(n['cgr_planilha'])}" if n.get("cgr_planilha") is not None else "sem CGR"
        add(m, "Planilha", "alta",
            f"A nota {n['numero']} de {n['empresa']} está na planilha ({linha}{valor}) e não está gravada no sistema.",
            "Se o fornecedor não mandou a nota, usar “Incluir esta nota” no Comparar com a planilha do Painel.")
    for n in pl.get("so_gravadas") or []:
        valor = f" ({brl(n['cgr_liquido'])})" if n.get("cgr_liquido") is not None else ""
        add(m, "Planilha", "alta",
            f"A nota {n['tipo']} {n['numero']} de {n['empresa']}{valor} está gravada no sistema e não está na planilha.",
            "Confirmar se a nota é deste mês. Se for, avisar quem mantém a planilha; se não, tirar do cálculo.")
    for x in pl.get("divergencias") or []:
        dif = x.get("diferenca_cgr") or 0.0
        linha = f" (linha {x['linha_excel']})" if x.get("linha_excel") else ""
        motivo = ", ".join(x.get("motivos") or []) or "valores"
        texto = f"A nota {x['numero']} de {x['empresa']}{linha} difere da planilha em: {motivo}."
        if x.get("explicacao"):
            texto += f" {x['explicacao']}"
        if abs(dif) > TOL:
            add(m, "Planilha", "alta", texto + f" Diferença no CGR: {brl(dif)}.",
                "Abrir o documento e ver qual valor está certo; corrigir a nota ou a planilha.")
        else:
            add(m, "Planilha", "atencao", texto + " O CGR é igual: não muda o total.",
                "Só conferir. Se a planilha estiver errada, corrigir lá.")
    for s in pl.get("supridores") or []:
        if not s["confere"]:
            add(m, "Planilha", "alta",
                f"O total de {s['empresa']} no sistema difere da planilha em {brl(s.get('diferenca') or 0.0)}.",
                "Abrir o Comparar com a planilha do mês e ver as notas desse supridor.")


def achados(d: dict) -> list[dict]:
    """Incongruências do trimestre em texto: {mes, modulo, gravidade, texto, acao}.

    Gravidade: "alta" = a conta não fecha; "atencao" = não dá para provar ou
    há algo a conferir; "info" = registro (ex.: nota digitada à mão)."""
    saida: list[dict] = []

    def add(mes, modulo, gravidade, texto, acao):
        saida.append({"mes": mes, "modulo": modulo, "gravidade": gravidade, "texto": texto, "acao": acao})

    for p in d["provas"]:
        m = p["periodo"]
        if not p["gravado"]:
            add(m, "Fechamento", "alta", "O mês não tem fechamento gravado: sem CGR, CGF, RET, RP e SCG.",
                "Processar o mês no Painel do Ciclo e gravar depois de conferir a prévia.")
            continue
        scg = _scg_do_mes(p)
        if p.get("scg_gravado") is None:
            add(m, "SCG", "atencao",
                f"O SCG do mês não está gravado no banco. Este relatório usou a conta refeita "
                f"(RPV + RET + RP) = {brl(scg)}.",
                "Abrir a tela SCG do mês e salvar, para gravar o valor.")
        else:
            dif = p.get("diferenca")
            if dif is not None and abs(dif) > TOL:
                add(m, "SCG", "alta",
                    f"O SCG gravado ({brl(p['scg_gravado'])}) difere da conta refeita com os valores do mês "
                    f"({brl(scg)}): diferença de {brl(dif)}. O relatório usa {brl(scg)}.",
                    "Abrir a tela SCG e salvar de novo para regravar o SCG com os valores atuais.")
        for chave, nome, campo, fonte in _MODULOS:
            o = p["origens"][chave]
            if not _tem(o):
                add(m, nome, "atencao",
                    f"Sem {fonte.split(' ', 1)[1]} gravados: o valor de {brl(p[chave])} não pôde ser provado "
                    "(foi gravado só com o total ou veio de outra fonte).",
                    "Reprocessar o mês pela pasta para gravar os itens, ou registrar de onde veio o total.")
            elif not o["confere"]:
                calc = o.get(campo)
                gravado = p[chave]
                if calc is not None:
                    dif_m = calc - gravado
                    lado = "a mais" if dif_m > 0 else "a menos"
                    texto = (f"Refeita com {fonte}, a conta dá {brl(calc)}, e o valor gravado é {brl(gravado)}: "
                             f"{brl(abs(dif_m))} {lado} nas notas. Diferença: {brl(dif_m)}.")
                else:
                    texto = f"A conta refeita com {fonte} não fecha com o valor gravado ({brl(gravado)})."
                add(m, nome, "alta", texto + " Causa provável: arquivos incompletos ou mês regravado com regra antiga.",
                    _ACAO_MODULO[chave])
        for dup in p.get("possiveis_duplicatas_valor") or []:
            notas = ", ".join(dup.get("notas") or [])
            add(m, "CGR (Auditoria)", "atencao",
                f"Possível duplicata em {dup['grupo']}: {dup['qtd']} notas com o mesmo valor de {brl(dup['valor'])}"
                + (f" ({notas})." if notas else "."),
                "Abrir os documentos. Se for cópia, usar “Tirar do cálculo” na Auditoria; se forem notas diferentes, nada a fazer.")
        for n in p.get("notas_digitadas") or []:
            add(m, "CGR (Auditoria)", "info",
                f"Nota {n['tipo']} {n['numero']} de {n['empresa']} ({brl(n['cgr_liquido'])}) foi incluída à mão "
                f"porque não veio nos arquivos. Motivo: {n['motivo'] or '(não informado)'}.",
                "Guardar o comprovante. Se o mês for reprocessado pela pasta, incluir a nota de novo.")
        if p.get("planilha"):
            _achados_planilha(m, p["planilha"], add)
    return saida


# ── Word: peças ───────────────────────────────────────────────────────────────

_ORDEM_TBLPR = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize",
                "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook"]


def _inserir_tblpr(tblPr, el, nome: str) -> None:
    """Põe `el` no tblPr na ordem do esquema (o Word recusa fora de ordem)."""
    depois = set(_ORDEM_TBLPR[_ORDEM_TBLPR.index(nome) + 1:])
    for filho in list(tblPr):
        if filho.tag.split("}")[-1] in depois:
            filho.addprevious(el)
            return
    tblPr.append(el)


def _bordas(t, cor: str = "BFBFBF", esquerda: tuple[str, int] | None = None, sem: bool = False) -> None:
    b = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        if lado == "left" and esquerda:
            e.set(qn("w:val"), "single"), e.set(qn("w:sz"), str(esquerda[1])), e.set(qn("w:color"), esquerda[0])
        elif sem:
            e.set(qn("w:val"), "nil")
        else:
            e.set(qn("w:val"), "single"), e.set(qn("w:sz"), "4"), e.set(qn("w:color"), cor)
        e.set(qn("w:space"), "0")
        b.append(e)
    _inserir_tblpr(t._tbl.tblPr, b, "tblBorders")


def _margens(t, vert: int = 50, horiz: int = 100) -> None:
    mar = OxmlElement("w:tblCellMar")
    for lado, v in (("top", vert), ("left", horiz), ("bottom", vert), ("right", horiz)):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:w"), str(v)), e.set(qn("w:type"), "dxa")
        mar.append(e)
    _inserir_tblpr(t._tbl.tblPr, mar, "tblCellMar")


def _sombra(celula, cor: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"), shd.set(qn("w:color"), "auto"), shd.set(qn("w:fill"), cor)
    tcPr = celula._tc.get_or_add_tcPr()
    va = tcPr.find(qn("w:vAlign"))
    if va is not None:
        va.addprevious(shd)
    else:
        tcPr.append(shd)


def _repetir_cabecalho(linha) -> None:
    h = OxmlElement("w:tblHeader")
    h.set(qn("w:val"), "true")
    linha._tr.get_or_add_trPr().append(h)


def _nova_tabela(doc, linhas: int, larguras: list[float]):
    t = doc.add_table(rows=linhas, cols=len(larguras))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for col, w in zip(t._tbl.tblGrid.gridCol_lst, larguras):
        col.w = Cm(w)
    for row in t.rows:
        for c, w in zip(row.cells, larguras):
            c.width = Cm(w)
    return t


def _escrever(c, texto: str, *, tam: float = 9, negrito: bool = False, cor: RGBColor | None = None,
              alinha=WD_ALIGN_PARAGRAPH.LEFT, novo: bool = False):
    p = c.add_paragraph() if novo else c.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.alignment = alinha
    r = p.add_run(texto)
    r.font.size, r.bold = Pt(tam), negrito
    if cor is not None:
        r.font.color.rgb = cor
    return p


def _tabela(doc, cabecalho: list[str], linhas: list[list], larguras: list[float], *,
            direita: set[int] = frozenset(), centro: set[int] = frozenset(),
            destaque: set[int] = frozenset()) -> None:
    """Tabela com cabeçalho azul. Cada célula é texto ou (texto, tom) — o tom pinta a célula."""
    t = _nova_tabela(doc, 1 + len(linhas), larguras)
    _bordas(t)
    _margens(t)
    _repetir_cabecalho(t.rows[0])
    for i, linha in enumerate([cabecalho] + linhas):
        for j, cel in enumerate(linha):
            texto, tom = cel if isinstance(cel, tuple) else (cel, None)
            c = t.cell(i, j)
            if i == 0:
                _sombra(c, _AZUL_HEX)
                alinha = (WD_ALIGN_PARAGRAPH.RIGHT if j in direita else
                          WD_ALIGN_PARAGRAPH.CENTER if j in centro else WD_ALIGN_PARAGRAPH.LEFT)
                _escrever(c, texto, negrito=True, cor=RGBColor(0xFF, 0xFF, 0xFF), alinha=alinha)
            else:
                alinha = (WD_ALIGN_PARAGRAPH.RIGHT if j in direita else
                          WD_ALIGN_PARAGRAPH.CENTER if (j in centro or tom) else WD_ALIGN_PARAGRAPH.LEFT)
                negrito, cor = (i - 1) in destaque, None
                if tom:
                    fundo, hexcor = _TONS[tom]
                    _sombra(c, fundo)
                    negrito, cor = True, RGBColor.from_string(hexcor)
                elif (i - 1) in destaque:
                    _sombra(c, "D9E2F3")
                _escrever(c, texto, negrito=negrito, cor=cor, alinha=alinha)
            c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    _espaco(doc)


def _espaco(doc, pts: float = 4) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.add_run().font.size = Pt(pts)


def _caixa(doc, titulo: str, linhas: list[str], tom: str) -> None:
    """Caixa de destaque: fundo claro e barra grossa à esquerda na cor do tom."""
    fundo, hexcor = _TONS[tom]
    t = _nova_tabela(doc, 1, [_LARGURA])
    _bordas(t, sem=True, esquerda=(hexcor, 36))
    _margens(t, vert=110, horiz=180)
    c = t.cell(0, 0)
    _sombra(c, fundo)
    _escrever(c, titulo, tam=13, negrito=True, cor=RGBColor.from_string(hexcor))
    for linha in linhas:
        p = _escrever(c, linha, tam=10, cor=RGBColor(0x26, 0x26, 0x26), novo=True)
        p.paragraph_format.space_before = Pt(3)
    _espaco(doc, 8)


def _cartoes(doc, itens: list[tuple[str, str, str]]) -> None:
    """Linha de cartões (valor grande + rótulo): [(valor, rótulo, tom)]."""
    larg = _LARGURA / len(itens)
    t = _nova_tabela(doc, 1, [larg] * len(itens))
    _bordas(t, cor="FFFFFF")
    _margens(t, vert=90, horiz=80)
    for j, (valor, rotulo, tom) in enumerate(itens):
        fundo, hexcor = _TONS[tom]
        c = t.cell(0, j)
        _sombra(c, fundo)
        _escrever(c, valor, tam=13, negrito=True, cor=RGBColor.from_string(hexcor), alinha=WD_ALIGN_PARAGRAPH.CENTER)
        _escrever(c, rotulo, tam=8, cor=_CINZA_TEXTO, alinha=WD_ALIGN_PARAGRAPH.CENTER, novo=True)
    _espaco(doc, 8)


def _par(doc, texto: str = "", negrito: bool = False, tamanho: float = 10.5, cor: RGBColor | None = None):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(texto)
    r.bold, r.font.size = negrito, Pt(tamanho)
    if cor is not None:
        r.font.color.rgb = cor
    return p


def _titulo(doc, texto: str, nivel: int = 1) -> None:
    h = doc.add_heading(texto, level=nivel)
    h.paragraph_format.space_before = Pt(14 if nivel == 1 else 8)
    h.paragraph_format.space_after = Pt(6)
    for r in h.runs:
        r.font.color.rgb = _AZUL
        r.font.name = "Calibri"
        r.font.size = Pt(15 if nivel == 1 else 12)


def _rodape(sec, texto: str) -> None:
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{texto} · página ")
    r.font.size, r.font.color.rgb = Pt(8), _CINZA_TEXTO
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    rr = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "16")
    rpr.append(sz)
    rr.append(rpr)
    tx = OxmlElement("w:t")
    tx.text = "1"
    rr.append(tx)
    fld.append(rr)
    p._p.append(fld)


def _v(valor) -> str:
    return brl(valor) if valor is not None else "—"


# ── Word: relatório ───────────────────────────────────────────────────────────

_SELO = {"ok": ("✓ Confere", "ok"), "erro": ("✗ Não confere", "erro"), "sem": ("— Sem notas", "atencao")}


def montar(d: dict) -> bytes:
    """Escreve o relatório; `d` é o resultado de `dados_do_trimestre`."""
    meses, provas = d["meses"], d["provas"]
    ach = achados(d)
    altas = [a for a in ach if a["gravidade"] == "alta"]
    atencao = [a for a in ach if a["gravidade"] == "atencao"]
    registros = [a for a in ach if a["gravidade"] == "info"]
    gravados = [p for p in provas if p["gravado"]]
    total_scg = sum(_scg_do_mes(p) for p in gravados)
    periodo_txt = f"{curto(meses[0])} a {curto(meses[-1])}"

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)
    _rodape(sec, f"Relatório Trimestral da Conta Gráfica · {periodo_txt}")

    # ── Capa ──
    t = doc.add_paragraph()
    t.paragraph_format.space_after = Pt(2)
    r = t.add_run("Relatório Trimestral da Conta Gráfica")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(22), _AZUL
    _par(doc, f"Trimestre {mes_ano(meses[0]).capitalize()} a {mes_ano(meses[-1]).capitalize()}", tamanho=13,
         cor=_CINZA_TEXTO)
    _par(doc, f"Gerado pelo sistema em {datetime.now():%d/%m/%Y às %H:%M}, a partir das provas reais de cada mês. "
              "Nada foi gravado ao gerar este relatório.", tamanho=9, cor=_CINZA_TEXTO)

    # ── Veredito ──
    com_planilha = bool(d.get("com_planilha"))
    sem_planilha = ([] if com_planilha else
                    ["Gerado sem a planilha oficial: o sistema foi conferido com ele mesmo. Nota que falta nos "
                     "arquivos e na planilha não aparece aqui. Para comparar, escolha a planilha no Painel do Ciclo "
                     "antes de gerar."])
    if not gravados:
        _caixa(doc, "Sem dados para conferir", ["Nenhum mês do trimestre tem fechamento gravado."], "neutro")
    elif altas:
        _caixa(doc, f"Não está tudo batendo: {len(altas)} ponto(s) não fecham",
               ["Pelo menos uma conta dá um valor diferente do gravado"
                + (" ou da planilha oficial" if com_planilha else "")
                + ". Veja a seção 6 para cada caso e o que fazer."]
               + ([f"Há também {len(atencao)} ponto(s) para conferir."] if atencao else []) + sem_planilha, "erro")
    elif atencao:
        _caixa(doc, f"As contas fecham, com {len(atencao)} ponto(s) para conferir",
               ["Tudo o que o sistema conseguiu refazer bate, mas há partes que não dá para provar "
                "ou que merecem um olhar (seção 6)."] + sem_planilha, "atencao")
    elif com_planilha:
        _caixa(doc, "Tudo batendo com a planilha oficial",
               [f"As contas de {len(gravados)} mês(es) fecham com as notas gravadas, parte por parte, e as notas "
                "batem com a planilha da Conta Gráfica. Nenhuma incongruência encontrada."], "ok")
    else:
        _caixa(doc, "Tudo batendo no sistema",
               [f"As contas de {len(gravados)} mês(es) fecham com as notas gravadas, parte por parte. "
                "Nenhuma incongruência encontrada."] + sem_planilha, "ok")

    partes = [_estado(p, k) for p in gravados for k in ("cgr", "cgf", "ret", "rp")]
    conferem = sum(1 for e in partes if e == "ok")
    _cartoes(doc, [
        (_v(total_scg) if gravados else "—", "SCG do trimestre", "info"),
        (f"{len(gravados)} de {len(meses)}", "meses com fechamento", "ok" if len(gravados) == len(meses) else "atencao"),
        (f"{conferem} de {len(partes)}" if partes else "—", "partes que conferem",
         "ok" if partes and conferem == len(partes) else ("erro" if any(e == "erro" for e in partes) else "atencao")),
        (str(len(altas) + len(atencao)), "pontos a resolver", "erro" if altas else ("atencao" if atencao else "ok")),
    ])

    # ── 1. Resumo ──
    _titulo(doc, "1. Resumo")
    if gravados:
        sentido = ("saldo a devolver na tarifa: faturou-se mais do que o gás custou" if total_scg < 0
                   else "saldo a recuperar na tarifa: o gás custou mais do que foi faturado")
        parcial = "" if len(gravados) == len(meses) else f" (só {len(gravados)} de {len(meses)} meses têm fechamento)"
        _par(doc, f"O SCG do trimestre é de {brl(total_scg)}{parcial}, {sentido}.")
        por_mes = "; ".join(f"{curto(p['periodo'])}: {brl(_scg_do_mes(p))}" for p in gravados)
        _par(doc, f"Mês a mês: {por_mes}.", tamanho=10, cor=_CINZA_TEXTO)
    else:
        _par(doc, "Nenhum mês do trimestre tem fechamento gravado.")

    # ── 2. Resultado ──
    _titulo(doc, "2. Resultado do trimestre")
    linhas = []
    for chave, nome in _COMPONENTES:
        vals = [None if not p["gravado"] else (_scg_do_mes(p) if chave == "scg" else p[chave]) for p in provas]
        linhas.append([nome, *[_v(v) for v in vals], brl(sum(v for v in vals if v is not None))])
    col_mes = (_LARGURA - 5.2 - 3.1) / len(meses)
    _tabela(doc, ["Componente", *[curto(m) for m in meses],
                  "Trimestre" if len(gravados) == len(meses) else "Trimestre (parcial)"],
            linhas, [5.2] + [col_mes] * len(meses) + [3.1],
            direita=set(range(1, len(meses) + 2)), destaque={5})
    _par(doc, "Fórmulas: RPV = CGR − CGF e SCG = RPV + RET + RP. O RP já vem líquido de PIS/COFINS. "
              "O SCG é sempre a conta refeita com os valores do mês, a mesma que as telas mostram.",
         tamanho=9, cor=_CINZA_TEXTO)

    # ── 3. Conferência ──
    _titulo(doc, "3. Está tudo batendo? Conferência mês a mês")
    _par(doc, "Cada parte do fechamento é refeita pelo sistema com o que foi gravado (notas, resumo, documentos) "
              "e comparada com o valor do fechamento.", tamanho=10)
    selo_planilha = {"ok": ("✓ Bate", "ok"), "erro": ("✗ Não bate", "erro"), "sem_mes": ("— Sem o mês", "atencao"),
                     "falhou": ("! Não comparou", "atencao")}
    n_cols = 6 if com_planilha else 5
    linhas = []
    for p in provas:
        nome_mes = mes_ano(p["periodo"]).capitalize()
        if not p["gravado"]:
            linhas.append([nome_mes, *[("— Sem fechamento", "neutro")] * n_cols])
            continue
        selos = [_SELO[_estado(p, k)] for k in ("cgr", "cgf", "ret", "rp")]
        if p.get("scg_gravado") is None:
            scg = ("! SCG não gravado", "atencao")
        elif p.get("confere"):
            scg = ("✓ Fecha", "ok")
        else:
            scg = ("✗ Não fecha", "erro")
        extra = [selo_planilha.get(_estado_planilha(p.get("planilha")), ("—", "neutro"))] if com_planilha else []
        linhas.append([nome_mes, *selos, scg, *extra])
    larg_mes = 2.6 if com_planilha else 3.1
    _tabela(doc, ["Mês", "CGR", "CGF", "RET", "RP", "SCG", *(["Planilha"] if com_planilha else [])], linhas,
            [larg_mes] + [(_LARGURA - larg_mes) / n_cols] * n_cols, centro=set(range(1, n_cols + 1)))
    _par(doc, "✓ Confere: a conta refeita bate com o gravado (até R$ 1,00 de arredondamento). "
              "✗ Não confere: a conta refeita dá outro valor (detalhe na seção 6). "
              "— Sem notas: o mês foi gravado só com o total, então o sistema não consegue abrir a conta."
              + (" Planilha: as notas gravadas comparadas com a planilha oficial (seção 4)." if com_planilha else ""),
         tamanho=9, cor=_CINZA_TEXTO)

    # ── 4. Planilha oficial ──
    _titulo(doc, "4. Comparação com a planilha oficial")
    if not com_planilha:
        _par(doc, "Este relatório foi gerado sem a planilha da Conta Gráfica. As seções acima conferem o sistema "
                  "com ele mesmo: uma nota que não veio nos arquivos fica fora do CGR gravado e também da conta "
                  "refeita, então não aparece como diferença. Para ver isso, escolha a planilha no Painel do Ciclo "
                  "(Comparar com a planilha) e gere o relatório de novo.", tamanho=10)
    else:
        _par(doc, "As notas gravadas de cada mês foram comparadas com a planilha pelo mesmo comparador da tela "
                  "da Auditoria.", tamanho=10)
        for p in provas:
            pl = p.get("planilha")
            _titulo(doc, mes_ano(p["periodo"]).capitalize(), 2)
            if not p["gravado"] or not pl:
                _par(doc, "Sem fechamento gravado.", tamanho=10, cor=_CINZA_TEXTO)
                continue
            if pl.get("erro") or not pl.get("tem_mes"):
                _par(doc, pl.get("erro") or "A planilha escolhida não tem este mês.", tamanho=10, cor=_CINZA_TEXTO)
                continue
            cgr = pl.get("cgr_notas")
            linhas = [["CGR das notas gravadas no sistema", _v(cgr), ""]]
            for f in pl.get("fontes_cgr") or []:
                dif = (cgr or 0.0) - f["valor"]
                linhas.append([f"Planilha · {f['rotulo']}", brl(f["valor"]),
                               (brl(dif), "ok" if abs(dif) <= TOL else "erro")])
            _tabela(doc, ["CGR", "Valor", "Diferença (sistema − planilha)"], linhas, [8.0, 4.0, 4.6],
                    direita={1, 2})
            dif_valor = [x for x in pl.get("divergencias") or []]
            _cartoes(doc, [
                (str(pl.get("qtd_em_ambas") or 0), "notas batem", "ok"),
                (str(len(dif_valor)), "valor diferente", "atencao" if dif_valor else "neutro"),
                (str(len(pl.get("so_gravadas") or [])), "só no sistema", "erro" if pl.get("so_gravadas") else "neutro"),
                (str(len(pl.get("so_na_planilha") or [])), "só na planilha",
                 "erro" if pl.get("so_na_planilha") else "neutro"),
            ])
            if pl.get("modelo_rotulo"):
                _par(doc, f"Planilha lida como: {pl['modelo_rotulo']}. Cada nota diferente está na seção 6.",
                     tamanho=9, cor=_CINZA_TEXTO)

    # ── 5. Auditoria do CGR ──
    _titulo(doc, "5. Auditoria do CGR por mês")
    _par(doc, "O CGR é a soma das NF-e de compra de gás e dos CT-e de gasoduto (TAG, Mastergás), líquidos de "
              "impostos e já descontadas as devoluções. CT-e das outras transportadoras é frete e fica fora.",
         tamanho=10)
    for p in provas:
        _titulo(doc, mes_ano(p["periodo"]).capitalize(), 2)
        aud = p.get("auditoria")
        if not p["gravado"]:
            _par(doc, "Sem fechamento gravado.", tamanho=10, cor=_CINZA_TEXTO)
            continue
        if not aud or not aud.get("qtd_notas"):
            _par(doc, f"Sem notas gravadas: o CGR de {brl(p['cgr'])} foi gravado só com o total, "
                      "então não dá para abrir por empresa.", tamanho=10, cor=_CINZA_TEXTO)
            continue
        dif = aud.get("diferenca")
        tom_dif = "ok" if dif is not None and abs(dif) <= TOL else "erro"
        empresas = aud.get("por_empresa") or []
        qtd_nfe = sum(e.get("qtd_nfe", 0) for e in empresas)
        qtd_cte = sum(e.get("qtd_cte", 0) for e in empresas)
        _tabela(doc, ["Conta do CGR", "Valor"], [
            [f"Notas gravadas ({qtd_nfe} NF-e, {qtd_cte} CT-e)", str(aud["qtd_notas"])],
            ["Compras de gás", brl(aud.get("compras") or 0.0)],
            ["Devoluções", brl(aud.get("devolucoes") or 0.0)],
            ["Frete fora do CGR (não entra na conta)", brl(aud.get("frete_fora_do_cgr") or 0.0)],
            ["CGR refeito pelas notas", brl(aud.get("cgr_das_notas") or 0.0)],
            ["CGR gravado no fechamento", _v(aud.get("cgr_gravado"))],
            ["Diferença (notas − gravado)", (_v(dif), tom_dif)],
        ], [11.6, 5.0], direita={1}, destaque={4})
        if empresas:
            _tabela(doc, ["Empresa", "Notas", "Compras", "Devoluções", "Fora do CGR", "CGR"], [
                [e["empresa"], str(e.get("qtd_nfe", 0) + e.get("qtd_cte", 0)), brl(e.get("compras") or 0.0),
                 brl(e.get("devolucoes") or 0.0), brl(e.get("frete_fora_do_cgr") or 0.0), brl(e.get("cgr") or 0.0)]
                for e in empresas
            ], [4.6, 1.6, 2.8, 2.6, 2.4, 2.6], direita={1, 2, 3, 4, 5})
        extras = []
        if p.get("possiveis_duplicatas_valor"):
            extras.append(f"{len(p['possiveis_duplicatas_valor'])} grupo(s) de possível duplicata")
        if p.get("notas_digitadas"):
            extras.append(f"{len(p['notas_digitadas'])} nota(s) incluída(s) à mão")
        if extras:
            _par(doc, f"Neste mês: {' e '.join(extras)}. Detalhes na seção 6.", tamanho=9.5, cor=_CINZA_TEXTO)

    # ── 6. Incongruências ──
    _titulo(doc, "6. Incongruências e o que fazer")
    if not ach:
        _par(doc, "Nenhuma incongruência encontrada.")
    grupos = [("alta", "Não fecha", "erro", altas), ("atencao", "Para conferir", "atencao", atencao),
              ("info", "Registros", "info", registros)]
    for _g, rotulo, tom, grupo in grupos:
        if not grupo:
            continue
        _titulo(doc, f"{rotulo} ({len(grupo)})", 2)
        _tabela(doc, ["Mês", "Parte", "O que aconteceu", "O que fazer"],
                [[(curto(a["mes"]), tom), a["modulo"], a["texto"], a["acao"]] for a in grupo],
                [1.7, 2.5, 7.4, 5.0])

    # ── 7. Como ler ──
    _titulo(doc, "7. Como ler este relatório")
    _par(doc, "“Confere” quer dizer que a conta fecha com o que está gravado, não que as notas estejam certas. "
              "Se uma nota não veio nos arquivos do mês, o CGR fica abaixo do esperado até ela ser incluída à mão, "
              "o que aparece em “Registros”. Quem pega esse caso é a comparação com a planilha oficial (seção 4).",
         tamanho=10)
    _par(doc, "SCG negativo: o gás custou menos do que foi faturado e o saldo volta ao consumidor na tarifa. "
              "SCG positivo: o gás custou mais e o saldo é recuperado na tarifa (Parcela de Recuperação).",
         tamanho=10)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
