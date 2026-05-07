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
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.series import DataPoint

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


def _to_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _money_fmt(val: Any) -> str:
    num = _to_float(val)
    return f"R$ {num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _money4_fmt(val: Any) -> str:
    num = _to_float(val)
    return f"R$ {num:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _vol_fmt(val: Any) -> str:
    num = _to_float(val)
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


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
        cell_value = _to_float(val) if fmt != "@" else ("" if val is None else val)
        cell = ws.cell(row=row_num, column=col_idx, value=val)
        cell.value = cell_value
        cell.fill = _fill(bg)
        cell.font = _font(bold=(bold_last and col_idx == len(values)))
        cell.alignment = _align("right" if fmt != "@" else "left")
        cell.number_format = fmt
        cell.border = _border()


def _apply_total_row(ws, row_num: int, values: list[Any],
                     fmts: list[str] | None = None, bg: str = _SUMMARY):
    fmts = fmts or ["@"] * len(values)
    for col_idx, (val, fmt) in enumerate(zip(values, fmts), start=1):
        cell_value = _to_float(val) if fmt != "@" else ("" if val is None else val)
        cell = ws.cell(row=row_num, column=col_idx, value=val)
        cell.value = cell_value
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

# Mapa de abreviatura → nome completo do mês (PT-BR)
_MESES_FULL: dict[str, str] = {
    "Jan": "Janeiro",  "Fev": "Fevereiro", "Mar": "Março",
    "Abr": "Abril",    "Mai": "Maio",       "Jun": "Junho",
    "Jul": "Julho",    "Ago": "Agosto",     "Set": "Setembro",
    "Out": "Outubro",  "Nov": "Novembro",   "Dez": "Dezembro",
}

# Ordem numérica de cada abreviatura
_MES_ORD: dict[str, int] = {ab: i for i, ab in enumerate(_MESES_FULL, 1)}

# Janelas de meses válidos por módulo (abreviaturas PT-BR)
_MESES_PMPV = {"Fev", "Mar", "Abr"}   # Fevereiro a Abril
_MESES_RET  = {"Jan", "Fev", "Mar"}   # Janeiro a Março
# RPV (CGR + CGF): sem restrição de mês — usa todos disponíveis

def _abrev_de_periodo(periodo: str) -> str:
    """Extrai a abreviatura do mês de 'Mmm/YYYY' → 'Mmm'."""
    return periodo.split("/")[0].capitalize()[:3] if "/" in periodo else periodo[:3].capitalize()

def _nome_mes_completo(periodo: str) -> str:
    """'Abr/2026' → 'Abril/2026'."""
    ab = _abrev_de_periodo(periodo)
    ano = periodo.split("/")[1] if "/" in periodo else ""
    nome = _MESES_FULL.get(ab, ab)
    return f"{nome}/{ano}" if ano else nome

def _agrupar_em_trimestres(meses: list[str]) -> list[list[str]]:
    """Divide uma lista de meses ordenados em grupos de 3 (trimestres).
    Ex: ['Jan/26','Fev/26','Mar/26','Abr/26'] → [['Jan/26','Fev/26','Mar/26'],['Abr/26']]
    """
    return [meses[i:i+3] for i in range(0, len(meses), 3)]

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
    def exportar(
        periodo: str | None = None,
        nome_arquivo: str | None = None,
        periodos_trimestre: list[str] | None = None,
    ) -> str:
        """
        Gera o Excel consolidado.

        Args:
            periodo: Período de referência principal (ex: 'Abr/2025') — usado
                     para PMPV, CGF, PR, PV, SR e SCG.
            periodos_trimestre: Lista dos 3 meses do trimestre (ex:
                     ['Fev/25', 'Mar/25', 'Abr/25']). Quando fornecida,
                     Auditoria, RET e Conciliação são agregados dos 3 meses.
                     Se None, usa apenas `periodo`.
            nome_arquivo: Caminho de saída. Se None, gera automaticamente.
        """
        db = DatabasePMPV()
        try:
            return ExcelConsolidado._gerar(db, periodo, nome_arquivo, periodos_trimestre)
        finally:
            db.fechar()

    # ── Gerador principal ────────────────────────────────────────────────────

    @staticmethod
    def _gerar(
        db: DatabasePMPV,
        periodo: str | None,
        nome_arquivo: str | None,
        periodos_trimestre: list[str] | None = None,
    ) -> str:
        # Abreviaturas de mês válidas PT-BR
        _ABREVS_VALIDAS = {"Jan","Fev","Mar","Abr","Mai","Jun",
                           "Jul","Ago","Set","Out","Nov","Dez"}

        def _mes_valido(p: str) -> bool:
            """Aceita apenas 'Mmm/YYYY' (ex: 'Jan/2026'). Rejeita 'RET/25', 'Q1/2026', etc."""
            partes = (p or "").strip().split("/")
            if len(partes) != 2:
                return False
            abrev, ano = partes[0].strip().capitalize()[:3], partes[1].strip()
            return abrev in _ABREVS_VALIDAS and len(ano) == 4 and ano.isdigit()

        # Lista de meses do trimestre para Auditoria / RET / Conciliação
        meses_raw = periodos_trimestre or ([periodo] if periodo else [])
        meses = [m for m in meses_raw if _mes_valido(m)]
        # Se filtragem removeu tudo, usa os originais (melhor exibir algo do que nada)
        if not meses and meses_raw:
            meses = meses_raw

        label_trimestre = "  ·  ".join(meses) if meses else (periodo or "completo")

        p_slug = label_trimestre.replace("/", "-").replace("  ·  ", "_")

        if nome_arquivo is None:
            nome_arquivo = f"Relatorio_ContaGrafica_{p_slug}.xlsx"

        final = str(Path(nome_arquivo))
        Path(final).parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        # ── PMPV / PR / PV / SR / SCG — filtrado pelo período principal
        cons_periodos = db.listar_consolidacao_completa(periodo) if periodo else db.listar_consolidacao_completa()
        cons          = db.buscar_consolidacao(periodo) if periodo else ExcelConsolidado._agregar_consolidacao(cons_periodos)
        pmpv_sessoes  = db.listar_sessoes_com_volumes(periodo)
        sr            = db.buscar_sr(periodo) if periodo else None
        sr_lista      = [sr] if periodo and sr else db.listar_sr()
        pr            = db.buscar_pr(periodo) if periodo else None
        pr_lista      = [pr] if periodo and pr else db.listar_pr()
        pv            = db.buscar_pv(periodo) if periodo else None
        pv_lista      = [pv] if periodo and pv else db.listar_pv()
        pmpv_mensal   = db.listar_pmpv_mensal()
        execucoes     = db.listar_execucoes_excel_final(periodo=periodo) if periodo else db.listar_execucoes_excel_final()

        # ── Helper: períodos válidos disponíveis em cada tabela ─────────────────
        def _ord(p):
            ab = _abrev_de_periodo(p)
            an = p.split("/")[1] if "/" in p else "0"
            return int(an) * 12 + _MES_ORD.get(ab, 0)

        def _periodos_tabela(
            tabela: str,
            col_periodo: str = "periodo",
            filtro_modulo: set[str] | None = None,
        ) -> list[str]:
            """Retorna períodos Mmm/YYYY distintos da tabela.

            filtro_modulo: conjunto de abreviaturas permitidas (ex: _MESES_RET).
            Se None, não aplica filtro de módulo — usa apenas o trimestre ativo.
            """
            try:
                db.cursor.execute(f"SELECT DISTINCT {col_periodo} FROM {tabela}")
                rows = [r[0] for r in db.cursor.fetchall() if r[0] and _mes_valido(r[0])]
            except Exception:
                return []
            if filtro_modulo:
                # Módulo com janela fixa (RET=Jan-Mar, PMPV=Fev-Abr):
                # filtra só pelas abreviaturas permitidas.
                rows = [r for r in rows if _abrev_de_periodo(r) in filtro_modulo]
            # Auditoria, CGF, Conciliação: sem filtro — todos os meses válidos do banco,
            # ordenados cronologicamente do mais antigo para o mais recente.
            return sorted(rows, key=_ord)

        # Cada módulo usa apenas os meses da sua janela de negócio:
        # RET  = Janeiro–Março  |  PMPV = Fevereiro–Abril  |  RPV/CGF/Auditoria = sem restrição
        meses_ret   = _periodos_tabela("ret_itens",       filtro_modulo=_MESES_RET)
        meses_audit = _periodos_tabela("auditoria_itens")           # RPV/CGR — sem restrição
        meses_cgf   = _periodos_tabela("cgf_resumo")                # RPV/CGF — sem restrição
        meses_conc  = _periodos_tabela("concilia_itens")

        # Labels de cada módulo para o título da aba
        def _label(ms): return "  ·  ".join(ms) if ms else label_trimestre

        # Buscar dados de cada módulo nos seus próprios períodos
        audit_itens = []
        for mes in meses_audit:
            audit_itens.extend(db.listar_auditoria_itens(mes) or [])

        ret_itens = []
        for mes in meses_ret:
            ret_itens.extend(db.listar_ret_itens(mes) or [])

        conc_itens = []
        for mes in meses_conc:
            conc_itens.extend(db.listar_concilia_itens(mes) or [])

        cgf_lista = []
        for mes in meses_cgf:
            resumo = db.buscar_cgf_resumo(mes)
            if resumo:
                cgf_lista.append(resumo)

        # Fallback CGF: se não encontrou nada pelos períodos, tenta tudo
        if not cgf_lista:
            cgf_lista = db.listar_cgf_resumos()

        # CGF de referência = último mês com dados
        cgf = cgf_lista[-1] if cgf_lista else None

        # PMPV: filtrar trimestre para incluir só Fev–Abr
        meses_pmpv = [m for m in meses if _abrev_de_periodo(m) in _MESES_PMPV] or meses

        # Sheets — cada um com o seu label e meses reais
        ExcelConsolidado._sheet_resumo(wb, cons, cons_periodos, pmpv_sessoes, cgf_lista, sr_lista, pr_lista, pv_lista, label_trimestre)
        ExcelConsolidado._sheet_pmpv(wb, db, pmpv_sessoes, meses_pmpv)
        ExcelConsolidado._sheet_auditoria(wb, audit_itens, _label(meses_audit), meses_audit)
        ExcelConsolidado._sheet_ret(wb, ret_itens, _label(meses_ret), meses_ret)
        ExcelConsolidado._sheet_concilia(wb, conc_itens, _label(meses_conc))
        ExcelConsolidado._sheet_cgf(wb, cgf_lista, _label(meses_cgf), meses_cgf, db)
        ExcelConsolidado._sheet_scg(wb, cons, cons_periodos, sr if periodo else sr_lista, periodo)
        ExcelConsolidado._sheet_sr(wb, sr if periodo else sr_lista, periodo)
        ExcelConsolidado._sheet_pr(wb, pr if periodo else pr_lista, periodo)
        ExcelConsolidado._sheet_pv(wb, pv if periodo else pv_lista, periodo)
        ExcelConsolidado._sheet_progresso(wb, execucoes, periodo)
        ExcelConsolidado._sheet_dashboard(
            wb, cons, cons_periodos, pr if periodo else (pr_lista[0] if pr_lista else None),
            pv if periodo else (pv_lista[0] if pv_lista else None),
            sr if periodo else (sr_lista[0] if sr_lista else None),
            label_trimestre,
        )

        # Se o arquivo estiver aberto no Excel, tenta fechar via taskkill antes de salvar
        try:
            wb.save(final)
        except PermissionError:
            # Tenta fechar o Excel no Windows e salva novamente
            try:
                os.system("taskkill /f /im excel.exe >nul 2>&1")
                import time; time.sleep(1)
                wb.save(final)
            except Exception:
                wb.close()
                raise PermissionError(
                    f"Feche o arquivo '{Path(final).name}' no Excel e tente novamente."
                )

        wb.close()

        try:
            os.startfile(final)
        except Exception:
            pass

        return final

    # ── Sheet 1: Resumo Executivo ────────────────────────────────────────────

    @staticmethod
    def _sheet_resumo(wb, cons, cons_periodos, pmpv_sessoes, cgf_lista, sr_lista, pr_lista, pv_lista, periodo):
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
        _card("📈  SR   (Volume Prospectivo − VF) × PR", _money_fmt(sr_val), _NAVY, row, col=5, span=2)
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

        pr_ref = (pr_lista[0] if pr_lista else {}) or {}
        pv_ref = (pv_lista[0] if pv_lista else {}) or {}
        _card("💡  PR Final  = (SGR + SR) / VP", _money4_fmt(pr_ref.get("pr", 0.0)), _BLUE, row, col=1, span=3)
        _card("💰  PV Final  = PMPV + PR", _money4_fmt(pv_ref.get("pv", 0.0)), _GREEN, row, col=4, span=3)

        row += 3

        # PMPV Mensal
        if pmpv_sessoes or True:
            _section_title(ws, row, "📊  PMPV — Últimas Sessões Salvas", 6, _TEAL)
            row += 1
            _apply_header_row(ws, row,
                ["Sessão", "Data", "Volume Prospectivo (m³)", "VF (m³)", "PMPV (R$/m³)", "Preço Final"],
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
    def _sheet_pmpv(wb, db: DatabasePMPV, sessoes, meses_trimestre: list[str] | None = None):
        def _nome_mes(mes_num: int) -> str:
            """Converte posição 1/2/3 no nome real do mês do trimestre."""
            if meses_trimestre and mes_num <= len(meses_trimestre):
                return _nome_mes_completo(meses_trimestre[mes_num - 1])
            return f"Mês {mes_num}"

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

        _NCOLS_PMPV = 7
        _COLS_PMPV  = ["Empresa", "Molécula", "Transporte", "Logística",
                       "Preço Unit.", "Volume (m³/dia)", "Subtotal (R$)"]
        _WIDTHS_PMPV = [28, 14, 14, 14, 14, 16, 16]
        _FMTS_PMPV   = ["@", _VOL4, _VOL4, _VOL4, _VOL4, _VOL, _BRL]

        for sessao in sessoes:
            sid  = sessao["id"]
            nome = sessao.get("nome", f"Sessão {sid}")
            data = sessao.get("data_criacao", "")

            # ── Cabeçalho da sessão ───────────────────────────────────────────
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=_NCOLS_PMPV)
            sh = ws.cell(row=row, column=1,
                value=f"  Sessão: {nome}  |  Data: {data}  |  "
                      f"VP: {_vol_fmt(sessao.get('vp', 0))} m³  |  "
                      f"VF: {_vol_fmt(sessao.get('vf', 0))} m³")
            sh.fill = _fill(_TEAL); sh.font = _font(bold=True, size=12, color=_HEADER_FG)
            sh.alignment = _align("left"); sh.border = _border()
            ws.row_dimensions[row].height = 22; row += 1
            ws.row_dimensions[row].height = 4; row += 1

            grand_vol = grand_sub = 0.0

            for mes_num in [1, 2, 3]:
                linhas = db.carregar_dados_mes(sid, mes_num)
                if not linhas:
                    continue

                nome_mes = _nome_mes(mes_num)

                # ── Divisor do mês (igual ao RET) ─────────────────────────────
                ws.merge_cells(start_row=row, start_column=1,
                               end_row=row, end_column=_NCOLS_PMPV)
                sec = ws.cell(row=row, column=1,
                              value=f"  ── {nome_mes} " + "─" * 42)
                sec.fill = _fill("1A5276"); sec.font = _font(bold=True, color=_HEADER_FG, size=11)
                sec.alignment = _align("left"); sec.border = _border()
                ws.row_dimensions[row].height = 20; row += 1

                # ── Cabeçalho de colunas do mês ───────────────────────────────
                _apply_header_row(ws, row, _COLS_PMPV, _WIDTHS_PMPV, "2E86C1")
                row += 1

                sub_vol = sub_preco = 0.0
                for i, l in enumerate(linhas):
                    mol   = l.get("molecula", 0.0)
                    trans = l.get("transporte", 0.0)
                    log   = l.get("logistica", 0.0)
                    vol   = l.get("volume", 0.0)
                    preco = mol + trans + log
                    subtotal = preco * vol
                    sub_vol += vol; sub_preco += subtotal
                    _apply_data_row(ws, row,
                        [l.get("empresa", ""), mol, trans, log, preco, vol, subtotal],
                        _FMTS_PMPV, alternate=(i % 2 == 1))
                    row += 1

                # ── Subtotal do mês ───────────────────────────────────────────
                for ci in range(1, _NCOLS_PMPV + 1):
                    c = ws.cell(row=row, column=ci)
                    c.fill = _fill("D6EAF8"); c.border = _border()
                    c.font = _font(bold=True, size=11, color="1A5276")
                ws.cell(row=row, column=1,
                        value=f"SUBTOTAL {nome_mes.upper()}").alignment = _align("left")
                c6 = ws.cell(row=row, column=6, value=sub_vol)
                c6.number_format = _VOL; c6.alignment = _align("right")
                c6.fill = _fill("D6EAF8"); c6.border = _border()
                c6.font = _font(bold=True, size=11, color="1A5276")
                c7 = ws.cell(row=row, column=7, value=sub_preco)
                c7.number_format = _BRL; c7.alignment = _align("right")
                c7.fill = _fill("D6EAF8"); c7.border = _border()
                c7.font = _font(bold=True, size=11, color="1A5276")
                ws.row_dimensions[row].height = 20; row += 1
                ws.row_dimensions[row].height = 6; row += 1

                grand_vol += sub_vol; grand_sub += sub_preco

            # ── Total geral da sessão ─────────────────────────────────────────
            db.cursor.execute(
                "SELECT * FROM resultados WHERE sessao_id = ? ORDER BY id DESC LIMIT 1",
                (sid,)
            )
            res_row_db = db.cursor.fetchone()
            pmpv_val = dict(res_row_db).get("pmpv_trimestral", 0) if res_row_db else 0

            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
            tl = ws.cell(row=row, column=1,
                         value=f"  ══ TOTAL GERAL DA SESSÃO  |  PMPV: {_money_fmt(pmpv_val)} /m³")
            tl.fill = _fill(_TEAL); tl.font = _font(bold=True, size=13, color=_HEADER_FG)
            tl.alignment = _align("left"); tl.border = _border()
            for ci in [2,3,4,5]:
                ws.cell(row=row,column=ci).fill=_fill(_TEAL); ws.cell(row=row,column=ci).border=_border()
            c6t = ws.cell(row=row, column=6, value=grand_vol)
            c6t.number_format=_VOL; c6t.alignment=_align("right")
            c6t.fill=_fill(_TEAL); c6t.border=_border(); c6t.font=_font(bold=True,size=13,color=_HEADER_FG)
            c7t = ws.cell(row=row, column=7, value=grand_sub)
            c7t.number_format=_BRL; c7t.alignment=_align("right")
            c7t.fill=_fill(_TEAL); c7t.border=_border(); c7t.font=_font(bold=True,size=13,color=_HEADER_FG)
            ws.row_dimensions[row].height = 26; row += 3

        for i, w in enumerate(_WIDTHS_PMPV, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ── Sheet 3: Auditoria XML ────────────────────────────────────────────────

    @staticmethod
    def _sheet_auditoria(wb, itens: list[dict], label_trimestre: str | None,
                         meses: list[str] | None = None):
        _NCOLS  = 10
        _COLS   = ["Empresa","Tipo","Número","Valor Bruto (R$)",
                   "ICMS (R$)","PIS (R$)","COFINS (R$)","Volume (m³)","CGR Líquido (R$)","Status"]
        _WIDTHS = [22, 8, 14, 18, 14, 14, 14, 14, 18, 10]
        _FMTS   = ["@","@","@",_BRL,_BRL,_BRL,_BRL,_VOL,_BRL,"@"]

        _BLUE_DARK  = "1A5276"
        _BLUE_MED   = "2E86C1"
        _BLUE_LIGHT = "D6EAF8"
        _BLUE_XL    = "EBF5FB"

        ws = wb.create_sheet("🔍 Auditoria XML")
        ws.sheet_view.showGridLines = False

        # Título
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=_NCOLS)
        t = ws.cell(row=1, column=1,
                    value=f"  AUDITORIA XML — NF-e e CT-e  |  Trimestre: {label_trimestre or 'N/D'}")
        t.fill = _fill(_BLUE_DARK); t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("left"); ws.row_dimensions[1].height = 34

        ws.row_dimensions[2].height = 6
        for c in range(1, _NCOLS + 1):
            ws.cell(row=2, column=c).fill = _fill("A9CCE3")

        if not itens:
            ws.cell(row=4, column=1, value="Nenhum item de Auditoria XML registrado para este trimestre.")
            return

        from collections import defaultdict
        grupos: dict[str, list] = defaultdict(list)
        for it in itens:
            grupos[it.get("periodo", "Sem Período")].append(it)

        ordem = list(meses or [])
        for p in grupos:
            if p not in ordem:
                ordem.append(p)

        grand = {"bruto":0.0,"icms":0.0,"pis":0.0,"cofins":0.0,"vol":0.0,"cgr":0.0}
        row = 3

        trimestres = _agrupar_em_trimestres(ordem)
        meses_por_trimestre = {m: i for i, tri in enumerate(trimestres) for m in tri}

        tri_atual = -1
        for periodo_mes in ordem:
            its = grupos.get(periodo_mes)
            if not its:
                continue

            # Banner de trimestre a cada novo grupo de 3 meses
            tri_idx = meses_por_trimestre.get(periodo_mes, -1)
            if tri_idx != tri_atual:
                tri_atual = tri_idx
                tri_meses = trimestres[tri_idx]
                label_tri = "  🗓  TRIMESTRE:  " + "  ·  ".join(tri_meses)
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=_NCOLS)
                bt = ws.cell(row=row, column=1, value=label_tri)
                bt.fill = _fill(_BLUE_DARK); bt.font = _font(bold=True, color="F0F8FF", size=12)
                bt.alignment = _align("left"); bt.border = _border()
                ws.row_dimensions[row].height = 24; row += 1

            ano_mes  = periodo_mes.split("/")[1] if "/" in periodo_mes else ""
            mes_full = _nome_mes_completo(periodo_mes).split("/")[0]
            label_sec = f"  ── {mes_full}{'/'+ano_mes if ano_mes else ''} " + "─"*40

            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=_NCOLS)
            sec = ws.cell(row=row, column=1, value=label_sec)
            sec.fill = _fill(_BLUE_MED); sec.font = _font(bold=True, color=_HEADER_FG, size=11)
            sec.alignment = _align("left"); sec.border = _border()
            ws.row_dimensions[row].height = 20; row += 1

            _apply_header_row(ws, row, _COLS, _WIDTHS, _BLUE_MED); row += 1

            sub = {"bruto":0.0,"icms":0.0,"pis":0.0,"cofins":0.0,"vol":0.0,"cgr":0.0}
            for i, it in enumerate(its):
                vb  = _to_float(it.get("valor_total"))
                ic  = _to_float(it.get("icms"))
                ps  = _to_float(it.get("pis"))
                cf  = _to_float(it.get("cofins"))
                vol = _to_float(it.get("volume_total"))
                cgr = _to_float(it.get("cgr_liquido"))
                sub["bruto"]+=vb; sub["icms"]+=ic; sub["pis"]+=ps
                sub["cofins"]+=cf; sub["vol"]+=vol; sub["cgr"]+=cgr
                _apply_data_row(ws, row,
                    [it.get("empresa",""),it.get("tipo",""),it.get("numero",""),
                     vb,ic,ps,cf,vol,cgr,"OK"], _FMTS, alternate=(i%2==1))
                row += 1

            # Subtotal do mês
            label_sub = f"SUBTOTAL {mes_full.upper()}{'/'+ano_mes if ano_mes else ''}"
            for ci in range(1, _NCOLS+1):
                c = ws.cell(row=row, column=ci)
                c.fill = _fill(_BLUE_LIGHT); c.border = _border()
                c.font = _font(bold=True, size=11, color=_BLUE_DARK)
            ws.cell(row=row, column=1, value=label_sub).alignment = _align("left")
            for ci, key, fmt in [(4,"bruto",_BRL),(5,"icms",_BRL),(6,"pis",_BRL),
                                  (7,"cofins",_BRL),(8,"vol",_VOL),(9,"cgr",_BRL)]:
                c = ws.cell(row=row, column=ci, value=sub[key])
                c.number_format=fmt; c.alignment=_align("right")
                c.fill=_fill(_BLUE_LIGHT); c.border=_border()
                c.font=_font(bold=True,size=11,color=_BLUE_DARK)
            for k in sub: grand[k] += sub[k]
            ws.row_dimensions[row].height = 20; row += 1
            ws.row_dimensions[row].height = 8; row += 1

        # Total Geral
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        tl = ws.cell(row=row, column=1, value="  ══ TOTAL GERAL DO TRIMESTRE ══")
        tl.fill=_fill(_BLUE_DARK); tl.font=_font(bold=True,size=13,color=_HEADER_FG)
        tl.alignment=_align("left"); tl.border=_border()
        for ci in [2,3]: ws.cell(row=row,column=ci).fill=_fill(_BLUE_DARK); ws.cell(row=row,column=ci).border=_border()
        for ci, key, fmt in [(4,"bruto",_BRL),(5,"icms",_BRL),(6,"pis",_BRL),
                              (7,"cofins",_BRL),(8,"vol",_VOL),(9,"cgr",_BRL)]:
            c = ws.cell(row=row, column=ci, value=grand[key])
            c.fill=_fill(_BLUE_DARK); c.font=_font(bold=True,size=13,color=_HEADER_FG)
            c.number_format=fmt; c.alignment=_align("right"); c.border=_border()
        for ci in [10]: ws.cell(row=row,column=ci).fill=_fill(_BLUE_DARK); ws.cell(row=row,column=ci).border=_border()
        ws.row_dimensions[row].height = 26

        ws.column_dimensions["A"].width = 22
        ws.column_dimensions["C"].width = 14
        for i, w in enumerate(_WIDTHS, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

    # ── Sheet 4: RET ────────────────────────────────────────────────────────

    @staticmethod
    def _sheet_ret(wb, itens: list[dict], label_trimestre: str | None,
                   meses: list[str] | None = None):
        _NCOLS = 9
        _COLS  = ["Arquivo", "Tipo Encargo", "Empresa", "Tipo Nota",
                  "Nº ND", "Vencimento", "Valor Total (R$)", "Moeda", "Contrib. EC"]
        _WIDTHS = [34, 16, 18, 12, 12, 14, 20, 8, 14]
        _FMTS   = ["@", "@", "@", "@", "@", "@", _BRL, "@", "@"]

        # Cores de destaque do módulo RET
        _ORANGE_DARK  = "A04000"   # título principal
        _ORANGE_MED   = "D35400"   # cabeçalho de mês / header de tabela
        _ORANGE_LIGHT = "FAD7A0"   # subtotal / total
        _ORANGE_XL    = "FEF5E7"   # resumo por tipo

        ws = wb.create_sheet("⚡ RET")
        ws.sheet_view.showGridLines = False

        # ── Linha 1: Título do trimestre ──────────────────────────────────────
        trimestre_label = label_trimestre or "N/D"
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=_NCOLS)
        t = ws.cell(row=1, column=1,
                    value=f"  SISTEMA RET — ENCARGOS E DOCUMENTOS  |  Trimestre: {trimestre_label}")
        t.fill = _fill(_ORANGE_DARK)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("left")
        ws.row_dimensions[1].height = 34

        # Linha 2: espaço
        ws.row_dimensions[2].height = 6
        for c in range(1, _NCOLS + 1):
            ws.cell(row=2, column=c).fill = _fill("F5CBA7")

        if not itens:
            ws.cell(row=4, column=1, value="Nenhum item RET registrado para este trimestre.")
            return

        # ── Agrupar itens por período (na ordem de meses do trimestre) ─────────
        from collections import defaultdict
        grupos: dict[str, list] = defaultdict(list)
        for it in itens:
            grupos[it.get("periodo", "Sem Período")].append(it)

        # Ordem: segue a lista de meses do trimestre; itens sem período vão ao fim
        ordem = list(meses or [])
        for p in grupos:
            if p not in ordem:
                ordem.append(p)

        tipos_total: dict[str, float] = {}
        grand_total = 0.0
        row = 3

        trimestres = _agrupar_em_trimestres(ordem)
        meses_por_trimestre = {m: i for i, tri in enumerate(trimestres) for m in tri}
        tri_atual = -1

        for periodo_mes in ordem:
            itens_mes = grupos.get(periodo_mes)
            if not itens_mes:
                continue

            # Banner de trimestre a cada novo grupo de 3 meses
            tri_idx = meses_por_trimestre.get(periodo_mes, -1)
            if tri_idx != tri_atual:
                tri_atual = tri_idx
                tri_meses = trimestres[tri_idx]
                label_tri = "  🗓  TRIMESTRE:  " + "  ·  ".join(tri_meses)
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=_NCOLS)
                bt = ws.cell(row=row, column=1, value=label_tri)
                bt.fill = _fill(_ORANGE_DARK); bt.font = _font(bold=True, color="FFF8F0", size=12)
                bt.alignment = _align("left"); bt.border = _border()
                ws.row_dimensions[row].height = 24; row += 1

            # Nome completo do mês para o cabeçalho da seção
            ano_mes  = periodo_mes.split("/")[1] if "/" in periodo_mes else ""
            mes_full = _nome_mes_completo(periodo_mes).split("/")[0]
            label_mes = f"  ── {mes_full}{'/'+ano_mes if ano_mes else ''} " + "─" * 40

            # Cabeçalho da seção do mês (laranja médio)
            ws.merge_cells(start_row=row, start_column=1,
                           end_row=row, end_column=_NCOLS)
            sec = ws.cell(row=row, column=1, value=label_mes)
            sec.fill = _fill(_ORANGE_MED)
            sec.font = _font(bold=True, color=_HEADER_FG, size=11)
            sec.alignment = _align("left")
            sec.border = _border()
            ws.row_dimensions[row].height = 20
            row += 1

            # Header das colunas
            _apply_header_row(ws, row, _COLS, _WIDTHS, _ORANGE_MED)
            row += 1

            _PIS_COFINS = 0.0925
            sub_eat = 0.0   # soma bruta EAT do mês
            sub_ec  = 0.0   # soma bruta EC_docs do mês
            for i, it in enumerate(itens_mes):
                vt    = _to_float(it.get("valor_total"))
                t_enc = it.get("tipo_encargo", "")
                if t_enc == "EAT":
                    sub_eat += vt
                elif t_enc == "EC":
                    sub_ec += vt
                tipos_total[t_enc] = tipos_total.get(t_enc, 0.0) + vt

                _apply_data_row(ws, row, [
                    it.get("arquivo", ""),
                    t_enc,
                    it.get("empresa", ""),
                    it.get("nota_tipo", ""),
                    it.get("numero_nd", ""),
                    it.get("data_vencimento", ""),
                    vt,
                    it.get("moeda", "BRL"),
                    it.get("contrib_ec", ""),
                ], _FMTS, alternate=(i % 2 == 1))
                row += 1

            # EC líquido do mês = EAT × (1 − PIS/COFINS) + EC_docs
            ec_liquido_mes = sub_eat * (1.0 - _PIS_COFINS) + sub_ec

            # Subtotal do mês — mostra EC líquido
            label_sub = f"SUBTOTAL EC LÍQUIDO — {mes_full.upper()}{'/'+ano_mes if ano_mes else ''}"
            for col_i in range(1, _NCOLS + 1):
                c = ws.cell(row=row, column=col_i)
                c.fill = _fill(_ORANGE_LIGHT)
                c.font = _font(bold=True, size=11, color=_ORANGE_DARK)
                c.border = _border()
                if col_i == 1:
                    c.value = label_sub
                    c.alignment = _align("left")
                elif col_i == 7:
                    c.value = ec_liquido_mes
                    c.number_format = _BRL
                    c.alignment = _align("right")
            ws.row_dimensions[row].height = 20
            grand_total += ec_liquido_mes
            row += 1

            # Espaço entre meses
            ws.row_dimensions[row].height = 8
            row += 1

        # ── Total Geral do Trimestre ──────────────────────────────────────────
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        tot_lbl = ws.cell(row=row, column=1, value="  ══ EC LÍQUIDO TOTAL DO TRIMESTRE (RET) ══")
        tot_lbl.fill = _fill(_ORANGE_DARK)
        tot_lbl.font = _font(bold=True, size=13, color=_HEADER_FG)
        tot_lbl.alignment = _align("left")
        tot_lbl.border = _border()
        tot_val = ws.cell(row=row, column=7, value=grand_total)
        tot_val.fill = _fill(_ORANGE_DARK)
        tot_val.font = _font(bold=True, size=13, color=_HEADER_FG)
        tot_val.number_format = _BRL
        tot_val.alignment = _align("right")
        tot_val.border = _border()
        for c in [2, 3, 4, 5, 6, 8, 9]:
            ws.cell(row=row, column=c).fill = _fill(_ORANGE_DARK)
            ws.cell(row=row, column=c).border = _border()
        ws.row_dimensions[row].height = 26
        row += 2

        # ── Resumo por Tipo de Encargo ────────────────────────────────────────
        _section_title(ws, row, "  ── RESUMO POR TIPO DE ENCARGO (TRIMESTRE)", _NCOLS, _ORANGE_MED)
        ws.row_dimensions[row].height = 20
        row += 1
        _apply_header_row(ws, row, ["Tipo de Encargo", "Total (R$)"], [24, 20], _ORANGE_MED)
        row += 1
        for tp, val in sorted(tipos_total.items()):
            for c in range(1, _NCOLS + 1):
                ws.cell(row=row, column=c).fill = _fill(_ORANGE_XL)
            ws.cell(row=row, column=1, value=tp).font = _font(bold=True, size=11)
            ws.cell(row=row, column=1).alignment = _align("left")
            ws.cell(row=row, column=1).border = _border()
            v_cell = ws.cell(row=row, column=2, value=val)
            v_cell.number_format = _BRL
            v_cell.font = _font(bold=True, size=11)
            v_cell.alignment = _align("right")
            v_cell.border = _border()
            row += 1

        # ── Larguras das colunas ──────────────────────────────────────────────
        for i, w in enumerate(_WIDTHS, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

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
    def _sheet_cgf(wb, cgf_lista: list[dict] | None, label_trimestre: str | None,
                   meses: list[str] | None = None, db=None):
        _GOLD_DARK  = "7D6608"
        _GOLD_MED   = "B7950B"
        _GOLD_LIGHT = "FCF3CF"
        _GOLD_XL    = "FEFDE7"
        _NCOLS = 5  # adicionou coluna CGF R$

        ws = wb.create_sheet("📋 CGF")
        ws.sheet_view.showGridLines = False

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=_NCOLS)
        t = ws.cell(row=1, column=1,
                    value=f"  VOLUME CGF — CONTA GRÁFICA DE FATURAMENTO  |  Trimestre: {label_trimestre or 'N/D'}")
        t.fill = _fill(_GOLD_DARK); t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("left"); ws.row_dimensions[1].height = 34

        ws.row_dimensions[2].height = 6
        for c in range(1, _NCOLS + 1):
            ws.cell(row=2, column=c).fill = _fill("F9E79F")

        registros = cgf_lista or []
        if not registros:
            ws.cell(row=4, column=1, value="Nenhum dado CGF registrado para este trimestre.")
            return

        # Indexar por período para seguir a ordem de meses
        idx = {r.get("periodo", ""): r for r in registros}
        ordem = list(meses or [])
        for p in idx:
            if p not in ordem:
                ordem.append(p)

        grand_vf  = 0.0
        grand_rs  = 0.0
        row = 3

        def _cgf_cell(r, c, val, bg, bold=False, fmt="@", align_h="left"):
            cell = ws.cell(row=r, column=c, value=val)
            cell.fill = _fill(bg); cell.border = _border()
            cell.font = _font(bold=bold, size=11)
            cell.alignment = _align(align_h, "center")
            if fmt != "@": cell.number_format = fmt
            return cell

        trimestres = _agrupar_em_trimestres(ordem)
        meses_por_trimestre = {m: i for i, tri in enumerate(trimestres) for m in tri}
        tri_atual = -1

        for periodo_mes in ordem:
            data = idx.get(periodo_mes)
            if not data:
                continue

            # Banner de trimestre a cada novo grupo de 3 meses
            tri_idx = meses_por_trimestre.get(periodo_mes, -1)
            if tri_idx != tri_atual:
                tri_atual = tri_idx
                tri_meses = trimestres[tri_idx]
                label_tri = "  🗓  TRIMESTRE:  " + "  ·  ".join(tri_meses)
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=_NCOLS)
                bt = ws.cell(row=row, column=1, value=label_tri)
                bt.fill = _fill(_GOLD_DARK); bt.font = _font(bold=True, color="FFFFF0", size=12)
                bt.alignment = _align("left"); bt.border = _border()
                ws.row_dimensions[row].height = 24; row += 1

            ano_mes  = periodo_mes.split("/")[1] if "/" in periodo_mes else ""
            mes_full = _nome_mes_completo(periodo_mes).split("/")[0]

            # Busca CGF em R$ da tabela consolidacao para este período
            cgf_rs_mes = 0.0
            pmpv_mes   = 0.0
            if db:
                try:
                    cons_mes = db.buscar_consolidacao(periodo_mes)
                    cgf_rs_mes = _to_float((cons_mes or {}).get("cgf"))
                    pmpv_row = db.buscar_pmpv_mensal(periodo_mes) if hasattr(db, "buscar_pmpv_mensal") else None
                    if pmpv_row is None:
                        try:
                            db.cursor.execute(
                                "SELECT pmpv FROM pmpv_mensal WHERE periodo = ? LIMIT 1",
                                (periodo_mes,)
                            )
                            r_pmpv = db.cursor.fetchone()
                            pmpv_mes = float(r_pmpv[0]) if r_pmpv else 0.0
                        except Exception:
                            pmpv_mes = 0.0
                    else:
                        pmpv_mes = _to_float(pmpv_row) if isinstance(pmpv_row, (int, float)) else 0.0
                except Exception:
                    pass

            # Cabeçalho do mês
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=_NCOLS)
            sec = ws.cell(row=row, column=1,
                          value=f"  ── {mes_full}{'/'+ano_mes if ano_mes else ''} " + "─"*40)
            sec.fill = _fill(_GOLD_MED); sec.font = _font(bold=True, color=_HEADER_FG, size=11)
            sec.alignment = _align("left"); sec.border = _border()
            ws.row_dimensions[row].height = 20; row += 1

            # Header de colunas — agora com CGF R$
            _apply_header_row(ws, row,
                ["Componente", "Volume (m³)", "Sinal", "PMPV (R$/m³)", "CGF (R$)"],
                [38, 20, 8, 16, 20], _GOLD_MED); row += 1

            campos = [
                ("(+) Volume Faturado (s/ cons. próprio)", data.get("volume_faturado", 0.0),         _ROW_NORM, "+"),
                ("   ↳ Consumo Próprio excluído",          data.get("volume_consumo_proprio", 0.0),  _ROW_ALT,  ""),
                ("(−) Volume Canceladas / Denegadas",      data.get("volume_canceladas", 0.0),       "FADBD8",  "(−)"),
                ("(−) Volume Devoluções",                  data.get("volume_devolucoes", 0.0),       "FADBD8",  "(−)"),
            ]
            for label, val, bg, sinal in campos:
                _cgf_cell(row, 1, label, bg)
                _cgf_cell(row, 2, val,   bg, fmt=_VOL,  align_h="right")
                _cgf_cell(row, 3, sinal, bg, align_h="center")
                _cgf_cell(row, 4, "",    bg)
                _cgf_cell(row, 5, "",    bg)
                row += 1

            # Volume Final + CGF em R$ do mês
            vf = _to_float(data.get("volume_final"))
            grand_vf += vf
            grand_rs += cgf_rs_mes

            _cgf_cell(row, 1, f"(=)  VOLUME FINAL CGF — {mes_full.upper()}", "D5F5E3", bold=True)
            _cgf_cell(row, 2, vf,         "D5F5E3", bold=True, fmt=_VOL, align_h="right")
            _cgf_cell(row, 3, "=",        "D5F5E3", align_h="center")
            _cgf_cell(row, 4, pmpv_mes if pmpv_mes else "", "D5F5E3",
                      fmt="#,##0.0000" if pmpv_mes else "@", align_h="right")
            _cgf_cell(row, 5, cgf_rs_mes if cgf_rs_mes else "", "D5F5E3",
                      bold=True, fmt=_BRL if cgf_rs_mes else "@", align_h="right")
            ws.row_dimensions[row].height = 22; row += 1
            ws.row_dimensions[row].height = 8;  row += 1

        # Total Geral
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
        tl = ws.cell(row=row, column=1, value="  ══ TOTAL DO TRIMESTRE ══")
        tl.fill=_fill(_GOLD_DARK); tl.font=_font(bold=True,size=13,color=_HEADER_FG)
        tl.alignment=_align("left"); tl.border=_border()
        for ci in [2, 3]:
            ws.cell(row=row, column=ci).fill = _fill(_GOLD_DARK)
            ws.cell(row=row, column=ci).border = _border()
        tv = ws.cell(row=row, column=4, value=grand_vf)
        tv.fill=_fill(_GOLD_DARK); tv.font=_font(bold=True,size=13,color=_HEADER_FG)
        tv.number_format=_VOL; tv.alignment=_align("right"); tv.border=_border()
        tr = ws.cell(row=row, column=5, value=grand_rs if grand_rs else "")
        tr.fill=_fill(_GOLD_DARK); tr.font=_font(bold=True,size=13,color=_HEADER_FG)
        tr.number_format=_BRL; tr.alignment=_align("right"); tr.border=_border()
        ws.row_dimensions[row].height = 26

        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 8
        ws.column_dimensions["D"].width = 16
        ws.column_dimensions["E"].width = 22

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

    # ── Sheet SR: Saldo Remanescente ─────────────────────────────────────────

    @staticmethod
    def _sheet_sr(wb, sr: dict | list[dict] | None, periodo: str | None):
        _NAVY_SR = "1B2A4A"
        ws = wb.create_sheet("📈 SR")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:E1")
        t = ws["A1"]
        t.value = f"SALDO REMANESCENTE (SR)  =  (VP − VF) × PR  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_NAVY_SR)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3

        registros = sr if isinstance(sr, list) else ([sr] if sr else [])
        registros = [r for r in registros if r]

        if not registros:
            ws.merge_cells(f"A{row}:E{row}")
            c = ws.cell(row=row, column=1, value="Nenhum dado de SR salvo.")
            c.font = _font(italic=True)
            c.alignment = _align("center")
        elif periodo:
            # Modo período único — exibe detalhado
            item = registros[0]
            vp   = _to_float(item.get("vp"))
            vf   = _to_float(item.get("vf"))
            pr_v = _to_float(item.get("pr"))
            sr_v = _to_float(item.get("sr"))
            diff = vp - vf

            _apply_header_row(ws, row,
                ["VP (m³)", "VF (m³)", "Diferença (m³)", "PR (R$/m³)", "SR (R$)"],
                [20, 20, 20, 20, 22], _NAVY_SR)
            row += 1
            _apply_data_row(ws, row,
                [vp, vf, diff, pr_v, sr_v],
                [_VOL, _VOL, _VOL, _BRL, _BRL])
            row += 2

            # Card resultado
            ws.merge_cells(f"A{row}:E{row}")
            lbl = ws.cell(row=row, column=1, value="📈  SR  =  (VP − VF) × PR")
            bg = _GREEN if sr_v >= 0 else _RED
            lbl.fill = _fill(bg)
            lbl.font = _font(bold=True, color=_HEADER_FG, size=13)
            lbl.alignment = _align("left")
            lbl.border = _border()
            ws.row_dimensions[row].height = 28
            row += 1

            ws.merge_cells(f"A{row}:E{row}")
            v = ws.cell(row=row, column=1, value=sr_v)
            v.number_format = _BRL
            v.fill = _fill(bg)
            v.font = _font(bold=True, color=_HEADER_FG, size=22)
            v.alignment = _align("center")
            v.border = _border()
            ws.row_dimensions[row].height = 44
        else:
            # Modo lista — todos os períodos
            _apply_header_row(ws, row,
                ["Período", "VP (m³)", "VF (m³)", "PR (R$/m³)", "SR (R$)"],
                [18, 20, 20, 20, 22], _NAVY_SR)
            row += 1
            for i, item in enumerate(registros):
                _apply_data_row(ws, row,
                    [item.get("periodo", ""), _to_float(item.get("vp")),
                     _to_float(item.get("vf")), _to_float(item.get("pr")),
                     _to_float(item.get("sr"))],
                    ["@", _VOL, _VOL, _BRL, _BRL],
                    alternate=(i % 2 == 1))
                row += 1

            # Linha de total
            if len(registros) > 1:
                row += 1
                total_sr = sum(_to_float(r.get("sr")) for r in registros)
                ws.merge_cells(f"A{row}:D{row}")
                lbl = ws.cell(row=row, column=1, value="TOTAL SR")
                bg = _GREEN if total_sr >= 0 else _RED
                lbl.fill = _fill(bg)
                lbl.font = _font(bold=True, color=_HEADER_FG)
                lbl.alignment = _align("right")
                lbl.border = _border()
                v = ws.cell(row=row, column=5, value=total_sr)
                v.number_format = _BRL
                v.fill = _fill(bg)
                v.font = _font(bold=True, color=_HEADER_FG)
                v.alignment = _align("right")
                v.border = _border()

        ws.column_dimensions["A"].width = 20
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 20
        ws.column_dimensions["D"].width = 20
        ws.column_dimensions["E"].width = 22

    # ── Sheet 8: PR Final ────────────────────────────────────────────────────

    @staticmethod
    def _sheet_pr(wb, pr: dict | list[dict] | None, periodo: str | None):
        _CYAN = "0E7490"
        ws = wb.create_sheet("💡 PR Final")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:D1")
        t = ws["A1"]
        t.value = f"PR FINAL  =  (SGR + SR) / VP  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_CYAN)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3

        if periodo is None:
            registros = pr if isinstance(pr, list) else ([pr] if pr else [])
            _apply_header_row(ws, row,
                ["Período", "SGR/SCG (R$)", "SR (R$)", "VP (m³)", "PR (R$/m³)", "Atualizado"],
                [18, 18, 18, 18, 18, 20], _CYAN)
            row += 1
            if not registros:
                ws.cell(row=row, column=1, value="Nenhum resultado PR salvo no banco.")
                return
            for i, item in enumerate(registros):
                _apply_data_row(ws, row,
                    [item.get("periodo", ""), item.get("scg", 0.0), item.get("sr", 0.0),
                     item.get("vp", 0.0), item.get("pr", 0.0),
                     str(item.get("data_atualizacao", ""))[:16]],
                    ["@", _BRL, _BRL, _VOL, _VOL4, "@"],
                    alternate=(i % 2 == 1))
                row += 1
            return

        data = pr if isinstance(pr, dict) else {}

        scg = _to_float(data.get("scg"))
        sr  = _to_float(data.get("sr"))
        vp  = _to_float(data.get("vp"))
        pr_val = _to_float(data.get("pr")) if data else (0.0 if vp == 0 else (scg + sr) / vp)

        linhas = [
            ("💼  SGR / SCG  (Saldo Gráfico Regulatório)", scg, _PURPLE,  "+"),
            ("📈  SR          (Saldo Remanescente)",         sr,  _GREEN,   "+"),
            ("🔢  VP          (Volume Produzido, m³)",       vp,  _BLUE,    "÷"),
        ]

        _apply_header_row(ws, row,
            ["Componente", "Valor", "Op.", "Obs."],
            [38, 22, 8, 30], _CYAN)
        row += 1

        fmts_by_label = [_BRL, _BRL, _VOL]
        for i, ((label, val, bg_mod, op), fmt) in enumerate(zip(linhas, fmts_by_label)):
            for col in range(1, 5):
                c = ws.cell(row=row, column=col)
                c.fill = _fill(_ROW_ALT if i % 2 else _ROW_NORM)
                c.border = _border()
            ws.cell(row=row, column=1, value=label).font = _font()
            ws.cell(row=row, column=1).alignment = _align("left")
            v = ws.cell(row=row, column=2, value=val)
            v.number_format = fmt
            v.alignment = _align("right")
            ws.cell(row=row, column=3, value=op).alignment = _align("center")
            row += 1

        row += 1

        ws.merge_cells(f"A{row}:D{row}")
        lbl = ws.cell(row=row, column=1, value="💡  PR  =  (SGR + SR)  /  VP")
        bg_pr = _GREEN if pr_val > 0 else (_RED if pr_val < 0 else _GOLD)
        lbl.fill = _fill(bg_pr)
        lbl.font = _font(bold=True, color=_HEADER_FG, size=13)
        lbl.alignment = _align("left")
        lbl.border = _border()
        ws.row_dimensions[row].height = 26
        row += 1

        ws.merge_cells(f"A{row}:D{row}")
        v = ws.cell(row=row, column=1, value=pr_val)
        v.number_format = _VOL4
        v.fill = _fill(bg_pr)
        v.font = _font(bold=True, color=_HEADER_FG, size=22)
        v.alignment = _align("center")
        v.border = _border()
        ws.row_dimensions[row].height = 44
        row += 2

        _section_title(ws, row, "  FÓRMULA OFICIAL", 4, "2C3E50")
        row += 1
        ws.merge_cells(f"A{row}:D{row}")
        c = ws.cell(row=row, column=1, value="PR  =  (SGR + SR)  /  VP   |   PR = 0 quando VP = 0")
        c.fill = _fill(_ROW_ALT)
        c.font = _font(italic=True, size=11)
        c.alignment = _align("center")
        c.border = _border()

        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 30

    # ── Sheet 9: Progresso por Etapa ───────────────────────────────────────

    @staticmethod
    def _sheet_pv(wb, pv: dict | list[dict] | None, periodo: str | None):
        _GREEN_DARK = "1D8348"
        ws = wb.create_sheet("💰 PV Final")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:D1")
        t = ws["A1"]
        t.value = f"PV FINAL  =  PMPV + PR  |  Período: {periodo or 'N/D'}"
        t.fill = _fill(_GREEN_DARK)
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3

        if periodo is None:
            registros = pv if isinstance(pv, list) else ([pv] if pv else [])
            _apply_header_row(ws, row,
                ["Período", "PMPV (R$/m³)", "PR (R$/m³)", "PV (R$/m³)", "Atualizado"],
                [18, 20, 20, 20, 20], _GREEN_DARK)
            row += 1
            if not registros:
                ws.cell(row=row, column=1, value="Nenhum resultado PV salvo no banco.")
                return
            for i, item in enumerate(registros):
                _apply_data_row(ws, row,
                    [item.get("periodo", ""), item.get("pmpv", 0.0), item.get("pr", 0.0),
                     item.get("pv", 0.0), str(item.get("data_atualizacao", ""))[:16]],
                    ["@", _VOL4, _VOL4, _VOL4, "@"],
                    alternate=(i % 2 == 1))
                row += 1
            return

        data = pv if isinstance(pv, dict) else {}
        pmpv = _to_float(data.get("pmpv"))
        pr = _to_float(data.get("pr"))
        pv_val = _to_float(data.get("pv")) if data else (pmpv + pr)

        linhas = [
            ("📊  PMPV  (Preço Médio Ponderado)", pmpv, _TEAL, "+"),
            ("💡  PR    (Preço Regulatório Final)", pr, _BLUE, "+"),
        ]

        _apply_header_row(ws, row, ["Componente", "Valor", "Op.", "Obs."], [38, 22, 8, 30], _GREEN_DARK)
        row += 1

        for i, (label, val, _bg_mod, op) in enumerate(linhas):
            for col in range(1, 5):
                c = ws.cell(row=row, column=col)
                c.fill = _fill(_ROW_ALT if i % 2 else _ROW_NORM)
                c.border = _border()
            ws.cell(row=row, column=1, value=label).font = _font()
            ws.cell(row=row, column=1).alignment = _align("left")
            v = ws.cell(row=row, column=2, value=val)
            v.number_format = _VOL4
            v.alignment = _align("right")
            ws.cell(row=row, column=3, value=op).alignment = _align("center")
            row += 1

        row += 1
        ws.merge_cells(f"A{row}:D{row}")
        lbl = ws.cell(row=row, column=1, value="💰  PV  =  PMPV + PR")
        bg_pv = _GREEN if pv_val > 0 else (_RED if pv_val < 0 else _GOLD)
        lbl.fill = _fill(bg_pv)
        lbl.font = _font(bold=True, color=_HEADER_FG, size=13)
        lbl.alignment = _align("left")
        lbl.border = _border()
        ws.row_dimensions[row].height = 26
        row += 1

        ws.merge_cells(f"A{row}:D{row}")
        v = ws.cell(row=row, column=1, value=pv_val)
        v.number_format = _VOL4
        v.fill = _fill(bg_pv)
        v.font = _font(bold=True, color=_HEADER_FG, size=22)
        v.alignment = _align("center")
        v.border = _border()
        ws.row_dimensions[row].height = 44
        row += 2

        _section_title(ws, row, "  FÓRMULA OFICIAL", 4, "2C3E50")
        row += 1
        ws.merge_cells(f"A{row}:D{row}")
        c = ws.cell(row=row, column=1, value="PV  =  PMPV  +  PR")
        c.fill = _fill(_ROW_ALT)
        c.font = _font(italic=True, size=11)
        c.alignment = _align("center")
        c.border = _border()

        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 22
        ws.column_dimensions["C"].width = 10
        ws.column_dimensions["D"].width = 30

    # ── Sheet 10: Progresso por Etapa ──────────────────────────────────────

    @staticmethod
    def _sheet_progresso(wb, execucoes: list[dict], periodo: str | None):
        ws = wb.create_sheet("📈 Progresso Execuções")
        ws.sheet_view.showGridLines = False

        ws.merge_cells("A1:F1")
        t = ws["A1"]
        t.value = f"PROGRESSÃO DO EXCEL FINAL  |  Período: {periodo or 'Todos'}"
        t.fill = _fill("2C3E50")
        t.font = _font(bold=True, size=14, color=_HEADER_FG)
        t.alignment = _align("center")
        ws.row_dimensions[1].height = 30

        row = 3
        _apply_header_row(
            ws,
            row,
            ["Sessão", "Período", "Etapa", "Execução", "Atualizado", "Arquivo"],
            [24, 14, 22, 12, 20, 46],
            "2C3E50",
        )
        row += 1

        if not execucoes:
            ws.cell(
                row=row,
                column=1,
                value="Nenhuma execução de etapa registrada no fluxo cumulativo.",
            )
            return

        for i, item in enumerate(execucoes):
            _apply_data_row(
                ws,
                row,
                [
                    item.get("nome_sessao", ""),
                    item.get("periodo", ""),
                    item.get("etapa", ""),
                    int(item.get("execucao", 0) or 0),
                    str(item.get("data_atualizacao", ""))[:19],
                    item.get("caminho_arquivo", ""),
                ],
                ["@", "@", "@", _NUM, "@", "@"],
                alternate=(i % 2 == 1),
            )
            row += 1

    # ── Sheet 11: Dashboard Visual ───────────────────────────────────────────

    @staticmethod
    def _sheet_dashboard(
        wb,
        cons: dict | None,
        cons_periodos: list[dict],
        pr: dict | None,
        pv: dict | None,
        sr: dict | None,
        periodo: str | None,
    ):
        ws = wb.create_sheet("📊 Dashboard")
        ws.sheet_view.showGridLines   = False
        ws.sheet_view.showRowColHeaders = False
        ws.sheet_properties.tabColor  = "0D2137"
        ws.sheet_view.zoomScale       = 90

        # ── Paleta Dashboard ──────────────────────────────────────────────────
        BG         = "F0F4F8"   # fundo geral (cinza muito claro)
        HDR1       = "0D2137"   # header topo escuro
        HDR2       = "1A3A5C"   # header 2ª linha
        CARD_SALDO = "0A3D62"   # Saldo a Recuperar — azul petróleo
        CARD_SALDO2= "0C4A76"   # sub-linha do card
        CARD_SCG   = "154360"   # SCG — azul mais claro
        CARD_SCG2  = "1A5276"
        CARD_PR    = "0E6252"   # Parcela PR — verde escuro
        CARD_PR2   = "117A65"
        CARD_PV    = "1D4E1F"   # PV Final — verde floresta
        CARD_PV2   = "1E8449"
        CARD_RPV   = "3D1A6E"   # RPV — roxo escuro
        CARD_RPV2  = "5B2C6F"
        CARD_RET   = "7E2000"   # RET — castanho/laranja
        CARD_RET2  = "A04000"
        CARD_RP    = "0B3954"   # RP — azul escuro
        CARD_RP2   = "1A5276"
        CARD_SR    = "1B1F3B"   # SR — azul noite
        CARD_SR2   = "2C3E6B"
        GOLD       = "F4D03F"   # valor destaque amarelo
        WHITE      = "FFFFFF"
        MUTED      = "B0BEC5"   # texto secundário
        SEP        = "DDE3EC"   # linha separadora

        # ── Layout de colunas ─────────────────────────────────────────────────
        # A=marg | B:C=card1 | D=gap | E:F=card2 | G=gap | H:I=card3 | J=gap | K:L=card4 | M=marg
        col_cfg = [
            ("A", 1.2),
            ("B", 14.0), ("C", 14.0),
            ("D", 1.8),
            ("E", 14.0), ("F", 14.0),
            ("G", 1.8),
            ("H", 14.0), ("I", 14.0),
            ("J", 1.8),
            ("K", 14.0), ("L", 14.0),
            ("M", 1.2),
        ]
        for col_ltr, w in col_cfg:
            ws.column_dimensions[col_ltr].width = w

        # col index: A=1 B=2 C=3 D=4 E=5 F=6 G=7 H=8 I=9 J=10 K=11 L=12 M=13
        CARD_STARTS = [2, 5, 8, 11]   # B, E, H, K
        FULL_START  = 2                # B
        FULL_END    = 12               # L

        # ── Dados ─────────────────────────────────────────────────────────────
        d     = cons or {}
        cgr   = _to_float(d.get("cgr"))
        cgf   = _to_float(d.get("cgf"))
        rpv   = _to_float(d.get("rpv", cgr - cgf))
        ret   = _to_float(d.get("ret"))
        rp    = _to_float(d.get("rp"))
        scg   = _to_float(d.get("scg", rpv + ret + rp))
        pr_d  = pr or {}
        sr_d  = sr or {}
        pv_d  = pv or {}
        pr_v  = _to_float(pr_d.get("pr"))
        pv_v  = _to_float(pv_d.get("pv"))
        vp_v  = _to_float(pr_d.get("vp") or sr_d.get("vp"))
        sr_v  = _to_float(sr_d.get("sr"))
        saldo = scg + sr_v

        # ── Helpers ───────────────────────────────────────────────────────────
        W  = Border(
            left=Side(style="thin", color=WHITE),
            right=Side(style="thin", color=WHITE),
            top=Side(style="thin", color=WHITE),
            bottom=Side(style="thin", color=WHITE),
        )
        NONE_BDR = Border()

        def _rh(r, h): ws.row_dimensions[r].height = h

        def _bg_row(r, h, bg, c1=1, c2=13):
            _rh(r, h)
            for ci in range(c1, c2 + 1):
                ws.cell(row=r, column=ci).fill = _fill(bg)

        def _merge(r, c1, c2, value, bg, fnt, align_h="center", fmt="@", row_h=None):
            if c1 != c2:
                ws.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
            cell = ws.cell(row=r, column=c1, value=value)
            cell.fill      = _fill(bg)
            cell.font      = fnt
            cell.alignment = _align(align_h, "center")
            cell.border    = W
            if fmt != "@":
                cell.number_format = fmt
            if row_h:
                _rh(r, row_h)
            return cell

        def card(row, col, label, main_val, main_fmt, c_dark, c_lite,
                 s1_lbl="", s1_val=None, s1_fmt=_BRL,
                 s2_lbl="", s2_val=None, s2_fmt=_BRL):
            """Desenha um card de métrica em 2 colunas × 7 linhas."""
            c2 = col + 1

            # R+0  label bar (dark)
            _merge(row,   col, c2, f"  {label}",
                   c_dark, _font(bold=True, size=10, color=WHITE), "left", "@", 18)

            # R+1  spacer
            for ci in (col, c2):
                cc = ws.cell(row=row+1, column=ci)
                cc.fill = _fill(c_dark); cc.border = W
            _rh(row+1, 6)

            # R+2  main value (grande)
            _merge(row+2, col, c2, main_val,
                   c_dark, _font(bold=True, size=22, color=WHITE), "center", main_fmt, 36)

            # R+3  spacer
            for ci in (col, c2):
                cc = ws.cell(row=row+3, column=ci)
                cc.fill = _fill(c_dark); cc.border = W
            _rh(row+3, 6)

            # R+4  sub 1
            lc = ws.cell(row=row+4, column=col,  value=f"  {s1_lbl}" if s1_lbl else "")
            vc = ws.cell(row=row+4, column=c2,   value=s1_val)
            for cc, al in ((lc, "left"), (vc, "right")):
                cc.fill      = _fill(c_lite)
                cc.font      = _font(size=9, color=MUTED if not s1_lbl else GOLD if cc is vc else "D0E8F5")
                cc.alignment = _align(al, "center")
                cc.border    = W
            if s1_val is not None and s1_fmt != "@":
                vc.number_format = s1_fmt
            lc.font = _font(size=9, color="D0E8F5")
            vc.font = _font(bold=True, size=9, color=GOLD)
            _rh(row+4, 17)

            # R+5  sub 2
            lc2 = ws.cell(row=row+5, column=col, value=f"  {s2_lbl}" if s2_lbl else "")
            vc2 = ws.cell(row=row+5, column=c2,  value=s2_val)
            for cc, al in ((lc2, "left"), (vc2, "right")):
                cc.fill      = _fill(c_lite)
                cc.alignment = _align(al, "center")
                cc.border    = W
            lc2.font = _font(size=9, color="D0E8F5")
            vc2.font = _font(bold=True, size=9, color=GOLD)
            if s2_val is not None and s2_fmt != "@":
                vc2.number_format = s2_fmt
            _rh(row+5, 17)

            # R+6  bottom accent strip
            for ci in (col, c2):
                cc = ws.cell(row=row+6, column=ci)
                cc.fill = _fill("091520"); cc.border = W
            _rh(row+6, 4)

        # ══════════════════════════════════════════════════════════════════════
        # HEADER
        # ══════════════════════════════════════════════════════════════════════
        # R1 — Banner principal
        _bg_row(1, 46, HDR1)
        _merge(1, FULL_START, 9,
               "    ARPE  ·  CONTA GRÁFICA  ·  TARIFA DE GÁS CANALIZADO",
               HDR1, _font(bold=True, size=18, color=WHITE), "left")
        # Badge CG versão (canto direito)
        _merge(1, 10, FULL_END,
               f"  {periodo or 'GERAL'}  ",
               GOLD, _font(bold=True, size=14, color="0D2137"), "right")

        # R2 — Subtítulo
        _bg_row(2, 24, HDR2)
        _merge(2, FULL_START, FULL_END,
               f"    Dashboard Executivo  ·  Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
               HDR2, _font(size=10, color="7FB3D3", italic=True), "left")

        # R3 — Barra colorida decorativa (accent azul claro)
        _bg_row(3, 4, "2E86C1")

        # R4 — Espaço
        _bg_row(4, 10, BG)

        # ══════════════════════════════════════════════════════════════════════
        # FAIXA DE CARDS 1 — SALDO A RECUPERAR | SCG | PR | PV
        # ══════════════════════════════════════════════════════════════════════
        _bg_row(5,  2, BG)   # gap antes dos cards
        R = 6

        card(R, CARD_STARTS[0],
             "SALDO A RECUPERAR", saldo, _BRL, CARD_SALDO, CARD_SALDO2,
             "SCG Atualizado",        scg,   _BRL,
             "Saldo Remanescente SR", sr_v,  _BRL)

        card(R, CARD_STARTS[1],
             "SALDO CONTA GRÁFICA — SCG", scg, _BRL, CARD_SCG, CARD_SCG2,
             "RPV (Preço Venda)", rpv, _BRL,
             "RET + RP",          ret + rp, _BRL)

        card(R, CARD_STARTS[2],
             "PARCELA DE RECUPERAÇÃO", pr_v, _VOL4, CARD_PR, CARD_PR2,
             "Volume Prospectivo (m³)", vp_v, _VOL,
             "PR = Saldo ÷ Volume",     None, "@")

        card(R, CARD_STARTS[3],
             "PREÇO FINAL — PV", pv_v, _VOL4, CARD_PV, CARD_PV2,
             "PMPV (R$/m³)",    None, "@",
             "PR  (R$/m³)",      pr_v, _VOL4)

        # fill gap columns entre cards (cor BG)
        for gap_col in (4, 7, 10):
            for rr in range(R, R + 7):
                ws.cell(row=rr, column=gap_col).fill = _fill(BG)
                ws.cell(row=rr, column=1).fill       = _fill(BG)
                ws.cell(row=rr, column=13).fill      = _fill(BG)

        # ══════════════════════════════════════════════════════════════════════
        # FAIXA DE CARDS 2 — CGR | RPV | RET | SR
        # ══════════════════════════════════════════════════════════════════════
        R2 = R + 8   # gap de 1 linha
        _bg_row(R + 7, 10, BG)

        card(R2, CARD_STARTS[0],
             "CGR — AUDITORIA XML", cgr, _BRL, "0A3D62", "0C4A76",
             "Total NF-e + CT-e", cgr, _BRL,
             "", None, "@")

        card(R2, CARD_STARTS[1],
             "RPV  =  CGR  −  CGF", rpv, _BRL, CARD_RPV, CARD_RPV2,
             "CGR (Auditoria)",      cgr, _BRL,
             "CGF (Volume Fat.)",    cgf, _BRL)

        card(R2, CARD_STARTS[2],
             "RET — ENCARGOS TRANSP.", ret, _BRL, CARD_RET, CARD_RET2,
             "EAT (bruto)",           ret, _BRL,
             "PIS/COFINS deduzido",   None, "@")

        card(R2, CARD_STARTS[3],
             "SALDO REMANESCENTE SR", sr_v, _BRL, CARD_SR, CARD_SR2,
             "RP (Conciliação)",      rp,  _BRL,
             "CGF (Volume Fat.)",     cgf, _BRL)

        for gap_col in (4, 7, 10):
            for rr in range(R2, R2 + 7):
                ws.cell(row=rr, column=gap_col).fill = _fill(BG)
                ws.cell(row=rr, column=1).fill       = _fill(BG)
                ws.cell(row=rr, column=13).fill      = _fill(BG)

        # ══════════════════════════════════════════════════════════════════════
        # SEPARADOR + TÍTULO DO GRÁFICO
        # ══════════════════════════════════════════════════════════════════════
        R3 = R2 + 8
        _bg_row(R3,     10, BG)
        _bg_row(R3 + 1, 3,  "2E86C1")   # accent stripe

        R4 = R3 + 2
        _bg_row(R4, 24, HDR1)
        _merge(R4, FULL_START, FULL_END,
               "    PARCELA DE RECUPERAÇÃO (R$/m³)  ·  HISTÓRICO POR PERÍODO",
               HDR1, _font(bold=True, size=12, color=WHITE), "left")

        # ── Tabela de dados para o gráfico ────────────────────────────────────
        R5 = R4 + 1
        # cabeçalho da tabela (tamanho mínimo, cor discreta)
        for ci, lbl in ((2, "Período"), (3, "PR (R$/m³)")):
            cc = ws.cell(row=R5, column=ci, value=lbl)
            cc.fill = _fill("E8EEF4")
            cc.font = _font(bold=True, size=8, color="5A7A9A")
            cc.alignment = _align("center")
        _rh(R5, 12)

        periodos_g = cons_periodos[-14:] if cons_periodos else []
        dr = R5 + 1
        for item in periodos_g:
            p_txt  = item.get("periodo", "")
            p_pr   = _to_float(item.get("pr")) if item.get("pr") else (
                _to_float(item.get("scg", 0)) / max(_to_float(item.get("vp", 1)), 1)
            )
            ws.cell(row=dr, column=2, value=p_txt).fill  = _fill("F5F8FA")
            vc = ws.cell(row=dr, column=3, value=p_pr)
            vc.fill = _fill("F5F8FA"); vc.number_format = _VOL4
            _rh(dr, 11); dr += 1

        if not periodos_g and pr_v:
            ws.cell(row=dr, column=2, value=periodo or "Atual")
            ws.cell(row=dr, column=3, value=pr_v).number_format = _VOL4
            dr += 1

        data_end = dr - 1

        # ── Gráfico de linha ──────────────────────────────────────────────────
        if data_end > R5 + 1:
            from openpyxl.chart.label import DataLabel
            chart = LineChart()
            chart.title  = None
            chart.style  = 2
            chart.legend = None
            chart.y_axis.numFmt          = '#,##0.0000'
            chart.y_axis.delete          = False
            chart.y_axis.majorGridlines  = None
            chart.x_axis.tickLblPos      = "low"
            chart.x_axis.delete          = False
            chart.height = 14
            chart.width  = 30

            data_ref = Reference(ws, min_col=3, min_row=R5 + 1, max_row=data_end)
            chart.add_data(data_ref)
            cats = Reference(ws, min_col=2, min_row=R5 + 1, max_row=data_end)
            chart.set_categories(cats)

            s = chart.series[0]
            s.graphicalProperties.line.solidFill        = "2E86C1"
            s.graphicalProperties.line.width            = 28000
            s.marker.symbol                              = "circle"
            s.marker.size                                = 7
            s.marker.graphicalProperties.solidFill      = "F4D03F"
            s.marker.graphicalProperties.line.solidFill = "2E86C1"

            ws.add_chart(chart, f"B{data_end + 2}")

        # ══════════════════════════════════════════════════════════════════════
        # FÓRMULAS OFICIAIS (rodapé informativo)
        # ══════════════════════════════════════════════════════════════════════
        foot_r = data_end + 22
        _bg_row(foot_r, 3, "0D2137")
        _merge(foot_r, FULL_START, FULL_END,
               "   SCG = RPV + RET + RP   |   RPV = CGR − CGF   |   "
               "PR = (SCG + SR) ÷ VP   |   PV = PMPV + PR   |   "
               f"ARPE · {datetime.now().year}",
               "0D2137", _font(italic=True, size=9, color="5A7A9A"), "center")
