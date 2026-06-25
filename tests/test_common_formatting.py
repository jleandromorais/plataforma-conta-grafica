from __future__ import annotations

import pytest

from Src.common.formatting import format_brl, format_brl_plain, parse_brl


class TestFormatBRL:
    def test_valor_inteiro(self):
        assert format_brl(1234) == "R$ 1.234,00"

    def test_valor_com_centavos(self):
        assert format_brl(1234.56) == "R$ 1.234,56"

    def test_milhar_e_milhao(self):
        assert format_brl(1_234_567.89) == "R$ 1.234.567,89"

    def test_zero(self):
        assert format_brl(0) == "R$ 0,00"

    def test_none_vira_zero(self):
        assert format_brl(None) == "R$ 0,00"

    def test_negativo(self):
        assert format_brl(-1234.56) == "R$ -1.234,56"

    def test_arredondamento_para_duas_casas(self):
        # Python usa banker's rounding (round-half-to-even), então 1.555 -> 1.55
        assert format_brl(1.554) == "R$ 1,55"
        assert format_brl(1.556) == "R$ 1,56"


class TestFormatBRLPlain:
    def test_sem_prefixo(self):
        assert format_brl_plain(1234.56) == "1.234,56"

    def test_zero(self):
        assert format_brl_plain(0) == "0,00"

    def test_none_vira_zero(self):
        assert format_brl_plain(None) == "0,00"


class TestParseBRL:
    def test_formato_completo(self):
        assert parse_brl("R$ 1.234,56") == 1234.56

    def test_sem_prefixo_com_separadores_pt(self):
        assert parse_brl("1.234,56") == 1234.56

    def test_so_virgula_decimal(self):
        assert parse_brl("1234,56") == 1234.56

    def test_formato_americano(self):
        assert parse_brl("1234.56") == 1234.56

    def test_texto_vazio_retorna_zero(self):
        assert parse_brl("") == 0.0

    def test_none_retorna_zero(self):
        assert parse_brl(None) == 0.0

    def test_invalido_retorna_zero(self):
        assert parse_brl("abc") == 0.0

    def test_com_espacos_e_prefixo(self):
        assert parse_brl("  R$  1.000,00  ") == 1000.0

    def test_so_ponto_e_tratado_como_decimal_americano(self):
        # "R$ 1.234" sem vírgula é interpretado como ponto decimal (1.234), não como milhar
        assert parse_brl("R$ 1.234") == 1.234

    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("R$ 0,00", 0.0),
            ("R$ 0,01", 0.01),
            ("R$ 999.999,99", 999999.99),
            ("-1234,56", -1234.56),
        ],
    )
    def test_casos_variados(self, entrada, esperado):
        assert parse_brl(entrada) == esperado

    def test_roundtrip_format_parse(self):
        valor = 12345.67
        assert parse_brl(format_brl(valor)) == valor
