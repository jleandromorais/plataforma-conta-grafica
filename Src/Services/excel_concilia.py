from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pathlib import Path

class ExcelConcilia:
    @staticmethod
    def gerar_relatorio(caminho: Path, itens):
        wb = Workbook()
        ws = wb.active
        ws.title = "Relatorio"
        
        # Estilos
        header_fill = PatternFill("solid", fgColor="2C3E50")
        header_font = Font(bold=True, color="FFFFFF")
        
        ws.append(["Arquivo", "Categoria", "Valor", "Status", "Método", "Caminho"])
        for cell in ws[1]:
            cell.font = header_font
            cell.fill = header_fill

        total_rec = 0.0
        total_desp = 0.0

        for i in itens:
            ws.append([i.file_name, i.category, i.amount, i.status, i.method, i.file_path])
            cell_val = ws.cell(row=ws.max_row, column=3)
            cell_val.number_format = '"R$ "#,##0.00'
            
            if i.status == "OK":
                if i.category == "Receita": total_rec += i.amount
                elif i.category == "Despesa": total_desp += i.amount

        # Rodapé com totais
        ws.append([])
        ws.append(["RESUMO FINAL", "", "", "", "", ""])
        ws.append(["(+) RECEITAS", "", total_rec, "", "", ""])
        ws.append(["(-) DESPESAS", "", total_desp, "", "", ""])
        ws.append(["(=) SALDO", "", total_rec - total_desp, "", "", ""])
        
        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["E"].width = 30
        
        wb.save(caminho)
        return total_rec, total_desp