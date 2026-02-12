"""
Testes para o módulo excel_handler.py
"""
import pytest
import openpyxl
from pathlib import Path
from excel_handler import ExcelHandlerPMPV


class TestExcelHandlerPMPV:
    """Suite de testes para ExcelHandlerPMPV"""
    
    @pytest.fixture
    def dados_exemplo(self):
        """Dados de exemplo para testes"""
        return {
            'Janeiro': [
                {
                    'empresa': 'PETROBRAS',
                    'molecula': 1.5000,
                    'transporte': 0.3000,
                    'logistica': 0.2000,
                    'volume': 1000
                },
                {
                    'empresa': 'GALP',
                    'molecula': 1.6000,
                    'transporte': 0.3500,
                    'logistica': 0.2500,
                    'volume': 800
                }
            ],
            'Fevereiro': [
                {
                    'empresa': 'PETROBRAS',
                    'molecula': 1.5200,
                    'transporte': 0.3100,
                    'logistica': 0.2100,
                    'volume': 1050
                }
            ],
            'Março': [
                {
                    'empresa': 'GALP',
                    'molecula': 1.5800,
                    'transporte': 0.3400,
                    'logistica': 0.2400,
                    'volume': 900
                }
            ]
        }
    
    @pytest.fixture
    def resultado_exemplo(self):
        """Resultado de exemplo para testes"""
        return {
            'volume_total': 90000,
            'custo_total': 180000,
            'pmpv': 2.0000,
            'conta_grafica': -0.0210,
            'preco_final': 1.9790
        }
    
    def test_exportar_trimestre_cria_arquivo(self, dados_exemplo, resultado_exemplo, tmp_path):
        """Testa se o arquivo Excel é criado"""
        arquivo = tmp_path / "teste.xlsx"
        
        nome_criado = ExcelHandlerPMPV.exportar_trimestre(
            dados_exemplo,
            resultado_exemplo,
            str(arquivo)
        )
        
        assert Path(nome_criado).exists()
        assert nome_criado == str(arquivo)
    
    def test_exportar_sem_nome_gera_timestamp(self, dados_exemplo, resultado_exemplo, tmp_path, monkeypatch):
        """Testa se gera nome com timestamp quando não fornecido"""
        # Muda o diretório de trabalho para tmp_path
        monkeypatch.chdir(tmp_path)
        
        nome_criado = ExcelHandlerPMPV.exportar_trimestre(
            dados_exemplo,
            resultado_exemplo
        )
        
        assert Path(nome_criado).exists()
        assert nome_criado.startswith("Relatorio_PMPV_")
        assert nome_criado.endswith(".xlsx")
    
    def test_arquivo_contem_abas_corretas(self, dados_exemplo, resultado_exemplo, tmp_path):
        """Verifica se as abas são criadas corretamente"""
        arquivo = tmp_path / "teste.xlsx"
        
        ExcelHandlerPMPV.exportar_trimestre(dados_exemplo, resultado_exemplo, str(arquivo))
        
        wb = openpyxl.load_workbook(arquivo)
        
        # Verifica aba de resumo
        assert "Resumo Executivo" in wb.sheetnames
        
        # Verifica abas mensais
        assert "Janeiro" in wb.sheetnames
        assert "Fevereiro" in wb.sheetnames
        assert "Março" in wb.sheetnames
        
        wb.close()
    
    def test_aba_mes_contem_cabecalhos(self, dados_exemplo, resultado_exemplo, tmp_path):
        """Verifica se os cabeçalhos estão corretos"""
        arquivo = tmp_path / "teste.xlsx"
        
        ExcelHandlerPMPV.exportar_trimestre(dados_exemplo, resultado_exemplo, str(arquivo))
        
        wb = openpyxl.load_workbook(arquivo)
        ws = wb["Janeiro"]
        
        headers_esperados = ["Empresa", "Molécula", "Transporte", "Logística", 
                            "Preço Unit.", "Volume (QDC)", "Custo Total"]
        
        headers_encontrados = [cell.value for cell in ws[1]]
        
        assert headers_encontrados == headers_esperados
        
        wb.close()
    
    def test_aba_mes_calcula_valores_corretamente(self, dados_exemplo, resultado_exemplo, tmp_path):
        """Verifica se os cálculos na aba estão corretos"""
        arquivo = tmp_path / "teste.xlsx"
        
        ExcelHandlerPMPV.exportar_trimestre(dados_exemplo, resultado_exemplo, str(arquivo))
        
        wb = openpyxl.load_workbook(arquivo)
        ws = wb["Janeiro"]
        
        # Primeira linha de dados (PETROBRAS)
        empresa = ws.cell(2, 1).value
        molecula = ws.cell(2, 2).value
        transporte = ws.cell(2, 3).value
        logistica = ws.cell(2, 4).value
        preco_unit = ws.cell(2, 5).value
        volume = ws.cell(2, 6).value
        custo_total = ws.cell(2, 7).value
        
        assert empresa == "PETROBRAS"
        assert molecula == 1.5
        assert transporte == 0.3
        assert logistica == 0.2
        assert preco_unit == 2.0  # 1.5 + 0.3 + 0.2
        assert volume == 1000
        assert custo_total == 2000  # 2.0 * 1000
        
        wb.close()
    
    def test_aba_resumo_contem_totais(self, dados_exemplo, resultado_exemplo, tmp_path):
        """Verifica se a aba de resumo contém os totais corretos"""
        arquivo = tmp_path / "teste.xlsx"
        
        ExcelHandlerPMPV.exportar_trimestre(dados_exemplo, resultado_exemplo, str(arquivo))
        
        wb = openpyxl.load_workbook(arquivo)
        ws = wb["Resumo Executivo"]
        
        # Verifica título
        assert ws["A1"].value == "FECHAMENTO TRIMESTRAL - PMPV"
        
        # Verifica valores (assumindo estrutura conhecida)
        # Volume Total
        assert ws["A3"].value == "Volume Total (Trimestre):"
        assert ws["B3"].value == 90000
        
        # Custo Total
        assert ws["A4"].value == "Custo Total (Trimestre):"
        assert ws["B4"].value == 180000
        
        # PMPV
        assert ws["A6"].value == "PMPV Calculado:"
        assert ws["B6"].value == 2.0000
        
        # Conta Gráfica
        assert ws["A7"].value == "(+) Conta Gráfica:"
        assert ws["B7"].value == -0.0210
        
        # Preço Final
        assert ws["A9"].value == "(=) PREÇO FINAL (PV):"
        assert ws["B9"].value == 1.9790
        
        wb.close()
    
    def test_dados_vazios_nao_sao_adicionados(self, resultado_exemplo, tmp_path):
        """Verifica que linhas sem empresa não são adicionadas"""
        dados_com_vazios = {
            'Janeiro': [
                {
                    'empresa': 'PETROBRAS',
                    'molecula': 1.5,
                    'transporte': 0.3,
                    'logistica': 0.2,
                    'volume': 1000
                },
                {
                    'empresa': '',  # Vazio
                    'molecula': 1.6,
                    'transporte': 0.35,
                    'logistica': 0.25,
                    'volume': 800
                },
                {
                    'empresa': None,  # None
                    'molecula': 1.7,
                    'transporte': 0.4,
                    'logistica': 0.3,
                    'volume': 900
                }
            ]
        }
        
        arquivo = tmp_path / "teste.xlsx"
        ExcelHandlerPMPV.exportar_trimestre(dados_com_vazios, resultado_exemplo, str(arquivo))
        
        wb = openpyxl.load_workbook(arquivo)
        ws = wb["Janeiro"]
        
        # Deve ter apenas cabeçalho + 1 linha (PETROBRAS)
        assert ws.max_row == 2
        
        wb.close()
    
    def test_formatacao_numerica(self, dados_exemplo, resultado_exemplo, tmp_path):
        """Verifica se a formatação numérica está aplicada"""
        arquivo = tmp_path / "teste.xlsx"
        
        ExcelHandlerPMPV.exportar_trimestre(dados_exemplo, resultado_exemplo, str(arquivo))
        
        wb = openpyxl.load_workbook(arquivo)
        ws = wb["Janeiro"]
        
        # Verifica formato de moeda nas células numéricas (linha 2)
        assert ws.cell(2, 2).number_format == '#,##0.0000'  # Molécula
        assert ws.cell(2, 3).number_format == '#,##0.0000'  # Transporte
        assert ws.cell(2, 4).number_format == '#,##0.0000'  # Logística
        assert ws.cell(2, 5).number_format == '#,##0.0000'  # Preço Unit
        assert ws.cell(2, 6).number_format == '#,##0'       # Volume
        assert ws.cell(2, 7).number_format == '#,##0.0000'  # Custo Total
        
        wb.close()
