from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ── Paleta de cores ──────────────────────────────────────────────────────────
_TITULO_BG      = "0D2137"
_HEADER_BG      = "1A3A5C"
_SUBTITULO_BG   = "E8F4FD"
_NFE_PAR        = "EBF7EE"
_NFE_IMPAR      = "D5F5E3"
_CTE_PAR        = "FEF9E7"
_CTE_IMPAR      = "FDF2D0"
_OUTRO_PAR      = "EBF3FB"
_OUTRO_IMPAR    = "F7F9FA"
_TOTAL_BG       = "D4E6F1"
_RESUMO_HEADER  = "2E86AB"

_FMT_MOEDA  = 'R$ #,##0.00'
_FMT_PCT    = '0.0%'
_FMT_INT    = '#,##0'

def _thin_border():
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def _thick_border():
    s = Side(style="medium", color="1A3A5C")
    return Border(left=s, right=s, top=s, bottom=s)


class ExcelAuditoria:

    @staticmethod
    def gerar_relatorio_auditoria(resultados, nome_arquivo, cgr_total: float = 0.0):
        """Gera relatório Excel completo e formatado com todos os dados auditados."""
        from Src.Services.servicos_auditoria import PIS_COFINS_RATE

        wb = Workbook()
        ws = wb.active
        ws.title = "Relatório Completo"

        COLS = [
            "Empresa",
            "Tipo",
            "Nº NF / CT-e",
            "Valor Total (R$)",
            "ICMS (R$)",
            "ICMS (%)",
            "PIS (R$)",
            "COFINS (R$)",
            "Volume (m³)",
            "CGR Líquido (R$)",
            "Fonte",
        ]
        N = len(COLS)
        last_col = get_column_letter(N)

        # ── Linha 1: Título ──────────────────────────────────────────────────
        ws.row_dimensions[1].height = 36
        c = ws.cell(1, 1, "RELATÓRIO DE AUDITORIA FISCAL")
        c.font = Font(name="Calibri", size=18, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color=_TITULO_BG, end_color=_TITULO_BG, fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(f"A1:{last_col}1")

        # ── Linha 2: Subtítulo ───────────────────────────────────────────────
        ws.row_dimensions[2].height = 20
        sub_txt = (
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y  %H:%M')}     |"
            f"     Total de registros: {len(resultados)}"
        )
        c2 = ws.cell(2, 1, sub_txt)
        c2.font = Font(name="Calibri", size=10, italic=True, color="555555")
        c2.fill = PatternFill(start_color=_SUBTITULO_BG, end_color=_SUBTITULO_BG, fill_type="solid")
        c2.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(f"A2:{last_col}2")

        # ── Linha 3: vazia ───────────────────────────────────────────────────
        ws.row_dimensions[3].height = 6

        # ── Linha 4: Cabeçalhos ──────────────────────────────────────────────
        ws.row_dimensions[4].height = 28
        for col, header in enumerate(COLS, 1):
            c = ws.cell(4, col, header)
            c.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            c.fill = PatternFill(start_color=_HEADER_BG, end_color=_HEADER_BG, fill_type="solid")
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = _thin_border()

        # ── Linhas de dados (ordenadas por empresa → tipo → número) ──────────
        dados = sorted(resultados, key=lambda r: (r.empresa.lower(), r.tipo, r.numero))
        PRIMEIRA = 5

        for idx, item in enumerate(dados, PRIMEIRA):
            par = (idx - PRIMEIRA) % 2 == 0
            if item.tipo == "NF-e":
                bg = _NFE_PAR if par else _NFE_IMPAR
            elif item.tipo == "CT-e":
                bg = _CTE_PAR if par else _CTE_IMPAR
            else:
                bg = _OUTRO_PAR if par else _OUTRO_IMPAR

            fill = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
            cgr_item = (item.valor_total - item.icms) * (1.0 - PIS_COFINS_RATE)

            linha = [
                item.empresa,
                item.tipo,
                item.numero,
                item.valor_total,
                item.icms,
                item.icms_taxa,
                item.pis,
                item.cofins,
                item.volume_total,
                cgr_item,
                item.status,
            ]
            for col, val in enumerate(linha, 1):
                c = ws.cell(idx, col, val)
                c.fill = fill
                c.border = _thin_border()
                c.font = Font(name="Calibri", size=10)
                if col == 1:
                    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
                elif col in (2, 3, 11):
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col in (4, 5, 7, 8, 10):
                    c.number_format = _FMT_MOEDA
                    c.alignment = Alignment(horizontal="right", vertical="center")
                elif col == 6:
                    c.number_format = _FMT_PCT
                    c.alignment = Alignment(horizontal="center", vertical="center")
                elif col == 9:
                    c.number_format = _FMT_INT
                    c.alignment = Alignment(horizontal="right", vertical="center")

        # ── Linha TOTAL ───────────────────────────────────────────────────────
        total_row = PRIMEIRA + len(dados)
        ws.row_dimensions[total_row].height = 26
        fill_tot = PatternFill(start_color=_TOTAL_BG, end_color=_TOTAL_BG, fill_type="solid")
        borda_tot = _thick_border()

        cell_lbl = ws.cell(total_row, 1, "TOTAL GERAL")
        cell_lbl.font = Font(name="Calibri", size=12, bold=True, color="0D2137")
        cell_lbl.fill = fill_tot
        cell_lbl.alignment = Alignment(horizontal="center", vertical="center")
        cell_lbl.border = borda_tot
        ws.merge_cells(f"A{total_row}:C{total_row}")

        totais = {
            4: sum(r.valor_total  for r in resultados),
            5: sum(r.icms         for r in resultados),
            7: sum(r.pis          for r in resultados),
            8: sum(r.cofins       for r in resultados),
            9: sum(r.volume_total for r in resultados),
            10: cgr_total if cgr_total else sum(
                (r.valor_total - r.icms) * (1.0 - PIS_COFINS_RATE) for r in resultados
            ),
        }
        for col in range(1, N + 1):
            c = ws.cell(total_row, col)
            if col <= 3:
                pass  # já mergeado
            else:
                val = totais.get(col)
                if val is not None:
                    c.value = val
                    c.number_format = _FMT_INT if col == 9 else _FMT_MOEDA
                    c.alignment = Alignment(horizontal="right", vertical="center")
                c.fill = fill_tot
                c.font = Font(name="Calibri", size=11, bold=True, color="0D2137")
                c.border = borda_tot

        # ── Seção RESUMO POR TIPO ─────────────────────────────────────────────
        res_start = total_row + 2
        ws.row_dimensions[res_start].height = 24

        lbl_res = ws.cell(res_start, 1, "RESUMO POR TIPO DE DOCUMENTO")
        lbl_res.font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        lbl_res.fill = PatternFill(start_color=_HEADER_BG, end_color=_HEADER_BG, fill_type="solid")
        lbl_res.alignment = Alignment(horizontal="center", vertical="center")
        ws.merge_cells(f"A{res_start}:F{res_start}")

        res_cols_hdr = ["Tipo", "Qtd.", "Valor Total (R$)", "ICMS Total (R$)", "CGR Líquido (R$)", "% do CGR"]
        for col, h in enumerate(res_cols_hdr, 1):
            c = ws.cell(res_start + 1, col, h)
            c.font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
            c.fill = PatternFill(start_color=_RESUMO_HEADER, end_color=_RESUMO_HEADER, fill_type="solid")
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = _thin_border()

        tipos: dict = {}
        for r in resultados:
            t = r.tipo
            if t not in tipos:
                tipos[t] = {"count": 0, "valor": 0.0, "icms": 0.0, "cgr": 0.0}
            tipos[t]["count"] += 1
            tipos[t]["valor"] += r.valor_total
            tipos[t]["icms"]  += r.icms
            tipos[t]["cgr"]   += (r.valor_total - r.icms) * (1.0 - PIS_COFINS_RATE)

        total_cgr_all = sum(v["cgr"] for v in tipos.values()) or 1.0
        for i, (tipo, vals) in enumerate(sorted(tipos.items()), 1):
            ri = res_start + 1 + i
            bg = _OUTRO_PAR if i % 2 == 0 else "FFFFFF"
            fill_r = PatternFill(start_color=bg, end_color=bg, fill_type="solid")
            row_v = [tipo, vals["count"], vals["valor"], vals["icms"], vals["cgr"], vals["cgr"] / total_cgr_all]
            for col, val in enumerate(row_v, 1):
                c = ws.cell(ri, col, val)
                c.fill = fill_r
                c.border = _thin_border()
                c.font = Font(name="Calibri", size=10)
                if col in (3, 4, 5):
                    c.number_format = _FMT_MOEDA
                    c.alignment = Alignment(horizontal="right", vertical="center")
                elif col == 6:
                    c.number_format = _FMT_PCT
                    c.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    c.alignment = Alignment(horizontal="center", vertical="center")

        # ── Larguras de colunas ───────────────────────────────────────────────
        for col, w in enumerate([34, 8, 16, 18, 16, 10, 14, 14, 14, 20, 10], 1):
            ws.column_dimensions[get_column_letter(col)].width = w

        ws.freeze_panes = "A5"

        wb.save(nome_arquivo)