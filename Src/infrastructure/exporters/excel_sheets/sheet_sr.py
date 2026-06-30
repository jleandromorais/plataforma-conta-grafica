from __future__ import annotations

from Src.infrastructure.exporters.excel_styles import (
    fill as _fill, font as _font, border as _border, align as _align,
    to_float as _to_float,
)
from ._helpers import (
    BRL, VOL, VOL4, GREEN, RED, HEADER_FG,
    apply_header_row, apply_data_row,
)


def sheet_sr(wb, sr: dict | list[dict] | None, periodo: str | None) -> None:
    _NAVY_SR = "1B2A4A"
    ws = wb.create_sheet("📈 SR")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:E1")
    t = ws["A1"]
    t.value = f"SALDO REMANESCENTE (SR)  =  (VP − VF) × PR  |  Período: {periodo or 'N/D'}"
    t.fill = _fill(_NAVY_SR)
    t.font = _font(bold=True, size=14, color=HEADER_FG)
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
        item = registros[0]
        vp   = _to_float(item.get("vp"))
        vf   = _to_float(item.get("vf"))
        pr_v = _to_float(item.get("pr"))
        sr_v = _to_float(item.get("sr"))

        apply_header_row(ws, row,
            ["VP (m³)", "VF (m³)", "Diferença (m³)", "PR (R$/m³)", "SR (R$)"],
            [20, 20, 20, 20, 22], _NAVY_SR)
        row += 1
        apply_data_row(ws, row,
            [vp, vf, vp - vf, pr_v, sr_v],
            [VOL, VOL, VOL, BRL, BRL])
        row += 2

        ws.merge_cells(f"A{row}:E{row}")
        lbl = ws.cell(row=row, column=1, value="📈  SR  =  (VP − VF) × PR")
        bg = GREEN if sr_v >= 0 else RED
        lbl.fill = _fill(bg)
        lbl.font = _font(bold=True, color=HEADER_FG, size=13)
        lbl.alignment = _align("left")
        lbl.border = _border()
        ws.row_dimensions[row].height = 28
        row += 1

        ws.merge_cells(f"A{row}:E{row}")
        v = ws.cell(row=row, column=1, value=sr_v)
        v.number_format = BRL
        v.fill = _fill(bg)
        v.font = _font(bold=True, color=HEADER_FG, size=22)
        v.alignment = _align("center")
        v.border = _border()
        ws.row_dimensions[row].height = 44
    else:
        apply_header_row(ws, row,
            ["Período", "VP (m³)", "VF (m³)", "PR (R$/m³)", "SR (R$)"],
            [18, 20, 20, 20, 22], _NAVY_SR)
        row += 1
        for i, item in enumerate(registros):
            apply_data_row(ws, row,
                [item.get("periodo", ""), _to_float(item.get("vp")),
                 _to_float(item.get("vf")), _to_float(item.get("pr")),
                 _to_float(item.get("sr"))],
                ["@", VOL, VOL, BRL, BRL],
                alternate=(i % 2 == 1))
            row += 1

        if len(registros) > 1:
            row += 1
            total_sr = sum(_to_float(r.get("sr")) for r in registros)
            ws.merge_cells(f"A{row}:D{row}")
            lbl = ws.cell(row=row, column=1, value="TOTAL SR")
            bg = GREEN if total_sr >= 0 else RED
            lbl.fill = _fill(bg)
            lbl.font = _font(bold=True, color=HEADER_FG)
            lbl.alignment = _align("right")
            lbl.border = _border()
            v = ws.cell(row=row, column=5, value=total_sr)
            v.number_format = BRL
            v.fill = _fill(bg)
            v.font = _font(bold=True, color=HEADER_FG)
            v.alignment = _align("right")
            v.border = _border()

    for col, w in zip("ABCDE", [20, 20, 20, 20, 22]):
        ws.column_dimensions[col].width = w
