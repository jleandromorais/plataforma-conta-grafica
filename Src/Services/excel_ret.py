import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from datetime import datetime

class ExcelRET:
    @staticmethod
    def gerar_relatorio_completo(dados_processados, calc_ret, excel_path):
        df = pd.DataFrame([{
            'Tipo de Encargo': d['tipo_encargo'],
            'Empresa': d['empresa'],
            'Nota Débito/Crédito': d['nota_tipo'],
            'Nº': d['numero_nd'],
            'Data Vencimento': d['data_vencimento'],
            'Valor Total': d['valor_total'],
            'QT': d['quantidade'],
            'Valor Unitário': d['valor_unitario'],
            'Arquivo': d['arquivo']
        } for d in dados_processados])
        
        wb = Workbook()
        ws_dados = wb.active
        ws_dados.title = "Dados Completos"
        
        header_fill = PatternFill(start_color="1F4788", end_color="1F4788", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF", size=12)
        border = Border(
            left=Side(style='thin'), right=Side(style='thin'),
            top=Side(style='thin'), bottom=Side(style='thin')
        )
        
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws_dados.cell(row=r_idx, column=c_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                if r_idx == 1:  
                    cell.fill = header_fill
                    cell.font = header_font
                else:
                    if c_idx in [6, 7, 8]:  
                        if isinstance(value, (int, float)): cell.number_format = '#,##0.00'
        
        ws_dados.column_dimensions['A'].width = 20
        ws_dados.column_dimensions['B'].width = 25
        ws_dados.column_dimensions['C'].width = 20
        ws_dados.column_dimensions['D'].width = 15
        ws_dados.column_dimensions['E'].width = 18
        ws_dados.column_dimensions['F'].width = 15
        ws_dados.column_dimensions['G'].width = 12
        ws_dados.column_dimensions['H'].width = 15
        ws_dados.column_dimensions['I'].width = 40
        
        # ABA RESUMO POR TIPO
        ws_resumo = wb.create_sheet("Resumo por Tipo")
        resumo = df.groupby('Tipo de Encargo').agg({
            'Valor Total': 'sum',
            'QT': 'sum',
            'Arquivo': 'count'
        }).rename(columns={'Arquivo': 'Quantidade de Arquivos'}).reset_index()
        
        for r_idx, row in enumerate(dataframe_to_rows(resumo, index=False, header=True), 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws_resumo.cell(row=r_idx, column=c_idx, value=value)
                cell.border = border
                cell.alignment = Alignment(horizontal='center', vertical='center')
                
                if r_idx == 1:
                    cell.fill = header_fill
                    cell.font = header_font
                else:
                    if c_idx > 1:
                        if isinstance(value, (int, float)): cell.number_format = '#,##0.00'
        
        ws_resumo.column_dimensions['A'].width = 25
        ws_resumo.column_dimensions['B'].width = 18
        ws_resumo.column_dimensions['C'].width = 15
        ws_resumo.column_dimensions['D'].width = 25
        
        # ABA RESUMO GERAL
        ws_geral = wb.create_sheet("Resumo Geral")

        eat_bruto_xls = calc_ret['eat_bruto']
        pis_rate      = calc_ret['pis_cofins_rate']
        ec_ret_xls    = calc_ret['ret']
        total_qt      = df['QT'].sum()
        total_arqs    = len(df)

        ret_fill = PatternFill(start_color="1F4788", end_color="1F4788", fill_type="solid")
        ret_font = Font(bold=True, color="FFFFFF", size=12)

        dados_geral = [
            ['RESUMO GERAL DO PROCESSAMENTO', ''],
            ['', ''], 
            ['Métrica', 'Valor'], 
            ['Total de PDFs Processados', total_arqs], 
            ['Quantidade Total (QT)', total_qt],
            ['', ''],
            ['Σ EAT bruto (R$)', eat_bruto_xls],
            [f'× (1 − {pis_rate*100:.2f}% PIS/COFINS)', 1.0 - pis_rate],
            ['EC = RET  (R$)', ec_ret_xls], 
            ['', ''],
            ['Data do Processamento', datetime.now().strftime('%Y-%m-%d %H:%M:%S')] 
        ]

        for r_idx, row in enumerate(dados_geral, 1):
            for c_idx, value in enumerate(row, 1):
                cell = ws_geral.cell(row=r_idx, column=c_idx, value=value)
                cell.alignment = Alignment(horizontal='left', vertical='center')
                if r_idx == 1:
                    cell.font = Font(bold=True, size=16, color="1F4788")
                elif r_idx == 3:
                    cell.fill = header_fill
                    cell.font = header_font
                elif r_idx == 9:
                    cell.fill = ret_fill
                    cell.font = ret_font
                    if c_idx == 2: cell.number_format = '#,##0.000000'
                else:
                    if c_idx == 2 and isinstance(value, (int, float)):
                        cell.number_format = '#,##0.000000'
            if r_idx == 1:
                ws_geral.merge_cells('A1:B1')

        ws_geral.column_dimensions['A'].width = 35
        ws_geral.column_dimensions['B'].width = 25
        
        wb.save(excel_path)
        wb.close()