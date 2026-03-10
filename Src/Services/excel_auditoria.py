from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

class ExcelAuditoria:
    @staticmethod
    def gerar_relatorio_auditoria(resultados, nome_arquivo):
        """Gera relatório Excel com os resultados da auditoria."""
        wb = Workbook()
        ws = wb.active
        ws.title = "Auditoria"
        
        # Cabeçalho
        headers = ["Empresa", "Tipo", "Número", "Valor Total", "ICMS", "PIS", 
                   "COFINS", "Volume", "Status"]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(1, col, header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Dados
        for row, item in enumerate(resultados, 2):
            ws.cell(row, 1, item.empresa)
            ws.cell(row, 2, item.tipo)
            ws.cell(row, 3, item.numero)
            ws.cell(row, 4, item.valor_total)
            ws.cell(row, 5, item.icms)
            ws.cell(row, 6, item.pis)
            ws.cell(row, 7, item.cofins)
            ws.cell(row, 8, item.volume)
            ws.cell(row, 9, item.status)
            
            # Colorir status
            status_cell = ws.cell(row, 9)
            if item.status == "OK":
                status_cell.fill = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
            else:
                status_cell.fill = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
        
        wb.save(nome_arquivo)