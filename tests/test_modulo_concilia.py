"""
Testes para o módulo modulo_concilia.py
"""
import pytest
from pathlib import Path
from modulo_concilia import (
    br_money_to_float,
    format_br,
    clean_ocr_text,
    extrair_valor,
    PdfItem
)


class TestUtilitarios:
    """Testes para funções utilitárias"""
    
    def test_br_money_to_float_formato_padrao(self):
        """Testa conversão de valores monetários brasileiros"""
        assert br_money_to_float("1.234,56") == 1234.56
        assert br_money_to_float("123,45") == 123.45
        assert br_money_to_float("1.234.567,89") == 1234567.89
    
    def test_br_money_to_float_com_simbolos(self):
        """Testa conversão removendo símbolos"""
        assert br_money_to_float("R$ 1.234,56") == 1234.56
        assert br_money_to_float("R$1.234,56") == 1234.56
        assert br_money_to_float("$ 123,45") == 123.45
    
    def test_br_money_to_float_valores_invalidos(self):
        """Testa valores inválidos retornam 0"""
        assert br_money_to_float("") == 0.0
        assert br_money_to_float(None) == 0.0
        assert br_money_to_float("abc") == 0.0
        assert br_money_to_float("   ") == 0.0
    
    def test_br_money_to_float_sem_centavos(self):
        """Testa valores sem centavos"""
        assert br_money_to_float("1234") == 1234.0
        assert br_money_to_float("1.234") == 1234.0
    
    def test_format_br_valores_positivos(self):
        """Testa formatação brasileira de valores positivos"""
        assert format_br(1234.56) == "1.234,56"
        assert format_br(123.45) == "123,45"
        assert format_br(1234567.89) == "1.234.567,89"
    
    def test_format_br_valores_negativos(self):
        """Testa formatação de valores negativos"""
        assert format_br(-1234.56) == "-1.234,56"
        assert format_br(-123.45) == "-123,45"
    
    def test_format_br_zero(self):
        """Testa formatação do valor zero"""
        assert format_br(0) == "0,00"
        assert format_br(0.0) == "0,00"
    
    def test_clean_ocr_text(self):
        """Testa limpeza de texto OCR"""
        assert clean_ocr_text("Teste|com|pipe") == "Testecompipe"
        assert clean_ocr_text("Val!or") == "Va11or"  # ! vira 1, l vira 1
        assert clean_ocr_text("l234") == "1234"
        assert clean_ocr_text("$=teste") == " teste"
        assert clean_ocr_text("a=b") == "a = b"
    
    def test_clean_ocr_text_vazio(self):
        """Testa limpeza de texto vazio"""
        assert clean_ocr_text("") == ""
        assert clean_ocr_text(None) == ""


class TestExtrairValor:
    """Testes para a função extrair_valor"""
    
    def test_extrair_valor_documento_oficial(self):
        """Testa extração de valor em documento oficial"""
        texto = """
        NOTA FISCAL
        Valor Total: R$ 1.234,56
        Data: 12/01/2024
        """
        valor, metodo = extrair_valor(texto)
        
        assert valor == 1234.56
        assert metodo == "Maior Valor Detectado"
    
    def test_extrair_valor_multiplos_valores(self):
        """Testa que retorna o maior valor"""
        texto = """
        Valores:
        R$ 100,00
        R$ 500,50
        R$ 250,25
        """
        valor, metodo = extrair_valor(texto)
        
        assert valor == 500.50
    
    def test_extrair_valor_filtra_anos(self):
        """Testa que anos são filtrados"""
        texto = """
        Ano: 2024,00
        Valor: R$ 1.500,00
        Ano: 2025,00
        """
        valor, metodo = extrair_valor(texto)
        
        assert valor == 1500.00
        # Anos não devem ser considerados
    
    def test_extrair_valor_documento_nao_oficial_filtra_pequenos(self):
        """Testa que valores pequenos são filtrados em docs não oficiais"""
        texto = """
        Valor 1: R$ 10,00
        Valor 2: R$ 500,00
        """
        valor, metodo = extrair_valor(texto)
        
        # Deve retornar 500 (valores < 50 são filtrados em docs não oficiais)
        assert valor == 500.00
    
    def test_extrair_valor_nao_encontrado(self):
        """Testa quando nenhum valor é encontrado"""
        texto = "Texto sem valores monetários"
        valor, metodo = extrair_valor(texto)
        
        assert valor == 0.0
        assert metodo == "Valor não identificado"
    
    def test_extrair_valor_vazio(self):
        """Testa com texto vazio"""
        valor, metodo = extrair_valor("")
        
        assert valor == 0.0
        assert metodo == "Valor não identificado"


class TestPdfItem:
    """Testes para a classe PdfItem"""
    
    def test_criar_pdf_item(self):
        """Testa criação de PdfItem"""
        item = PdfItem(
            file_name="teste.pdf",
            file_path="/caminho/teste.pdf",
            category="Receita",
            amount=1234.56,
            status="OK",
            method="TEXTO_DIGITAL"
        )
        
        assert item.file_name == "teste.pdf"
        assert item.file_path == "/caminho/teste.pdf"
        assert item.category == "Receita"
        assert item.amount == 1234.56
        assert item.status == "OK"
        assert item.method == "TEXTO_DIGITAL"
    
    def test_pdf_item_imutavel(self):
        """Testa que PdfItem é imutável (frozen)"""
        item = PdfItem(
            file_name="teste.pdf",
            file_path="/caminho/teste.pdf",
            category="Receita",
            amount=1234.56,
            status="OK",
            method="TEXTO_DIGITAL"
        )
        
        with pytest.raises(AttributeError):
            item.amount = 999.99
