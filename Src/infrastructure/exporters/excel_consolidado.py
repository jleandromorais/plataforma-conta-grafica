"""
Exportador do Relatório Consolidado da Conta Gráfica.

Gera um único arquivo .xlsx com todas as etapas do processo:
  📋 Resumo Executivo  |  📊 PMPV  |  🔍 Auditoria XML
  ⚡ RET               |  📄 Conciliação RP  |  📋 CGF
  🧾 SCG Final
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.styles import (
    Alignment, Border, Font, GradientFill, PatternFill, Side,
)
from openpyxl.utils import get_column_letter

from Src.Database.database import DatabasePMPV

# ── Paleta de cores ───────────────────────────────────────────────────────────
_NAVY      = "1A3A5C"   # cabeçalhos principais
_BLUE      = "2E86C1"   # módulo Auditoria
_TEAL      = "0E6655"   # módulo PMPV
_ORANGE    = "D35400"   # módulo RET
_PURPLE    = "6C3483"   # módulo Conciliação
_GOLD      = "B7950B"   # módulo CGF / SCG
_GREEN     = "1E8449"   # positivo
_RED       = "C0392B"   # negativo
_HEADER_FG = "FFFFFF"   # texto em cabeçalho escuro
_ROW_ALT   = "EBF5FB"   # linha alternada clara
_ROW_NORM  = "FFFFFF"   # linha normal
_SUMMARY   = "FEF9E7"   # linha de totais
_TITLE_BG  = "1A3A5C"   # fundo do título principal


# ── Helpers de estilo ─────────────────────────────────────────────────────────

def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, size=11, color="000000", italic=False) -> Font:
    return Font(bold=bold, size=size, color=color, italic=italic)


def _border(style="thin") -> Border:
    s = Side(style=style)
    return Border(left=s, right=s, top=s, bottom=s)


def _align(h="left", v="center", wrap=False) -> Alignment:
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)


def _money_fmt(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _vol_fmt(val: float) -> str:
    return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _apply_header_row(ws, row_num: int, labels: list[str],
                      widths: list[int], bg: str = _NAVY):
    for col_idx, (label, width) in enumerate(zip(labels, widths), start=1):
        cell = ws.cell(row=row_num, column=col_idx, value=label)
        cell.fill = _fill(bg)
        cell.font = _font(bold=True, color=_HEADER_FG, size=11)
        cell.alignment = _align("center")
        cell.border = _border()
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _apply_data_row(ws, row_num: int, values: list[Any],
                    fmts: list[str] | None = None,
                    alternate: bool = False,
                    bold_last: bool = False):
    bg = _ROW_ALT if alternate else _ROW_NORM
    fmts = fmts or ["@"] * len(values)
    for col_idx, (val, fmt) in enumerate(zip(values, fmts), start=1):
        cell = ws.cell(row=row_num, column=col_idx, value=val)
        cell.fill = _fill(bg)
        cell.font = _font(bold=(bold_last and col_idx == len(values)))
        cell.alignment = _align("right" if fmt != "@" else "left")
        cell.number_format = fmt
        cell.border = _border()


def _apply_total_row(ws, row_num: int, values: list[Any],
                     fmts: list[str] | None = None, bg: str = _SUMMARY):
    fmts = fmts or ["@"] * len(values)
    for col_idx, (val, fmt) in enumerate(zip(values, fmts), start=1):
        cell = ws.cell(row=row_num, column=col_idx, value=val)
        cell.fill = _fill(bg)
        cell.font = _font(bold=True, size=11)
        cell.alignment = _align("right" if fmt != "@" else "left")
        cell.number_format = fmt
        cell.border = _border()


def _section_title(ws, row_num: int, text: str, ncols: int, bg: str):
    ws.merge_cells(start_row=row_num, start_column=1,
                   end_row=row_num, end_column=ncols)
    cell = ws.cell(row=row_num, column=1, value=text)
    cell.fill = _fill(bg)
    cell.font = _font(bold=True, color=_HEADER_FG, size=12)
    cell.alignment = _align("left")
    cell.border = _border()


_BRL = 'R$ #,##0.00'
_VOL = '#,##0.00'
_VOL4 = '#,##0.0000'
_NUM = '#,##0'


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class ExcelConsolidado:
    """Gera o Relatório Consolidado completo a partir do banco de dados."""

    @staticmethod
    def _agregar_consolidacao(registros: list[dict]) -> dict:
        total = {
            "cgr": 0.0,
            "cgf": 0.0,
            "ret": 0.0,
            "rp": 0.0,
            "rpv": 0.0,
            "scg": 0.0,
        }
        for registro in registros:
            for chave in total:
                total[chave] += registro.get(chave, 0.0) or 0.0
        return total

    @staticmethod
    def exportar(periodo: str | None = None, nome_arquivo: str | None = None) -> str:
        """
        Gera o Excel consolidado.

        Args:
            periodo: Período a filtrar (ex: 'Dez/2025'). Se None, usa o mais
                     recente disponível para cada módulo.
            nome_arquivo: Caminho de saída. Se None, gera automaticamente.

        Returns:
            Caminho do arquivo gerado.
        """
        db = DatabasePMPV()
        try:
            return ExcelConsolidado._gerar(db, periodo, nome_arquivo)
        finally:
            db.fechar()

    # ── Gerador principal ────────────────────────────────────────────────────

    @staticmethod
    def _gerar(db: DatabasePMPV, periodo: str | None, nome_arquivo: str | None) -> str:
        if nome_arquivo is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            p_slug = (periodo or "completo").replace("/", "-")
            nome_arquivo = f"Relatorio_ContaGrafica_{p_slug}_{ts}.xlsx"

        final = str(Path(nome_arquivo))
        Path(final).parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        # Coleta dados do BD
        cons_periodos = db.listar_consolidacao_completa()
        cons = db.buscar_consolidacao(periodo) if periodo else ExcelConsolidado._agregar_consolidacao(cons_periodos)
        pmpv_sessoes = db.listar_sessoes_com_volumes()
        audit_itens  = db.listar_auditoria_itens(periodo)
        ret_itens    = db.listar_ret_itens(periodo)
        conc_itens   = db.listar_concilia_itens(periodo)
        cgf          = db.buscar_cgf_resumo(periodo) if periodo else None
        cgf_lista    = [cgf] if periodo and cgf else db.listar_cgf_resumos()
        sr           = db.buscar_sr(periodo) if periodo else None
        sr_lista     = [sr] if periodo and sr else db.listar_sr()
        pmpv_mensal  = db.listar_pmpv_mensal()

        # Sheets
        ExcelConsolidado._sheet_resumo(wb, cons, cons_periodos, pmpv_sessoes, cgf_lista, sr_lista, periodo)
        ExcelConsolidado._sheet_pmpv(wb, db, pmpv_sessoes)
        ExcelConsolidado._sheet_auditoria(wb, audit_itens, periodo)
        ExcelConsolidado._sheet_ret(wb, ret_itens, periodo)
        ExcelConsolidado._sheet_concilia(wb, conc_itens, periodo)
        ExcelConsolidado._sheet_cgf(wb, cgf if periodo else cgf_lista, periodo)
        ExcelConsolidado._sheet_scg(wb, cons, cons_periodos, sr if periodo else sr_lista, periodo)

        try:
            wb.save(final)
        except PermissionError as exc:
            wb.close()
            raise PermissionError(
                f"Não foi possível atualizar o Excel final em '{final}'. Feche o arquivo se ele estiver aberto no Excel e tente novamente."
            ) from exc
        wb.close()

        try:
            os.startfile(final)
        except Exception:
            pass

        return final

    # ── Sheet 1: Resumo Executivo ────────────────────────────────────────────

    @staticmethod
    def _sheet_resumo(wb, cons, cons_periodos, pmpv_sessoes, cgf_lista, sr_lista, periodo):
        ws = wb.create_sheet("📋 Resumo Executivo")
        ws.sheet_view.showGridLines = False

        # ── Título
        ws.merge_cells("A1:H1")
        t = ws["A1"]
        t.value = "RELATÓRIO CONSOLIDADO — CONTA GRÁFICA"
        t.fill = _fill(_TITLE_BG)
        t.font = _font(bold=True, size=18, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 40

        ws.merge_cells("A2:H2")
        sub = ws["A2"]
        sub.value = (
            f"Período: {periodo or 'Todos'}   |   "
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        sub.fill = _fill("2E4057")
        sub.font = _font(size=11, color="CCDDEE")
        sub.alignment = _align("center")
        ws.row_dimensions[2].height = 22

        row = 4

        def _card(label: str, value: str, bg: str, row: int, col: int = 1, span: int = 2):
            ws.merge_cells(
                start_row=row, start_column=col,
                end_row=row, end_column=col + span - 1
            )
            c = ws.cell(row=row, column=col, value=label)
            c.fill = _fill(bg)
            c.font = _font(bold=True, color=_HEADER_FG, size=11)
            c.alignment = _align("left")
            c.border = _border()

            ws.merge_cells(
                start_row=row + 1, start_column=col,
                end_row=row + 1, end_column=col + span - 1
            )
            v = ws.cell(row=row + 1, column=col, value=value)
            v.fill = _fill("F2F3F4")
            v.font = _font(bold=True, size=14)
            v.alignment = _align("center")
            v.border = _border()
            ws.row_dimensions[row].height = 20
            ws.row_dimensions[row + 1].height = 28

        sr_total = (sr_lista[0] if periodo and sr_lista else None) or None

        # CGR
        cgr_val = (cons or {}).get("cgr", 0.0)
        _card("🔍  CGR  (Auditoria XML)", _money_fmt(cgr_val), _BLUE, row, col=1, span=2)
        # CGF
        cgf_val = (cons or {}).get("cgf", 0.0)
        _card("📋  CGF  (Volume Faturado)", _money_fmt(cgf_val), _GOLD, row, col=3, span=2)
        # RPV
        rpv_val = (cons or {}).get("rpv", cgr_val - cgf_val)
        _card("🧾  RPV  = CGR − CGF", _money_fmt(rpv_val), _PURPLE, row, col=5, span=2)
        row += 3

        # RET
        ret_val = (cons or {}).get("ret", 0.0)
        _card("⚡  RET  (Encargos)", _money_fmt(ret_val), _ORANGE, row, col=1, span=2)
        # RP
        rp_val = (cons or {}).get("rp", 0.0)
        _card("📄  RP   (Conciliação)", _money_fmt(rp_val), _TEAL, row, col=3, span=2)
        # SR
        sr_val = sum((item or {}).get("sr", 0.0) or 0.0 for item in sr_lista) if not periodo else (sr_total or {}).get("sr", 0.0)
        _card("📈  SR   (Volume Prospectiva − VF) × PR", _money_fmt(sr_val), _NAVY, row, col=5, span=2)
        row += 3

        # SCG Final
        scg_val = (cons or {}).get("scg", 0.0)
        ws.merge_cells(f"A{row}:F{row}")
        c = ws.cell(row=row, column=1, value="💼  SCG FINAL  =  RPV + RET + RP")
        c.fill = _fill(_NAVY)
        c.font = _font(bold=True, color=_HEADER_FG, size=13)
        c.alignment = _align("center")
        c.border = _border()
        ws.row_dimensions[row].height = 24

        row += 1
        ws.merge_cells(f"A{row}:F{row}")
        v = ws.cell(row=row, column=1, value=scg_val)
        v.number_format = _BRL
        bg = _GREEN if scg_val >= 0 else _RED
        v.fill = _fill(bg)
        v.font = _font(bold=True, color=_HEADER_FG, size=20)
        v.alignment = _align("center")
        v.border = _border()
        ws.row_dimensions[row].height = 36

        row += 2

        # PMPV Mensal
        if pmpv_sessoes or True:
            _section_title(ws, row, "📊  PMPV — Últimas Sessões Salvas", 6, _TEAL)
            row += 1
            _apply_header_row(ws, row,
                ["Sessão", "Data", "Volume Prospectiva (m³)", "VF (m³)", "PMPV (R$/m³)", "Preço Final"],
                [30, 18, 16, 16, 16, 16], _TEAL)
            row += 1
            for i, s in enumerate(pmpv_sessoes[:10]):
                _apply_data_row(ws, row,
                    [s.get("nome", ""), s.get("data_criacao", ""),
                     s.get("vp", 0.0), s.get("vf", 0.0), "", ""],
                    ["@", "@", _VOL, _VOL, _BRL, _BRL],
                    alternate=(i % 2 == 1))
                row += 1

        if not periodo and cons_periodos:
            row += 2
            _section_title(ws, row, "📚  Consolidação por Período", 8, _NAVY)
            row += 1
            _apply_header_row(ws, row,
                ["Período", "CGR", "CGF", "RPV", "RET", "RP", "SCG", "Atualizado"],
                [18, 14, 14, 14, 14, 14, 14, 20], _NAVY)
            row += 1
            for i, item in enumerate(cons_periodos):
                _apply_data_row(ws, row,
                    [item.get("periodo", ""), item.get("cgr", 0.0), item.get("cgf", 0.0),
                     item.get("rpv", 0.0), item.get("ret", 0.0), item.get("rp", 0.0),
                     item.get("scg", 0.0), (item.get("data_atualizacao") or "")[:16]],
                    ["@", _BRL, _BRL, _BRL, _BRL, _BRL, _BRL, "@"],
                    alternate=(i % 2 == 1))
                row += 1

        ws.column_dimensions["A"].width = 32
        for col in "BCDEFG":
            ws.column_dimensions[col].width = 18

    # ── Sheet 2: PMPV ────────────────────────────────────────────────────────

    @staticmethod
    def _sheet_pmpv(wb, db: DatabasePMPV, sessoes):
        ws = wb.create_sheet("📊 PMPV")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:G1")
        t = ws["A1"]
        t.value = "GESTÃO PMPV — VOLUMES E PREÇOS POR EMPRESA / MÊS"
        t.fill = _fill(_TEAL)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3

        if not sessoes:
            ws.cell(row=row, column=1, value="Nenhuma sessão PMPV salva no banco de dados.")
            return

        for sessao in sessoes:
            sid  = sessao["id"]
            nome = sessao.get("nome", f"Sessão {sid}")
            data = sessao.get("data_criacao", "")

            _section_title(ws, row,
                f"  Sessão: {nome}  |  Data: {data}  |  "
                f"Volume Prospectiva: {_vol_fmt(sessao.get('vp', 0))} m³  |  "
                f"VF: {_vol_fmt(sessao.get('vf', 0))} m³",
                7, _TEAL)
            row += 1

            _apply_header_row(ws, row,
                ["Empresa", "Mês", "Molécula", "Transporte", "Logística",
                 "Preço Unit.", "Volume (m³/dia)"],
                [28, 12, 14, 14, 14, 14, 16], _TEAL)
            row += 1

            meses_rows: dict[int, list] = {}
            for mes_num in [1, 2, 3]:
                meses_rows[mes_num] = db.carregar_dados_mes(sid, mes_num)

            total_vf = total_custo = 0.0
            for mes_num, linhas in meses_rows.items():
                for i, l in enumerate(linhas):
                    mol   = l.get("molecula", 0.0)
                    trans = l.get("transporte", 0.0)
                    log   = l.get("logistica", 0.0)
                    vol   = l.get("volume", 0.0)
                    preco = mol + trans + log
                    _apply_data_row(ws, row,
                        [l.get("empresa", ""), f"Mês {mes_num}",
                         mol, trans, log, preco, vol],
                        ["@", "@", _VOL4, _VOL4, _VOL4, _VOL4, _VOL],
                        alternate=(i % 2 == 1))
                    row += 1

            # Resultados da sessão
            db.cursor.execute(
                "SELECT * FROM resultados WHERE sessao_id = ? ORDER BY id DESC LIMIT 1",
                (sid,)
            )
            res_row = db.cursor.fetchone()
            if res_row:
                res = dict(res_row)
                row += 1
                _apply_total_row(ws, row,
                    ["RESULTADO DA SESSÃO", "",
                     "", "", "",
                     f"PMPV: {_money_fmt(res.get('pmpv_trimestral', 0))} /m³",
                     f"VF Total: {_vol_fmt(res.get('vf_total', res.get('volume_total', 0)))} m³"],
                    bg="D5F5E3")
                row += 2

        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 12
        for col in "CDEFG":
            ws.column_dimensions[col].width = 16

    # ── Sheet 3: Auditoria XML ────────────────────────────────────────────────

    @staticmethod
    def _sheet_auditoria(wb, itens: list[dict], periodo: str | None):
        ws = wb.create_sheet("🔍 Auditoria XML")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:J1")
        t = ws["A1"]
        t.value = f"AUDITORIA XML — NF-e e CT-e  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_BLUE)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3
        mostrar_periodo = periodo is None
        cols  = (["Período"] if mostrar_periodo else []) + ["Empresa", "Tipo", "Número",
             "Valor Bruto (R$)", "ICMS (R$)", "PIS (R$)", "COFINS (R$)",
             "Volume (m³)", "CGR Líquido (R$)", "Status"]
        widths = ([14] if mostrar_periodo else []) + [22, 8, 14, 18, 14, 14, 14, 14, 18, 10]
        _apply_header_row(ws, row, cols, widths, _BLUE)
        row += 1

        if not itens:
            ws.cell(row=row, column=1,
                    value=f"Nenhum item de Auditoria XML registrado para o período '{periodo}'.")
            return

        tot_bruto = tot_icms = tot_pis = tot_cofins = tot_vol = tot_cgr = 0.0
        for i, it in enumerate(itens):
            vb  = it.get("valor_total", 0.0)
            ic  = it.get("icms", 0.0)
            ps  = it.get("pis", 0.0)
            cf  = it.get("cofins", 0.0)
            vol = it.get("volume_total", 0.0)
            cgr = it.get("cgr_liquido", 0.0)
            tot_bruto += vb; tot_icms += ic; tot_pis += ps
            tot_cofins += cf; tot_vol += vol; tot_cgr += cgr

            _apply_data_row(ws, row,
                ([it.get("periodo", "")] if mostrar_periodo else []) + [it.get("empresa", ""), it.get("tipo", ""), it.get("numero", ""),
                 vb, ic, ps, cf, vol, cgr, "OK"],
                (["@"] if mostrar_periodo else []) + ["@", "@", "@", _BRL, _BRL, _BRL, _BRL, _VOL, _BRL, "@"],
                alternate=(i % 2 == 1))
            row += 1

        # Totais
        _apply_total_row(ws, row,
            (["TOTAL"] if mostrar_periodo else []) + ["TOTAL", "", "", tot_bruto, tot_icms, tot_pis,
             tot_cofins, tot_vol, tot_cgr, ""],
            (["@"] if mostrar_periodo else []) + ["@", "@", "@", _BRL, _BRL, _BRL, _BRL, _VOL, _BRL, "@"],
            bg="D6EAF8")

        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["C"].width = 14
        for col in "DEFGHIJ":
            ws.column_dimensions[col].width = 16

    # ── Sheet 4: RET ────────────────────────────────────────────────────────

    @staticmethod
    def _sheet_ret(wb, itens: list[dict], periodo: str | None):
        ws = wb.create_sheet("⚡ RET")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:I1")
        t = ws["A1"]
        t.value = f"SISTEMA RET — ENCARGOS E DOCUMENTOS  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_ORANGE)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3
        mostrar_periodo = periodo is None
        cols   = (["Período"] if mostrar_periodo else []) + ["Arquivo", "Tipo Encargo", "Empresa", "Tipo Nota",
                  "Nº ND", "Vencimento", "Valor Total (R$)", "Moeda", "Contrib. EC"]
        widths = ([14] if mostrar_periodo else []) + [32, 16, 18, 12, 12, 14, 18, 8, 14]
        _apply_header_row(ws, row, cols, widths, _ORANGE)
        row += 1

        if not itens:
            ws.cell(row=row, column=1,
                    value=f"Nenhum item RET registrado para o período '{periodo}'.")
            return

        tipos: dict[str, float] = {}
        total = 0.0

        for i, it in enumerate(itens):
            vt = it.get("valor_total", 0.0)
            total += vt
            t_enc = it.get("tipo_encargo", "")
            tipos[t_enc] = tipos.get(t_enc, 0.0) + vt

            _apply_data_row(ws, row,
                ([it.get("periodo", "")] if mostrar_periodo else []) + [it.get("arquivo", ""), t_enc, it.get("empresa", ""),
                 it.get("nota_tipo", ""), it.get("numero_nd", ""),
                 it.get("data_vencimento", ""), vt,
                 it.get("moeda", "BRL"), it.get("contrib_ec", "")],
                (["@"] if mostrar_periodo else []) + ["@", "@", "@", "@", "@", "@", _BRL, "@", "@"],
                alternate=(i % 2 == 1))
            row += 1

        _apply_total_row(ws, row,
            (["TOTAL"] if mostrar_periodo else []) + ["TOTAL", "", "", "", "", "", total, "", ""],
            (["@"] if mostrar_periodo else []) + ["@", "@", "@", "@", "@", "@", _BRL, "@", "@"],
            bg="FAD7A0")
        row += 2

        # Resumo por tipo
        _section_title(ws, row, "  RESUMO POR TIPO DE ENCARGO", 9, _ORANGE)
        row += 1
        _apply_header_row(ws, row, ["Tipo Encargo", "Total (R$)"], [22, 18], _ORANGE)
        row += 1
        for tp, val in sorted(tipos.items()):
            _apply_total_row(ws, row, [tp, val], ["@", _BRL], bg="FEF5E7")
            row += 1

        ws.column_dimensions["A"].width = 34
        for col in "BCDEFGHI":
            ws.column_dimensions[col].width = 16

    # ── Sheet 5: Conciliação RP ──────────────────────────────────────────────

    @staticmethod
    def _sheet_concilia(wb, itens: list[dict], periodo: str | None):
        ws = wb.create_sheet("📄 Conciliação RP")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:F1")
        t = ws["A1"]
        t.value = f"CONCILIAÇÃO RP — RECEITAS E DESPESAS (PDFs)  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_PURPLE)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3
        mostrar_periodo = periodo is None
        cols   = (["Período"] if mostrar_periodo else []) + ["Arquivo", "Categoria", "Valor (R$)", "Status", "Método"]
        widths = ([14] if mostrar_periodo else []) + [40, 12, 18, 10, 30]
        _apply_header_row(ws, row, cols, widths, _PURPLE)
        row += 1

        if not itens:
            ws.cell(row=row, column=1,
                    value=f"Nenhum item de Conciliação registrado para o período '{periodo}'.")
            return

        tot_rec = tot_desp = 0.0
        for i, it in enumerate(itens):
            val  = it.get("valor", 0.0)
            cat  = it.get("categoria", "")
            if cat == "Receita":
                tot_rec += val
            else:
                tot_desp += val

            _apply_data_row(ws, row,
                ([it.get("periodo", "")] if mostrar_periodo else []) + [it.get("arquivo", ""), cat, val,
                 it.get("status", ""), it.get("metodo", "")],
                (["@"] if mostrar_periodo else []) + ["@", "@", _BRL, "@", "@"],
                alternate=(i % 2 == 1))
            row += 1

        saldo = tot_rec - tot_desp
        _apply_total_row(ws, row,
            (["TOTAL RECEITA"] if mostrar_periodo else []) + ["TOTAL RECEITA", "Receita", tot_rec, "", ""],
            bg="D5F5E3")
        row += 1
        _apply_total_row(ws, row,
            (["TOTAL DESPESA"] if mostrar_periodo else []) + ["TOTAL DESPESA", "Despesa", tot_desp, "", ""],
            bg="FADBD8")
        row += 1
        bg_saldo = _GREEN if saldo >= 0 else _RED
        c = ws.cell(row=row, column=1, value="SALDO  RP  =  Receita − Despesa")
        c.fill = _fill(bg_saldo)
        c.font = _font(bold=True, color=_HEADER_FG, size=12)
        c.border = _border()
        v = ws.cell(row=row, column=3, value=saldo)
        v.number_format = _BRL
        v.fill = _fill(bg_saldo)
        v.font = _font(bold=True, color=_HEADER_FG, size=12)
        v.border = _border()
        ws.cell(row=row, column=2).fill = _fill(bg_saldo)
        ws.cell(row=row, column=2).border = _border()

        ws.column_dimensions["A"].width = 40
        for col in "BCDEF":
            ws.column_dimensions[col].width = 18

    # ── Sheet 6: CGF ────────────────────────────────────────────────────────

    @staticmethod
    def _sheet_cgf(wb, cgf: dict | list[dict] | None, periodo: str | None):
        ws = wb.create_sheet("📋 CGF")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:D1")
        t = ws["A1"]
        t.value = f"VOLUME CGF — CONTA GRÁFICA DE FATURAMENTO  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_GOLD)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3
        if periodo is None:
            registros = cgf or []
            _apply_header_row(ws, row,
                ["Período", "Volume Faturado", "Consumo Próprio", "Canceladas", "Devoluções", "Volume Final"],
                [16, 18, 18, 16, 16, 16], _GOLD)
            row += 1
            for i, item in enumerate(registros):
                _apply_data_row(ws, row,
                    [item.get("periodo", ""), item.get("volume_faturado", 0.0), item.get("volume_consumo_proprio", 0.0),
                     item.get("volume_canceladas", 0.0), item.get("volume_devolucoes", 0.0), item.get("volume_final", 0.0)],
                    ["@", _VOL, _VOL, _VOL, _VOL, _VOL],
                    alternate=(i % 2 == 1))
                row += 1
            return

        data = cgf or {}
        campos = [
            ("(+) Volume Faturado (s/ cons. próprio)", data.get("volume_faturado", 0.0), _ROW_NORM),
            ("   ↳ Consumo Próprio excluído",           data.get("volume_consumo_proprio", 0.0), _ROW_ALT),
            ("(−) Volume Canceladas / Denegadas",       data.get("volume_canceladas", 0.0), "FADBD8"),
            ("(−) Volume Devoluções",                   data.get("volume_devolucoes", 0.0), "FADBD8"),
        ]

        _apply_header_row(ws, row, ["Componente", "Volume (m³)", "Sinal", "Obs."],
                          [36, 20, 10, 30], _GOLD)
        row += 1
        sinais = ["+", "(−)", "(−)", "(−)"]
        for (label, val, bg), sinal in zip(campos, sinais):
            for col in range(1, 5):
                c = ws.cell(row=row, column=col)
                c.fill = _fill(bg)
                c.border = _border()
            ws.cell(row=row, column=1, value=label).font = _font()
            ws.cell(row=row, column=1).alignment = _align("left")
            v = ws.cell(row=row, column=2, value=val)
            v.number_format = _VOL
            v.alignment = _align("right")
            ws.cell(row=row, column=3, value=sinal).alignment = _align("center")
            row += 1

        vf = data.get("volume_final", 0.0)
        _apply_total_row(ws, row,
            ["(=)  VOLUME FINAL CGF (VF)", vf, "=", ""],
            ["@", _VOL, "@", "@"], bg="D5F5E3")
        ws.row_dimensions[row].height = 22

        ws.column_dimensions["A"].width = 38
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 30

    # ── Sheet 7: SCG Final ───────────────────────────────────────────────────

    @staticmethod
    def _sheet_scg(wb, cons: dict | None, cons_periodos: list[dict], sr: dict | list[dict] | None, periodo: str | None):
        ws = wb.create_sheet("🧾 SCG Final")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:D1")
        t = ws["A1"]
        t.value = f"CONSOLIDAÇÃO SCG FINAL  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_NAVY)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3
        if periodo is None:
            _apply_header_row(ws, row,
                ["Período", "CGR", "CGF", "RPV", "RET", "RP", "SCG"],
                [18, 14, 14, 14, 14, 14, 14], _NAVY)
            row += 1
            for i, item in enumerate(cons_periodos):
                _apply_data_row(ws, row,
                    [item.get("periodo", ""), item.get("cgr", 0.0), item.get("cgf", 0.0),
                     item.get("rpv", 0.0), item.get("ret", 0.0), item.get("rp", 0.0), item.get("scg", 0.0)],
                    ["@", _BRL, _BRL, _BRL, _BRL, _BRL, _BRL],
                    alternate=(i % 2 == 1))
                row += 1

            if sr:
                row += 2
                _section_title(ws, row, "  📈  SR por Período", 4, _NAVY)
                row += 1
                _apply_header_row(ws, row,
                    ["Período", "VP (m³)", "VF (m³)", "SR (R$)"],
                    [18, 18, 18, 18], _NAVY)
                row += 1
                for i, item in enumerate(sr):
                    _apply_data_row(ws, row,
                        [item.get("periodo", ""), item.get("vp", 0.0), item.get("vf", 0.0), item.get("sr", 0.0)],
                        ["@", _VOL, _VOL, _BRL],
                        alternate=(i % 2 == 1))
                    row += 1
            return

        data = cons or {}

        cgr = data.get("cgr", 0.0)
        cgf = data.get("cgf", 0.0)
        rpv = data.get("rpv", cgr - cgf)
        ret = data.get("ret", 0.0)
        rp  = data.get("rp", 0.0)
        scg = data.get("scg", rpv + ret + rp)

        linhas = [
            ("📄  CGR  (Auditoria XML)",       cgr,  _BLUE,   "+"),
            ("📋  CGF  (Volume Faturado)",      cgf,  _GOLD,   "−"),
            ("🧾  RPV  = CGR − CGF",            rpv,  _PURPLE, "="),
            ("⚡  RET  (Encargos Transporte)",   ret,  _ORANGE, "+"),
            ("📄  RP   (Conciliação Penalid.)",  rp,   _TEAL,   "+"),
        ]

        _apply_header_row(ws, row,
            ["Módulo / Componente", "Valor (R$)", "Op.", "Obs."],
            [36, 22, 8, 30], _NAVY)
        row += 1

        for i, (label, val, bg_mod, op) in enumerate(linhas):
            for col in range(1, 5):
                c = ws.cell(row=row, column=col)
                c.fill = _fill(_ROW_ALT if i % 2 else _ROW_NORM)
                c.border = _border()
            ws.cell(row=row, column=1, value=label).font = _font()
            ws.cell(row=row, column=1).alignment = _align("left")
            v = ws.cell(row=row, column=2, value=val)
            v.number_format = _BRL
            v.alignment = _align("right")
            ws.cell(row=row, column=3, value=op).alignment = _align("center")
            row += 1

        # Linha separadora
        row += 1

        # SCG Final
        ws.merge_cells(f"A{row}:D{row}")
        lbl = ws.cell(row=row, column=1,
                      value="💼  SCG  =  RPV  +  RET  +  RP")
        bg_scg = _GREEN if scg >= 0 else _RED
        lbl.fill = _fill(bg_scg)
        lbl.font = _font(bold=True, color=_HEADER_FG, size=13)
        lbl.alignment = _align("left")
        lbl.border = _border()
        ws.row_dimensions[row].height = 28
        row += 1

        ws.merge_cells(f"A{row}:D{row}")
        v = ws.cell(row=row, column=1, value=scg)
        v.number_format = _BRL
        v.fill = _fill(bg_scg)
        v.font = _font(bold=True, color=_HEADER_FG, size=22)
        v.alignment = _align("center")
        v.border = _border()
        ws.row_dimensions[row].height = 44
        row += 2

        # SR (se disponível)
        if sr:
            _section_title(ws, row, "  📈  SR  =  (VP − VF) × PR", 4, _NAVY)
            row += 1
            _apply_header_row(ws, row,
                ["VP (m³)", "VF (m³)", "PR (R$/m³)", "SR (R$)"],
                [20, 20, 20, 22], _NAVY)
            row += 1
            _apply_data_row(ws, row,
                [sr.get("vp", 0.0), sr.get("vf", 0.0),
                 sr.get("pr", 0.0), sr.get("sr", 0.0)],
                [_VOL, _VOL, _BRL, _BRL])
            row += 2

        # Fórmula legível
        _section_title(ws, row, "  FÓRMULA OFICIAL", 4, "2C3E50")
        row += 1
        formulas = [
            "RPV  =  CGR  −  CGF",
            "SCG  =  RPV  +  RET  +  RP",
            "SR   =  (VP  −  VF) × PR",
        ]
        for f in formulas:
            ws.merge_cells(f"A{row}:D{row}")
            c = ws.cell(row=row, column=1, value=f)
            c.fill = _fill(_ROW_ALT)
            c.font = _font(italic=True, size=11)
            c.alignment = _align("center")
            c.border = _border()
            row += 1

        ws.column_dimensions["A"].width = 38
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 30
