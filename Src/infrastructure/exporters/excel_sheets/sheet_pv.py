from __future__ import annotations

from Src.infrastructure.exporters.excel_styles import (
    fill as _fill, font as _font, border as _border, align as _align,
    to_float as _to_float,
)
from ._helpers import (
    BRL, VOL, VOL4, GREEN, RED, GOLD, BLUE, TEAL, HEADER_FG,
    ROW_ALT, ROW_NORM, apply_header_row, apply_data_row, section_title,
)


def sheet_pv(wb, pv: dict | list[dict] | None, periodo: str | None) -> None:
    _GREEN_DARK = "1D8348"
    ws = wb.create_sheet("💰 PV Final")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:D1")
    t = ws["A1"]
    t.value = f"PV FINAL  =  PMPV + PR  |  Período: {periodo or 'N/D'}"
    t.fill = _fill(_GREEN_DARK)
    t.font = _font(bold=True, size=14, color=HEADER_FG)
    t.alignment = _align("center")
    ws.row_dimensions[1].height = 30

    row = 3

    if periodo is None:
        registros = pv if isinstance(pv, list) else ([pv] if pv else [])
        apply_header_row(ws, row,
            ["Período", "PMPV (R$/m³)", "PR (R$/m³)", "PV (R$/m³)", "Atualizado"],
            [18, 20, 20, 20, 20], _GREEN_DARK)
        row += 1
        if not registros:
            ws.cell(row=row, column=1, value="Nenhum resultado PV salvo no banco.")
            return
        for i, item in enumerate(registros):
            apply_data_row(ws, row,
                [item.get("periodo", ""), item.get("pmpv", 0.0), item.get("pr", 0.0),
                 item.get("pv", 0.0), str(item.get("data_atualizacao", ""))[:16]],
                ["@", VOL4, VOL4, VOL4, "@"],
                alternate=(i % 2 == 1))
            row += 1
        return

    data  = pv if isinstance(pv, dict) else {}
    pmpv  = _to_float(data.get("pmpv"))
    pr    = _to_float(data.get("pr"))
    pv_val = _to_float(data.get("pv")) if data else (pmpv + pr)

    linhas = [
        ("📊  PMPV  (Preço Médio Ponderado)",  pmpv, TEAL, "+"),
        ("💡  PR    (Preço Regulatório Final)", pr,   BLUE, "+"),
    ]

    apply_header_row(ws, row, ["Componente", "Valor", "Op.", "Obs."], [38, 22, 8, 30], _GREEN_DARK)
    row += 1

    for i, (label, val, _bg_mod, op) in enumerate(linhas):
        for col in range(1, 5):
            c = ws.cell(row=row, column=col)
            c.fill = _fill(ROW_ALT if i % 2 else ROW_NORM)
            c.border = _border()
        ws.cell(row=row, column=1, value=label).font = _font()
        ws.cell(row=row, column=1).alignment = _align("left")
        v = ws.cell(row=row, column=2, value=val)
        v.number_format = VOL4
        v.alignment = _align("right")
        ws.cell(row=row, column=3, value=op).alignment = _align("center")
        row += 1

    row += 1
    ws.merge_cells(f"A{row}:D{row}")
    lbl = ws.cell(row=row, column=1, value="💰  PV  =  PMPV + PR")
    bg_pv = GREEN if pv_val > 0 else (RED if pv_val < 0 else GOLD)
    lbl.fill = _fill(bg_pv)
    lbl.font = _font(bold=True, color=HEADER_FG, size=13)
    lbl.alignment = _align("left")
    lbl.border = _border()
    ws.row_dimensions[row].height = 26
    row += 1

    ws.merge_cells(f"A{row}:D{row}")
    v = ws.cell(row=row, column=1, value=pv_val)
    v.number_format = VOL4
    v.fill = _fill(bg_pv)
    v.font = _font(bold=True, color=HEADER_FG, size=22)
    v.alignment = _align("center")
    v.border = _border()
    ws.row_dimensions[row].height = 44
    row += 2

    section_title(ws, row, "  FÓRMULA OFICIAL", 4, "2C3E50")
    row += 1
    ws.merge_cells(f"A{row}:D{row}")
    c = ws.cell(row=row, column=1, value="PV  =  PMPV  +  PR")
    c.fill = _fill(ROW_ALT)
    c.font = _font(italic=True, size=11)
    c.alignment = _align("center")
    c.border = _border()

    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 10
    ws.column_dimensions["D"].width = 30
