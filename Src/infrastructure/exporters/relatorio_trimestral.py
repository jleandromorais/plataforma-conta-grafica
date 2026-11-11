"""Relatório trimestral da Conta Gráfica em Word (.docx).

Gerado pelo sistema no fim do ciclo, só com o que as provas reais já sabem:
resultado de cada mês (CGR, CGF, RPV, RET, RP, SCG) e o que não confere —
com valores e a causa provável. Não grava nada no banco.

`dados_do_trimestre` lê (provas reais), `achados` interpreta (texto das
incongruências) e `montar` escreve o Word. As três são separadas para testar
sem banco.
"""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from Src.infrastructure.exporters.nota_tecnica import brl, curto, mes_ano

_COMPONENTES = [("cgr", "CGR – custo do gás realizado"), ("cgf", "CGF – custo do gás faturado"),
                ("rpv", "RPV – CGR menos CGF"), ("ret", "RET – encargos de transporte"),
                ("rp", "RP – saldo de penalidades"), ("scg", "SCG – saldo da conta gráfica")]
_MODULOS = [("cgr", "CGR (Auditoria)", "valor_das_notas", "notas"),
            ("cgf", "CGF", "valor_calculado", "resumo de volumes"),
            ("ret", "RET", "valor_calculado", "documentos"),
            ("rp", "RP", "valor_calculado", "notas")]
_AZUL = RGBColor(0x1F, 0x38, 0x64)


# ── Leitura ───────────────────────────────────────────────────────────────────

def dados_do_trimestre(meses: list[str]) -> dict:
    """Provas reais dos meses (nada é gravado). A de cada mês traz os valores
    gravados e se cada parte (CGR, CGF, RET, RP) confere com as suas notas."""
    from Src.Services import servicos_auditoria_lote
    from Src.Services.servicos_scg import ServicosSCG

    scg = ServicosSCG()
    lista = []
    for m in meses:
        prova = scg.prova_real(m)
        aud = servicos_auditoria_lote.prova_real(m)
        prova["notas_digitadas"] = aud.get("notas_digitadas") or []
        prova["possiveis_duplicatas_valor"] = aud.get("possiveis_duplicatas_valor") or []
        prova["cgr_diferenca_notas"] = aud.get("diferenca")
        lista.append(prova)
    return {"meses": meses, "provas": lista}


# ── Interpretação ─────────────────────────────────────────────────────────────

def achados(d: dict) -> list[dict]:
    """Incongruências do trimestre em texto: {mes, modulo, gravidade, texto}.

    Gravidade: "alta" = a conta não fecha; "atencao" = não dá para provar ou
    há algo a conferir; "info" = registro (ex.: nota digitada à mão)."""
    saida: list[dict] = []

    def add(mes, modulo, gravidade, texto):
        saida.append({"mes": mes, "modulo": modulo, "gravidade": gravidade, "texto": texto})

    for p in d["provas"]:
        m = p["periodo"]
        if not p["gravado"]:
            add(m, "Fechamento", "alta", "O mês não tem fechamento gravado: sem CGR, CGF, RET, RP e SCG.")
            continue
        dif = p.get("diferenca")
        if dif is not None and abs(dif) > 1:
            add(m, "SCG", "alta",
                f"O SCG gravado ({brl(p['scg_gravado'])}) difere da conta refeita com os valores do mês "
                f"({brl(p['scg_calculado'])}): {brl(dif)}. O valor pode ter sido alterado fora do sistema.")
        for chave, nome, campo, fonte in _MODULOS:
            o = p["origens"][chave]
            tem = o.get("tem_itens", o.get("tem_resumo"))
            if not tem:
                add(m, nome, "atencao",
                    f"Nada gravado de {fonte}: o valor de {brl(p[chave])} não pôde ser provado pelo sistema "
                    "(foi gravado só com o total ou carregado de outra fonte).")
            elif not o["confere"]:
                calc = o.get(campo)
                gravado = p[chave]
                dif_m = f" Diferença: {brl(calc - gravado)}." if calc is not None else ""
                add(m, nome, "alta",
                    f"Refeita com {fonte}, a conta dá {brl(calc) if calc is not None else '—'} e o valor gravado é {brl(gravado)}.{dif_m} "
                    "Causa provável: arquivos incompletos ou mês regravado com regra antiga.")
        for n in p["notas_digitadas"]:
            add(m, "CGR (Auditoria)", "info",
                f"Nota {n['tipo']} {n['numero']} de {n['empresa']} ({brl(n['cgr_liquido'])}) foi incluída à mão "
                f"porque não veio nos arquivos. Motivo informado: {n['motivo'] or '(não informado)'}.")
        for dup in p["possiveis_duplicatas_valor"]:
            add(m, "CGR (Auditoria)", "atencao",
                f"Possível duplicata no grupo {dup['grupo']}: {dup['qtd']} notas de {brl(dup['valor'])}. Conferir.")
    return saida


# ── Word ──────────────────────────────────────────────────────────────────────

def _sombra(celula, cor: str) -> None:
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), cor)
    celula._tc.get_or_add_tcPr().append(shd)


def _tabela(doc, cabecalho: list[str], linhas: list[list[str]], larguras: list[float],
            destaque: set[int] = frozenset(), alinha_direita: bool = True) -> None:
    t = doc.add_table(rows=1 + len(linhas), cols=len(cabecalho))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for col, w in zip(t._tbl.tblGrid.gridCol_lst, larguras):
        col.w = Cm(w)
    for i, linha in enumerate([cabecalho] + linhas):
        for j, texto in enumerate(linha):
            c = t.cell(i, j)
            c.width = Cm(larguras[j])
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            p.alignment = (WD_ALIGN_PARAGRAPH.RIGHT if alinha_direita and j and i else WD_ALIGN_PARAGRAPH.LEFT)
            r = p.add_run(texto)
            r.font.size = Pt(9)
            r.bold = i == 0 or (i - 1) in destaque
            if i == 0:
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                _sombra(c, "1F3864")
            elif (i - 1) in destaque:
                _sombra(c, "D9D9D9")
    doc.add_paragraph()


def _par(doc, texto: str = "", negrito: bool = False, tamanho: float = 10.5):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(texto)
    r.bold, r.font.size = negrito, Pt(tamanho)
    return p


def _titulo(doc, texto: str, nivel: int = 1) -> None:
    h = doc.add_heading(texto, level=nivel)
    for r in h.runs:
        r.font.color.rgb = _AZUL
        r.font.name = "Calibri"


def montar(d: dict) -> bytes:
    """Escreve o relatório; `d` é o resultado de `dados_do_trimestre`."""
    meses, provas = d["meses"], d["provas"]
    ach = achados(d)
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.left_margin = sec.right_margin = Cm(2.2)
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10.5)

    t = doc.add_paragraph()
    r = t.add_run("Relatório Trimestral da Conta Gráfica")
    r.bold, r.font.size, r.font.color.rgb = True, Pt(22), _AZUL
    _par(doc, f"Trimestre {curto(meses[0])} a {curto(meses[-1])}", tamanho=13)
    _par(doc, "Gerado pelo sistema a partir das provas reais dos meses. Nada foi gravado ao gerar este relatório.",
         tamanho=9)

    gravados = [p for p in provas if p["gravado"]]
    total_scg = sum(p["scg_gravado"] or 0.0 for p in gravados)
    altas = [a for a in ach if a["gravidade"] == "alta"]
    _titulo(doc, "1. Resumo")
    sentido = ("saldo a devolver à tarifa (faturou-se mais do que o gás custou)" if total_scg < 0
               else "saldo a recuperar na tarifa (o gás custou mais do que foi faturado)")
    _par(doc, f"O SCG do trimestre é de {brl(total_scg)}, {sentido}." if gravados
         else "Nenhum mês do trimestre tem fechamento gravado.")
    if altas:
        _par(doc, f"Há {len(altas)} incongruência(s) que não fecham e exigem ação (seção 4).", negrito=True)
    else:
        _par(doc, "As provas reais dos meses com notas gravadas fecham com os valores do fechamento.")
    atencao = [a for a in ach if a["gravidade"] == "atencao"]
    if atencao:
        _par(doc, f"Há {len(atencao)} ponto(s) que o sistema não conseguiu provar ou que merecem conferência.")

    _titulo(doc, "2. Resultado do trimestre")
    linhas = []
    for chave, nome in _COMPONENTES:
        vals = [(p["scg_gravado"] if chave == "scg" else p[chave]) if p["gravado"] else None for p in provas]
        linhas.append([nome, *[brl(v) if v is not None else "—" for v in vals],
                       brl(sum(v for v in vals if v is not None))])
    _tabela(doc, ["Componente", *[curto(m) for m in meses], "Trimestre"], linhas,
            [5.6, 2.6, 2.6, 2.6, 3.0][:len(meses) + 2] if len(meses) == 3 else [5.6] + [2.4] * (len(meses) + 1),
            destaque={5})
    _par(doc, "Fórmulas: RPV = CGR − CGF; SCG = RPV + RET + RP. O RP já vem líquido de PIS/COFINS.", tamanho=9)

    _titulo(doc, "3. Conferência mês a mês")
    _par(doc, "Cada parte do fechamento é refeita com as notas gravadas e comparada com o valor do fechamento.")
    linhas = []
    for p in provas:
        if not p["gravado"]:
            linhas.append([mes_ano(p["periodo"]).capitalize(), "—", "—", "—", "—", "sem fechamento"])
            continue
        def sel(chave):
            o = p["origens"][chave]
            tem = o.get("tem_itens", o.get("tem_resumo"))
            return "sem notas" if not tem else ("confere" if o["confere"] else "NÃO CONFERE")
        linhas.append([mes_ano(p["periodo"]).capitalize(), sel("cgr"), sel("cgf"), sel("ret"), sel("rp"),
                       "fecha" if p["confere"] else "NÃO FECHA"])
    _tabela(doc, ["Mês", "CGR", "CGF", "RET", "RP", "Conta do SCG"], linhas, [3.4, 2.6, 2.6, 2.6, 2.6, 3.0],
            alinha_direita=False)
    _par(doc, "“sem notas” = o mês foi gravado só com o total, então o sistema não consegue abrir a conta. "
              "“Conta do SCG” = RPV + RET + RP refeita com os valores do fechamento.", tamanho=9)

    _titulo(doc, "4. Incongruências e pontos de atenção")
    if not ach:
        _par(doc, "Nenhuma incongruência encontrada.")
    rotulo = {"alta": "Não fecha", "atencao": "Atenção", "info": "Registro"}
    for grav in ("alta", "atencao", "info"):
        grupo = [a for a in ach if a["gravidade"] == grav]
        if not grupo:
            continue
        _titulo(doc, rotulo[grav], 2)
        _tabela(doc, ["Mês", "Parte", "O que aconteceu"],
                [[curto(a["mes"]), a["modulo"], a["texto"]] for a in grupo], [1.8, 3.0, 11.8],
                alinha_direita=False)

    _titulo(doc, "5. Como ler este relatório")
    _par(doc, "“Confere” quer dizer que a conta fecha com as notas gravadas, não que as notas estejam certas. "
              "Se uma nota não veio nos arquivos do mês (como a da TAG em jul/26), o CGR fica abaixo do esperado "
              "até ela ser incluída à mão, o que aparece em “Registro”. Para validar contra a planilha oficial, "
              "use “Comparar com a planilha” no Painel do Ciclo.", tamanho=10)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
