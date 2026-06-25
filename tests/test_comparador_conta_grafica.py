from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from Src.Services.comparador_conta_grafica import (
    ComparadorContaGrafica,
    ResultadoComparacaoNotas,
    _normalizar_numero_nota,
    _periodo_de_data,
    _sheet_corresponde_periodo,
    _tokens_periodo,
)
from Src.Services.servicos_auditoria import XMLItem


# ════════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════════

class TestNormalizarNumeroNota:
    def test_string_simples(self):
        assert _normalizar_numero_nota("123456") == "123456"

    def test_remove_zeros_a_esquerda(self):
        assert _normalizar_numero_nota("0001234") == "1234"

    def test_float_inteiro_sem_decimal(self):
        # 123456.0 (lido pelo pandas) → "123456", não "1234560"
        assert _normalizar_numero_nota(123456.0) == "123456"

    def test_string_com_ponto_zero_sufixo(self):
        assert _normalizar_numero_nota("123456.0") == "123456"

    def test_padrao_numero_serie(self):
        assert _normalizar_numero_nota("132893-55") == "132893"
        assert _normalizar_numero_nota("7861/24") == "7861"
        assert _normalizar_numero_nota("000001227-2") == "1227"

    def test_nan_vazio_n_a(self):
        assert _normalizar_numero_nota(float("nan")) == ""
        assert _normalizar_numero_nota("nan") == ""
        assert _normalizar_numero_nota("N/A") == ""
        assert _normalizar_numero_nota("-") == ""

    def test_letras_e_numeros(self):
        # Quando não há dígitos: cai no alnum maiúsculo
        assert _normalizar_numero_nota("ABC123") == "123"

    def test_zero_puro(self):
        assert _normalizar_numero_nota("000") == "0"


class TestPeriodoDeData:
    def test_datetime(self):
        assert _periodo_de_data(datetime(2026, 1, 15)) == "Jan/2026"

    def test_date(self):
        assert _periodo_de_data(date(2026, 3, 1)) == "Mar/2026"

    def test_timestamp(self):
        assert _periodo_de_data(pd.Timestamp("2026-05-20")) == "Mai/2026"

    def test_string_periodo(self):
        assert _periodo_de_data("jan/26") == "Jan/2026"

    def test_string_data(self):
        assert _periodo_de_data("15/01/2026") == "Jan/2026"

    def test_nan(self):
        assert _periodo_de_data(float("nan")) == ""

    def test_string_vazia(self):
        assert _periodo_de_data("") == ""

    def test_invalido(self):
        assert _periodo_de_data("xyz qualquer coisa") == ""


class TestTokensPeriodo:
    def test_tokens_jan_2026(self):
        tokens = _tokens_periodo("Jan/2026")
        assert "jan/2026" in tokens
        assert "jan/26" in tokens
        assert "jan26" in tokens
        assert "janeiro26" in tokens
        assert "janeiro/2026" in tokens

    def test_periodo_sem_separador_fallback(self):
        tokens = _tokens_periodo("xyz")
        assert "xyz" in tokens


class TestSheetCorrespondePeriodo:
    def test_nome_com_mes_abrev(self):
        assert _sheet_corresponde_periodo("Jan-26", "Jan/2026") is True

    def test_nome_com_mes_completo(self):
        assert _sheet_corresponde_periodo("Janeiro/2026", "Jan/2026") is True

    def test_nao_corresponde(self):
        assert _sheet_corresponde_periodo("Fev/2026", "Jan/2026") is False

    def test_none(self):
        assert _sheet_corresponde_periodo(None, "Jan/2026") is False

    def test_nan(self):
        assert _sheet_corresponde_periodo(float("nan"), "Jan/2026") is False

    def test_vazio(self):
        assert _sheet_corresponde_periodo("", "Jan/2026") is False


# ════════════════════════════════════════════════════════════════════════════
# ComparadorContaGrafica.comparar
# ════════════════════════════════════════════════════════════════════════════

def _mk_item(numero: str, valor: float = 1000.0, icms_taxa: float = 0.12) -> XMLItem:
    return XMLItem(
        empresa="ACME", tipo="NF-e", numero=numero,
        valor_total=valor, icms=valor * icms_taxa, icms_taxa=icms_taxa,
        pis=valor * 0.0165, cofins=valor * 0.076,
        volume=10, status="OK", volume_total=10.0,
    )


class TestComparar:
    def test_dataframe_vazio_levanta(self):
        with pytest.raises(ValueError, match="vazia ou inválida"):
            ComparadorContaGrafica.comparar(
                [_mk_item("1")], pd.DataFrame(), "Jan/2026"
            )

    def test_periodo_invalido_levanta(self):
        df = pd.DataFrame({"Nota": [1, 2], "Valor": [100, 200]})
        with pytest.raises(ValueError, match="Período inválido"):
            ComparadorContaGrafica.comparar([_mk_item("1")], df, "")

    def test_resultados_sem_notas_validas(self):
        df = pd.DataFrame({"Nota": [1, 2]})
        with pytest.raises(ValueError, match="auditoria não retornou"):
            ComparadorContaGrafica.comparar([], df, "Jan/2026")

    def test_match_completo(self):
        # Auditoria tem nota 123, planilha também — deve dar match
        df = pd.DataFrame({
            "Numero Nota Fiscal": ["123", "456", "789"],
            "Periodo": ["jan/26", "jan/26", "jan/26"],
        })
        resultado = ComparadorContaGrafica.comparar(
            [_mk_item("123"), _mk_item("456")], df, "Jan/2026"
        )
        assert isinstance(resultado, ResultadoComparacaoNotas)
        assert resultado.periodo == "Jan/2026"
        assert resultado.qtd_em_ambas == 2
        assert resultado.total_nossa_base == 2
        # 789 está só na planilha
        assert len(resultado.notas_apenas_conta_grafica) == 1
        assert resultado.notas_apenas_conta_grafica[0]["numero_normalizado"] == "789"

    def test_apenas_na_auditoria(self):
        df = pd.DataFrame({
            "Numero Nota Fiscal": ["999"],
            "Periodo": ["jan/26"],
        })
        resultado = ComparadorContaGrafica.comparar(
            [_mk_item("123")], df, "Jan/2026"
        )
        assert resultado.qtd_em_ambas == 0
        assert len(resultado.notas_apenas_nossa) == 1
        assert resultado.notas_apenas_nossa[0]["numero_normalizado"] == "123"

    def test_filtra_por_periodo(self):
        df = pd.DataFrame({
            "Numero Nota Fiscal": ["100", "200"],
            "Periodo": ["jan/26", "fev/26"],
        })
        resultado = ComparadorContaGrafica.comparar(
            [_mk_item("100"), _mk_item("200")], df, "Jan/2026"
        )
        # Só a 100 está em jan/26 — 200 é fev/26, não deve aparecer
        assert resultado.qtd_em_ambas == 1
        assert any(n["numero_normalizado"] == "200" for n in resultado.notas_apenas_nossa)

    def test_avisos_quando_nada_cruza(self):
        df = pd.DataFrame({
            "Numero Nota Fiscal": ["999"],
            "Periodo": ["jan/26"],
        })
        resultado = ComparadorContaGrafica.comparar(
            [_mk_item("123")], df, "Jan/2026"
        )
        assert resultado.avisos
        assert any("auditoria" in a.lower() or "coincidiu" in a.lower() for a in resultado.avisos)
