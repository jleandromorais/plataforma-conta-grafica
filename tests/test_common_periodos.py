from __future__ import annotations

import pytest

from Src.common.periodos import normalizar_periodo, variantes_periodo


class TestNormalizarPeriodoComSeparador:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("jan/26", "Jan/2026"),
            ("jan/2026", "Jan/2026"),
            ("Jan/2026", "Jan/2026"),
            ("janeiro/2026", "Jan/2026"),
            ("JANEIRO/26", "Jan/2026"),
            ("fev/25", "Fev/2025"),
            ("fevereiro/2025", "Fev/2025"),
            ("dez/25", "Dez/2025"),
            ("dezembro/2024", "Dez/2024"),
            ("marco/2026", "Mar/2026"),
            ("março/2026", "Mar/2026"),
            ("abr/26", "Abr/2026"),
            ("01/2026", "Jan/2026"),
            ("12/2026", "Dez/2026"),
            ("1/26", "Jan/2026"),
        ],
    )
    def test_normalizacao_mes_ano(self, entrada, esperado):
        assert normalizar_periodo(entrada) == esperado


class TestNormalizarPeriodoSemSeparador:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("jan26", "Jan/2026"),
            ("jan2026", "Jan/2026"),
            ("janeiro26", "Jan/2026"),
            ("fev25", "Fev/2025"),
            ("dezembro2024", "Dez/2024"),
        ],
    )
    def test_sem_separador(self, entrada, esperado):
        assert normalizar_periodo(entrada) == esperado


class TestNormalizarPeriodoTrimestre:
    @pytest.mark.parametrize(
        "entrada,esperado",
        [
            ("Q1/2026", "Q1/2026"),
            ("q1/26", "Q1/2026"),
            ("Q4/2025", "Q4/2025"),
        ],
    )
    def test_trimestre(self, entrada, esperado):
        assert normalizar_periodo(entrada) == esperado


class TestNormalizarPeriodoEdgeCases:
    def test_none(self):
        assert normalizar_periodo(None) == ""

    def test_vazio(self):
        assert normalizar_periodo("") == ""

    def test_so_espacos(self):
        assert normalizar_periodo("   ") == ""

    def test_mes_invalido_retorna_texto_original_limpo(self):
        assert normalizar_periodo("xyz/2026") == "xyz/2026"

    def test_mes_invalido_numero(self):
        # 13 não está no mapa, então retorna o texto original
        assert normalizar_periodo("13/2026") == "13/2026"

    def test_espacos_extra_sao_colapsados(self):
        assert normalizar_periodo("  jan  /  26  ") == "Jan/2026"

    def test_texto_solto_sem_match(self):
        assert normalizar_periodo("dezembro") == "dezembro"


class TestVariantesPeriodo:
    def test_vazio(self):
        assert variantes_periodo("") == tuple()
        assert variantes_periodo(None) == tuple()

    def test_mes_ano_gera_curto(self):
        variantes = variantes_periodo("jan/2026")
        assert "Jan/2026" in variantes
        assert "Jan/26" in variantes

    def test_inclui_original_se_diferente(self):
        variantes = variantes_periodo("janeiro/2026")
        assert "Jan/2026" in variantes
        # original normalizado, então o "janeiro/2026" entra como texto bruto também
        assert "janeiro/2026" in variantes

    def test_trimestre_gera_curto(self):
        variantes = variantes_periodo("Q1/2026")
        assert "Q1/2026" in variantes
        assert "Q1/26" in variantes

    def test_sem_duplicatas(self):
        variantes = variantes_periodo("Jan/2026")
        assert len(variantes) == len(set(variantes))
