import os
from datetime import datetime
from typing import Dict

"""
Esse arquivo (`excel_handler_pmpv.py`) serve como um "exportador" dos resultados do módulo PMPV para arquivos Excel (.xlsx).

Ele contém a classe `ExcelHandlerPMPV`, que possui métodos para criar planilhas do Excel de forma programática, preenchendo abas com os dados por mês e um resumo dos resultados principais dos cálculos de PMPV.

O principal objetivo dele é permitir que, depois do processamento dos dados e das análises/tratamentos no backend, o usuário possa exportar tudo em um formato amigável (Excel), já pronto para consulta, impressão ou análise posterior — organizando as informações em diferentes abas, ajustando formatação e facilitando a visualização dos resultados.

Resumindo, ele automatiza a geração do arquivo Excel do relatório PMPV, incluindo controle para nomes de arquivos, sobreescrita, formato visual e abertura automática do arquivo gerado.
"""


import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


class ExcelHandlerPMPV:
    @staticmethod
    def exportar_trimestre(dados_por_mes: Dict, resultado: Dict, nome_arquivo: str = None) -> str:
        if nome_arquivo is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"Relatorio_PMPV_{timestamp}.xlsx"

        nome_base = nome_arquivo.replace(".xlsx", "")
        contador = 1
        nome_final = nome_arquivo

        while True:
            try:
                with open(nome_final, "w"):
                    pass
                os.remove(nome_final)
                break
            except (PermissionError, IOError):
                nome_final = f"{nome_base}_{contador}.xlsx"
                contador += 1
                if contador > 100:
                    nome_final = f"{nome_base}_{datetime.now().strftime('%H%M%S%f')}.xlsx"
                    break

        wb = openpyxl.Workbook()
        if "Sheet" in wb.sheetnames:
            wb.remove(wb["Sheet"])

        for nome_aba, dados in dados_por_mes.items():
            ExcelHandlerPMPV._criar_aba_mes(wb, nome_aba, dados)

        ExcelHandlerPMPV._criar_aba_resumo(wb, dados_por_mes, resultado)
        wb.save(nome_final)
        wb.close()

        try:
            os.startfile(nome_final)
        except Exception:
            pass

        return nome_final

    @staticmethod
    def _criar_aba_mes(wb, nome_aba, dados):
        ws = wb.create_sheet(nome_aba)
        header_fill = PatternFill("solid", fgColor="2C3E50")
        header_font = Font(bold=True, color="FFFFFF")
        border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

        headers = ["Empresa", "Molécula", "Transporte", "Logística", "Preço Unit.", "Volume (QDC)", "Custo Total"]
        ws.append(headers)

        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        for linha in dados:
            if not linha.get("empresa"):
                continue

            mol = float(linha.get("molecula", 0))
            trans = float(linha.get("transporte", 0))
            log = float(linha.get("logistica", 0))
            vol = float(linha.get("volume", 0))
            preco = mol + trans + log
            total = preco * vol
            ws.append([linha["empresa"], mol, trans, log, preco, vol, total])

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.border = border
            for idx in [1, 2, 3, 4, 6]:
                row[idx].number_format = "#,##0.0000"
            row[5].number_format = "#,##0"

        ws.column_dimensions["A"].width = 30
        ws.column_dimensions["G"].width = 20

    @staticmethod
    def _criar_aba_resumo(wb, _dados_por_mes, resultado):
        ws = wb.create_sheet("Resumo Executivo", 0)
        ws["A1"] = "FECHAMENTO TRIMESTRAL - PMPV"
        ws["A1"].font = Font(size=16, bold=True)
        ws.merge_cells("A1:D1")

        row = 3

        def write_res(label, val, fmt, bold=False, color="000000", bg=None):
            nonlocal row
            ws[f"A{row}"] = label
            ws[f"B{row}"] = val
            ws[f"B{row}"].number_format = fmt
            if bold:
                ws[f"A{row}"].font = Font(bold=True, size=12)
                ws[f"B{row}"].font = Font(bold=True, size=12, color=color)
            if bg:
                fill = PatternFill("solid", fgColor=bg)
                ws[f"A{row}"].fill = fill
                ws[f"B{row}"].fill = fill
            row += 1

        vf_total = resultado.get("vf_total", resultado["volume_total"])
        write_res("Volume Faturado (Trimestre):", vf_total, "#,##0.00")
        write_res("Custo Total (Trimestre):", resultado["custo_total"], "R$ #,##0.00")
        row += 1
        write_res("PMPV Calculado:", resultado["pmpv"], "R$ 0.0000", bold=True)
        write_res("(+) Conta Gráfica:", resultado.get("conta_grafica", 0), "R$ 0.0000")
        row += 1
        write_res("(=) PREÇO FINAL (PV):", resultado.get("preco_final", 0), "R$ 0.0000", bold=True, bg="F1C40F")

        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 20
