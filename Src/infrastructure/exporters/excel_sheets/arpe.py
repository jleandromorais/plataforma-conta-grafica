"""Visual ARPE do Excel Final: fundo branco, cabeçalhos azul-escuro, linhas
alternadas claras e totais em amarelo-claro, como a planilha da Nota Técnica.

`tabela()` monta as abas de resultado; `aplicar_tema()` padroniza as abas de
detalhe já geradas (cores, fontes, larguras, impressão) sem mexer nos dados.
"""
from __future__ import annotations

import re
from typing import Any

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

AZUL = "1F4E78"      # título e cabeçalhos
AZUL_CLARO = "DDEBF7"  # linha de resultado (ex.: SCG, SR com SELIC)
CINZA = "F2F2F2"     # linha alternada
AMARELO = "FFF2CC"   # totais
BORDA = "BFBFBF"
TEXTO = "1F1F1F"
TEXTO_SUAVE = "595959"

BRL = 'R$ #,##0.00;[Red]-R$ #,##0.00'
TARIFA = '0.0000;[Red]-0.0000'
VOLUME = '#,##0.00;[Red]-#,##0.00'
PCT = '0.000000'

_LADO = Side(style="thin", color=BORDA)
_BORDA = Border(left=_LADO, right=_LADO, top=_LADO, bottom=_LADO)
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿️]+")


def _fill(cor: str) -> PatternFill:
    return PatternFill("solid", fgColor=cor)


def _font(bold=False, cor=TEXTO, tam=10, italico=False) -> Font:
    return Font(name="Calibri", bold=bold, color=cor, size=tam, italic=italico)


def preparar(ws, ncols: int, larguras: list[float]) -> None:
    ws.sheet_view.showGridLines = False
    for i, w in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def titulo(ws, texto: str, subtitulo: str, ncols: int) -> int:
    """Faixa azul com o título (linha 1) e a explicação em cinza (linha 2).
    Devolve a próxima linha livre."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(1, 1, texto)
    c.fill, c.font = _fill(AZUL), _font(True, "FFFFFF", 13)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 26
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    s = ws.cell(2, 1, subtitulo)
    s.font = _font(cor=TEXTO_SUAVE, italico=True)
    s.alignment = Alignment(horizontal="left", vertical="center", indent=1, wrap_text=True)
    ws.row_dimensions[2].height = 30
    return 4


def cabecalho(ws, linha: int, rotulos: list[str]) -> None:
    for i, r in enumerate(rotulos, start=1):
        c = ws.cell(linha, i, r)
        c.fill, c.font, c.border = _fill(AZUL), _font(True, "FFFFFF"), _BORDA
        c.alignment = Alignment(horizontal="left" if i == 1 else "center", vertical="center", wrap_text=True)
    ws.row_dimensions[linha].height = 20


def linha(ws, n: int, valores: list[Any], formatos: list[str | None], estilo: str = "normal", alternada=False) -> None:
    """estilo: "normal", "destaque" (azul-claro, negrito) ou "total" (amarelo, negrito)."""
    fundo = {"destaque": AZUL_CLARO, "total": AMARELO}.get(estilo, CINZA if alternada else "FFFFFF")
    negrito = estilo != "normal"
    for i, (v, fmt) in enumerate(zip(valores, formatos), start=1):
        c = ws.cell(n, i, v)
        c.fill, c.font, c.border = _fill(fundo), _font(negrito), _BORDA
        if fmt and isinstance(v, (int, float)):
            c.number_format = fmt
            c.alignment = Alignment(horizontal="right", vertical="center")
        else:
            c.alignment = Alignment(horizontal="left" if i == 1 else "center", vertical="center", indent=1 if i == 1 else 0)
    ws.row_dimensions[n].height = 18


def nota(ws, n: int, texto: str, ncols: int) -> None:
    ws.merge_cells(start_row=n, start_column=1, end_row=n, end_column=ncols)
    c = ws.cell(n, 1, texto)
    c.font = _font(cor=TEXTO_SUAVE, italico=True, tam=9)
    c.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True, indent=1)
    ws.row_dimensions[n].height = 28


# ── Padronização das abas de detalhe ─────────────────────────────────────────

def _luminancia(rgb: str) -> float:
    rgb = rgb[-6:]
    r, g, b = (int(rgb[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _rgb(cor) -> str | None:
    if cor is None or getattr(cor, "type", None) != "rgb" or not isinstance(cor.rgb, str):
        return None
    return cor.rgb[-6:].upper()


def sem_emoji(texto: str) -> str:
    return _EMOJI.sub("", texto).strip()


def aplicar_tema(ws) -> None:
    """Leva uma aba já gerada para o visual ARPE: fundos escuros/coloridos viram
    azul ARPE com texto branco; amarelados viram total; os demais claros viram
    cinza alternado; fonte Calibri; largura mínima para não aparecer ####."""
    ws.title = sem_emoji(ws.title) or ws.title
    ws.sheet_view.showGridLines = False
    larguras: dict[int, float] = {}
    mescladas = {c.coordinate for r in ws.merged_cells.ranges for row in ws[r.coord] for c in row}

    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str):
                limpo = sem_emoji(c.value)
                if limpo != c.value:
                    c.value = limpo
            fundo = _rgb(c.fill.fgColor) if c.fill is not None and c.fill.fill_type == "solid" else None
            fonte = c.font
            branco = False
            if fundo and fundo not in ("FFFFFF", "000000"):
                lum = _luminancia(fundo)
                if lum < 0.75:
                    c.fill, branco = _fill(AZUL), True
                elif fundo[:2] in ("FE", "FF") and fundo[4:] < "E8":  # amarelados/laranja-claro
                    c.fill = _fill(AMARELO)
                else:
                    c.fill = _fill(CINZA)
            # Texto branco só sobre o azul; nos fundos claros mantém a cor
            # original (ex.: vermelho de negativo), trocando branco por escuro.
            original = _rgb(fonte.color)
            cor = "FFFFFF" if branco else (TEXTO if original in (None, "FFFFFF") else original)
            c.font = Font(name="Calibri", size=fonte.sz or 10, bold=fonte.b, italic=fonte.i, color=cor)
            if c.border is not None and c.border.left is not None and c.border.left.style:
                c.border = _BORDA
            if c.value is not None and c.coordinate not in mescladas:
                larguras[c.column] = max(larguras.get(c.column, 0), _largura(c))

    for col, w in larguras.items():
        dim = ws.column_dimensions[get_column_letter(col)]
        if (dim.width or 8.43) < w:
            dim.width = min(w, 60)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def _largura(c) -> float:
    v = c.value
    if isinstance(v, (int, float)):
        txt = f"{v:,.2f}"
        if "R$" in (c.number_format or ""):
            txt = "R$ " + txt
    else:
        txt = str(v).split("\n")[0]
    escala = 1.15 if (c.font is not None and c.font.b) else 1.05
    return len(txt) * escala * max((c.font.sz or 10) / 10, 1) + 2
