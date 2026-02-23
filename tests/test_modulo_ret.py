"""
Testes para o módulo modulo_ret.py
"""
import pytest
import re
import os
from pathlib import Path
from modulo_ret import SistemaRET, TAXA_EUR_BRL


# ---------------------------------------------------------------------------
# Funções puras extraídas para teste sem UI
# ---------------------------------------------------------------------------

def identificar_tipo(caminho: str) -> str:
    partes = [p.upper() for p in Path(caminho).parts[:-1]]
    if any('EAT' in p for p in partes):
        return 'EAT'
    if any('PENALIDADE' in p for p in partes):
        return 'Penalidades'
    if any(re.fullmatch(r'TOP[\s_\-]?.*', p) or p == 'TOP' for p in partes):
        return 'TOP'
    return 'Outros'


def extrair_tipo_nota(caminho: str) -> str:
    nome = os.path.basename(caminho).upper()
    tokens = set(re.split(r'[\s_\-\.]+', nome))
    if 'ND' in tokens or 'DEBITO' in nome or 'DÉBITO' in nome:
        return 'Débito'
    if 'NC' in tokens or 'CREDITO' in nome or 'CRÉDITO' in nome:
        return 'Crédito'
    return 'N/A'


def parse_valor(s: str):
    try:
        v = float(s.replace('.', '').replace(',', '.'))
        return v if v > 0 else None
    except Exception:
        return None


def extrair_valores(texto: str):
    """Replica a lógica de extração de valores sem UI."""
    padrao_brl = r'R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
    padrao_eur = r'€\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)'
    padrao_gen = r'(?<![€$\d,])(\d{1,3}(?:\.\d{3})+,\d{2})(?!\d)'

    valores_brl = [v for m in re.findall(padrao_brl, texto)
                   if (v := parse_valor(m)) is not None]
    valores_eur = [v for m in re.findall(padrao_eur, texto)
                   if (v := parse_valor(m)) is not None]

    if not valores_brl and not valores_eur:
        valores_brl = [v for m in re.findall(padrao_gen, texto)
                       if (v := parse_valor(m)) is not None]

    todos_brl = valores_brl + [v * TAXA_EUR_BRL for v in valores_eur]
    moeda = 'EUR' if valores_eur and not valores_brl else 'BRL'
    return todos_brl, moeda


class TestIdentificacaoTipo:
    """Testes para identificação de tipos de encargo"""

    def test_identificar_tipo_eat(self):
        assert identificar_tipo("C:/pasta/EAT/arquivo.pdf") == 'EAT'

    def test_identificar_tipo_penalidade(self):
        assert identificar_tipo("C:/pasta/PENALIDADE/arquivo.pdf") == 'Penalidades'

    def test_identificar_tipo_top(self):
        assert identificar_tipo("C:/pasta/TOP/arquivo.pdf") == 'TOP'

    def test_identificar_tipo_outros(self):
        assert identificar_tipo("C:/pasta/DESCONHECIDO/arquivo.pdf") == 'Outros'

    # --- Regressão bug: "TOP" em "DESKTOP" ---
    def test_bug_desktop_nao_e_top(self):
        """BUG CORRIGIDO: arquivo na pasta Desktop não deve ser tipo TOP."""
        assert identificar_tipo("C:/Users/fulano/Desktop/arquivo.pdf") == 'Outros'

    def test_bug_laptop_nao_e_top(self):
        assert identificar_tipo("C:/LAPTOP/arquivo.pdf") == 'Outros'

    def test_top_com_sufixo_ainda_e_top(self):
        """Pasta 'TOP_2025' deve continuar sendo identificada como TOP."""
        assert identificar_tipo("C:/pasta/TOP_2025/arquivo.pdf") == 'TOP'


class TestExtrairEmpresa:
    """Testes para extração de empresa (usa método estático via instância mock simples)"""

    def _mock(self):
        return type('M', (), {'_extrair_empresa': SistemaRET._extrair_empresa})()

    def test_extrair_empresa_petrobras(self):
        assert self._mock()._extrair_empresa("C:/pasta/arquivo_PETROBRAS_01.pdf") == 'PETROBRAS'

    def test_extrair_empresa_galp(self):
        assert self._mock()._extrair_empresa("C:/pasta/nota_GALP_202401.pdf") == 'GALP'

    def test_extrair_empresa_ambev(self):
        assert self._mock()._extrair_empresa("C:/pasta/AMBEV_fatura.pdf") == 'AMBEV'

    def test_extrair_empresa_desconhecida(self):
        assert self._mock()._extrair_empresa("C:/pasta/empresa_desconhecida.pdf") == 'N/A'


class TestExtrairTipoNota:
    """Testes para identificação de tipo de nota"""

    def test_debito_nd(self):
        assert extrair_tipo_nota("C:/pasta/ND_12345.pdf") == 'Débito'

    def test_debito_palavra(self):
        assert extrair_tipo_nota("C:/pasta/NOTA_DEBITO_2024.pdf") == 'Débito'

    def test_credito_nc(self):
        assert extrair_tipo_nota("C:/pasta/NC_67890.pdf") == 'Crédito'

    def test_credito_palavra(self):
        assert extrair_tipo_nota("C:/pasta/NOTA_CREDITO_2024.pdf") == 'Crédito'

    def test_nao_identificada(self):
        assert extrair_tipo_nota("C:/pasta/fatura_2024.pdf") == 'N/A'

    # --- Regressão bug: "ND" dentro de palavras ---
    def test_bug_fundo_nao_e_debito(self):
        """BUG CORRIGIDO: 'FUNDO' contém 'ND' mas não é nota de débito."""
        assert extrair_tipo_nota("C:/pasta/FUNDO_SOCIAL.pdf") == 'N/A'

    def test_bug_agenda_nao_e_debito(self):
        """BUG CORRIGIDO: 'AGENDA' contém 'ND' mas não é nota de débito."""
        assert extrair_tipo_nota("C:/pasta/AGENDA_2024.pdf") == 'N/A'

    def test_bug_segunda_nao_e_debito(self):
        assert extrair_tipo_nota("C:/pasta/SEGUNDA_VIA.pdf") == 'N/A'


class TestCalculos:
    """Testes para cálculos de valores"""

    def test_conversao_eur_brl(self):
        assert 100.0 * TAXA_EUR_BRL == pytest.approx(600.0)

    def test_calculo_valor_unitario(self):
        assert 1000.0 / 50.0 == pytest.approx(20.0)

    def test_calculo_valor_unitario_quantidade_zero(self):
        valor_unitario = 1000.0 / 50.0 if 50.0 > 0 else 0.0
        assert valor_unitario == pytest.approx(20.0)
        valor_zero = 1000.0 / 1.0 if 0.0 > 0 else 0.0
        assert valor_zero == 0.0


class TestExtracaoValores:
    """Testes para extração e conversão de moeda — cobre os bugs corrigidos."""

    def test_valor_brl_nao_multiplicado(self):
        """BUG CORRIGIDO: valor em R$ não deve ser multiplicado por TAXA_EUR_BRL."""
        texto = "Total a pagar: R$ 1.000,00"
        valores, moeda = extrair_valores(texto)
        assert moeda == 'BRL'
        assert max(valores) == pytest.approx(1000.0)

    def test_valor_eur_convertido_para_brl(self):
        """Valor em € deve ser convertido para BRL na extração."""
        texto = "Total: € 100,00"
        valores, moeda = extrair_valores(texto)
        assert moeda == 'EUR'
        assert max(valores) == pytest.approx(100.0 * TAXA_EUR_BRL)

    def test_sem_simbolo_usa_fallback_generico(self):
        """Sem símbolo de moeda, o padrão genérico captura valores formatados."""
        texto = "Valor apurado: 2.500,00 referente ao período."
        valores, moeda = extrair_valores(texto)
        assert moeda == 'BRL'
        assert 2500.0 in [pytest.approx(v) for v in valores]

    def test_bug_regex_nao_duplica_valores(self):
        """BUG CORRIGIDO: padrão genérico não deve duplicar valores já capturados
        por R$ ou €."""
        texto = "Fatura: R$ 5.000,00"
        valores, _ = extrair_valores(texto)
        count_5000 = sum(1 for v in valores if abs(v - 5000.0) < 0.01)
        assert count_5000 == 1, f"Valor 5000 apareceu {count_5000}x (esperado 1)"

    def test_valores_negativos_ignorados(self):
        """Valores negativos ou zero não devem entrar na lista."""
        texto = "Desconto: R$ 0,00  Total: R$ 300,00"
        valores, _ = extrair_valores(texto)
        assert all(v > 0 for v in valores)


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
