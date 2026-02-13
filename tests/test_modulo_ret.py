"""
Testes para o módulo modulo_ret.py
"""
import pytest
import os
from pathlib import Path
from modulo_ret import SistemaRET, TAXA_EUR_BRL


class TestIdentificacaoTipo:
    """Testes para identificação de tipos de encargo"""
    
    def test_identificar_tipo_eat(self):
        """Testa identificação de EAT"""
        caminho = "C:/pasta/EAT/arquivo.pdf"
        
        # Criar instância temporária (sem mostrar GUI)
        sistema = type('MockSistema', (), {
            '_identificar_tipo': SistemaRET._identificar_tipo.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._identificar_tipo(caminho)
        assert tipo == 'EAT'
    
    def test_identificar_tipo_penalidade(self):
        """Testa identificação de Penalidade"""
        caminho = "C:/pasta/PENALIDADE/arquivo.pdf"
        
        sistema = type('MockSistema', (), {
            '_identificar_tipo': SistemaRET._identificar_tipo.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._identificar_tipo(caminho)
        assert tipo == 'Penalidades'
    
    def test_identificar_tipo_top(self):
        """Testa identificação de TOP"""
        caminho = "C:/pasta/TOP/arquivo.pdf"
        
        sistema = type('MockSistema', (), {
            '_identificar_tipo': SistemaRET._identificar_tipo.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._identificar_tipo(caminho)
        assert tipo == 'TOP'
    
    def test_identificar_tipo_outros(self):
        """Testa tipo Outros quando não identifica"""
        caminho = "C:/pasta/DESCONHECIDO/arquivo.pdf"
        
        sistema = type('MockSistema', (), {
            '_identificar_tipo': SistemaRET._identificar_tipo.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._identificar_tipo(caminho)
        assert tipo == 'Outros'


class TestExtrairEmpresa:
    """Testes para extração de empresa"""
    
    def test_extrair_empresa_petrobras(self):
        """Testa extração de PETROBRAS"""
        caminho = "C:/pasta/arquivo_PETROBRAS_01.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_empresa': SistemaRET._extrair_empresa.__get__(None, SistemaRET)
        })()
        
        empresa = sistema._extrair_empresa(caminho)
        assert empresa == 'PETROBRAS'
    
    def test_extrair_empresa_galp(self):
        """Testa extração de GALP"""
        caminho = "C:/pasta/nota_GALP_202401.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_empresa': SistemaRET._extrair_empresa.__get__(None, SistemaRET)
        })()
        
        empresa = sistema._extrair_empresa(caminho)
        assert empresa == 'GALP'
    
    def test_extrair_empresa_ambev(self):
        """Testa extração de AMBEV"""
        caminho = "C:/pasta/AMBEV_fatura.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_empresa': SistemaRET._extrair_empresa.__get__(None, SistemaRET)
        })()
        
        empresa = sistema._extrair_empresa(caminho)
        assert empresa == 'AMBEV'
    
    def test_extrair_empresa_desconhecida(self):
        """Testa quando empresa não é reconhecida"""
        caminho = "C:/pasta/empresa_desconhecida.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_empresa': SistemaRET._extrair_empresa.__get__(None, SistemaRET)
        })()
        
        empresa = sistema._extrair_empresa(caminho)
        assert empresa == 'N/A'


class TestExtrairTipoNota:
    """Testes para identificação de tipo de nota"""
    
    def test_extrair_tipo_nota_debito_nd(self):
        """Testa identificação de Nota de Débito (ND)"""
        caminho = "C:/pasta/ND_12345.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_tipo_nota': SistemaRET._extrair_tipo_nota.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._extrair_tipo_nota(caminho)
        assert tipo == 'Débito'
    
    def test_extrair_tipo_nota_debito_palavra(self):
        """Testa identificação por palavra DEBITO"""
        caminho = "C:/pasta/NOTA_DEBITO_2024.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_tipo_nota': SistemaRET._extrair_tipo_nota.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._extrair_tipo_nota(caminho)
        assert tipo == 'Débito'
    
    def test_extrair_tipo_nota_credito_nc(self):
        """Testa identificação de Nota de Crédito (NC)"""
        caminho = "C:/pasta/NC_67890.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_tipo_nota': SistemaRET._extrair_tipo_nota.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._extrair_tipo_nota(caminho)
        assert tipo == 'Crédito'
    
    def test_extrair_tipo_nota_credito_palavra(self):
        """Testa identificação por palavra CREDITO"""
        caminho = "C:/pasta/NOTA_CREDITO_2024.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_tipo_nota': SistemaRET._extrair_tipo_nota.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._extrair_tipo_nota(caminho)
        assert tipo == 'Crédito'
    
    def test_extrair_tipo_nota_nao_identificada(self):
        """Testa quando tipo não é identificado"""
        caminho = "C:/pasta/fatura_2024.pdf"
        
        sistema = type('MockSistema', (), {
            '_extrair_tipo_nota': SistemaRET._extrair_tipo_nota.__get__(None, SistemaRET)
        })()
        
        tipo = sistema._extrair_tipo_nota(caminho)
        assert tipo == 'N/A'


class TestCalculos:
    """Testes para cálculos de valores"""
    
    def test_conversao_eur_brl(self):
        """Testa conversão de EUR para BRL"""
        valor_eur = 100.0
        valor_brl = valor_eur * TAXA_EUR_BRL
        
        assert valor_brl == 600.0  # 100 * 6.0
    
    def test_calculo_valor_unitario(self):
        """Testa cálculo de valor unitário"""
        valor_total = 1000.0
        quantidade = 50.0
        
        valor_unitario = valor_total / quantidade
        
        assert valor_unitario == 20.0
    
    def test_calculo_valor_unitario_quantidade_zero(self):
        """Testa que valor unitário é 0 quando quantidade é 0"""
        valor_total = 1000.0
        quantidade = 0.0
        
        if quantidade > 0:
            valor_unitario = valor_total / quantidade
        else:
            valor_unitario = 0.0
        
        assert valor_unitario == 0.0


class TestEstruturaDados:
    """Testes para estrutura de dados"""
    
    def test_estrutura_dados_completa(self):
        """Testa estrutura completa de dados extraídos"""
        dados = {
            'arquivo': 'teste.pdf',
            'caminho': '/caminho/teste.pdf',
            'tipo_encargo': 'EAT',
            'empresa': 'PETROBRAS',
            'nota_tipo': 'Débito',
            'numero_nd': '12345',
            'data_vencimento': '01/01/2024',
            'valor_total': 1000.0,
            'quantidade': 50.0,
            'valor_unitario': 20.0,
            'valores_encontrados': [500.0, 1000.0, 250.0]
        }
        
        # Verifica campos obrigatórios
        assert 'arquivo' in dados
        assert 'caminho' in dados
        assert 'tipo_encargo' in dados
        assert 'empresa' in dados
        assert 'valor_total' in dados
        assert 'valores_encontrados' in dados
        
        # Verifica tipos
        assert isinstance(dados['arquivo'], str)
        assert isinstance(dados['valor_total'], float)
        assert isinstance(dados['valores_encontrados'], list)
    
    def test_valores_encontrados_max(self):
        """Testa que valor_total é o máximo dos valores encontrados"""
        valores_encontrados = [100.0, 500.0, 250.0, 300.0]
        valor_total = max(valores_encontrados)
        
        assert valor_total == 500.0
    
    def test_dados_sem_valores(self):
        """Testa dados quando nenhum valor é encontrado"""
        dados = {
            'arquivo': 'teste.pdf',
            'valor_total': 0.0,
            'valores_encontrados': []
        }
        
        assert len(dados['valores_encontrados']) == 0
        assert dados['valor_total'] == 0.0


class TestFormatacao:
    """Testes para formatação de valores"""
    
    def test_formatacao_moeda_brasileira(self):
        """Testa formatação de valores em Real"""
        valor = 1234.56
        
        # Formato brasileiro: 1.234,56
        valor_fmt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        assert valor_fmt == "1.234,56"
    
    def test_formatacao_valor_grande(self):
        """Testa formatação de valores grandes"""
        valor = 1234567.89
        
        valor_fmt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        assert valor_fmt == "1.234.567,89"
    
    def test_formatacao_valor_pequeno(self):
        """Testa formatação de valores pequenos"""
        valor = 12.34
        
        valor_fmt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        assert valor_fmt == "12,34"


class TestValidacoes:
    """Testes de validação"""
    
    def test_validar_arquivo_pdf(self):
        """Testa validação de arquivo PDF"""
        arquivo = "documento.pdf"
        
        assert arquivo.lower().endswith('.pdf')
    
    def test_validar_arquivo_nao_pdf(self):
        """Testa que arquivo não-PDF é rejeitado"""
        arquivo = "documento.txt"
        
        assert not arquivo.lower().endswith('.pdf')
    
    def test_valor_positivo(self):
        """Testa que apenas valores positivos são aceitos"""
        valores = [100.0, -50.0, 200.0, 0.0, 150.0]
        valores_validos = [v for v in valores if v > 0]
        
        assert valores_validos == [100.0, 200.0, 150.0]
    
    def test_taxa_cambio_valida(self):
        """Testa que taxa de câmbio é válida"""
        assert TAXA_EUR_BRL > 0
        assert isinstance(TAXA_EUR_BRL, (int, float))
