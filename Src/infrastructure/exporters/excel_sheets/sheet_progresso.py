from __future__ import annotations

from Src.infrastructure.exporters.excel_styles import (
    fill as _fill, font as _font, align as _align, to_float as _to_float,
)
from ._helpers import NUM, HEADER_FG, apply_header_row, apply_data_row


def sheet_progresso(wb, execucoes: list[dict], periodo: str | None) -> None:
    ws = wb.create_sheet("📈 Progresso Execuções")
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:F1")
    t = ws["A1"]
    t.value = f"PROGRESSÃO DO EXCEL FINAL  |  Período: {periodo or 'Todos'}"
    t.fill = _fill("2C3E50")
    t.font = _font(bold=True, size=14, color=HEADER_FG)
    t.alignment = _align("center")
    ws.row_dimensions[1].height = 30

    row = 3
    apply_header_row(
        ws, row,
        ["Sessão", "Período", "Etapa", "Execução", "Atualizado", "Arquivo"],
        [24, 14, 22, 12, 20, 46],
        "2C3E50",
    )
    row += 1

    if not execucoes:
        ws.cell(row=row, column=1,
                value="Nenhuma execução de etapa registrada no fluxo cumulativo.")
        return

    for i, item in enumerate(execucoes):
        apply_data_row(
            ws, row,
            [
                item.get("nome_sessao", ""),
                item.get("periodo", ""),
                item.get("etapa", ""),
                int(item.get("execucao", 0) or 0),
                str(item.get("data_atualizacao", ""))[:19],
                item.get("caminho_arquivo", ""),
            ],
            ["@", "@", "@", NUM, "@", "@"],
            alternate=(i % 2 == 1),
        )
        row += 1
