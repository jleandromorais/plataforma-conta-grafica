from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from Src.Services.servicos_rpv import ServicosRPV


@pytest.fixture
def servico():
    with patch("Src.Services.servicos_rpv.ServicosConsolidacao") as mock_cls:
        mock_cls.return_value = MagicMock()
        s = ServicosRPV()
        yield s


class TestFormatacao:
    def test_formatar_brl_basico(self):
        assert ServicosRPV.formatar_brl(1234.56) == "R$ 1.234,56"

    def test_formatar_brl_zero(self):
        assert ServicosRPV.formatar_brl(0) == "R$ 0,00"

    def test_formatar_brl_none(self):
        assert ServicosRPV.formatar_brl(None) == "R$ 0,00"

    def test_parse_brl_com_prefixo(self):
        assert ServicosRPV.parse_brl("R$ 1.234,56") == 1234.56

    def test_parse_brl_sem_prefixo(self):
        assert ServicosRPV.parse_brl("1234,56") == 1234.56

    def test_parse_brl_invalido(self):
        assert ServicosRPV.parse_brl("abc") == 0.0


class TestBuscarDadosPeriodo:
    def test_periodo_inexistente_retorna_none(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = None
        assert servico.buscar_dados_periodo("Jan/2026") is None

    def test_dados_completos(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": 1000.0, "cgf": 600.0, "rpv": 400.0
        }
        r = servico.buscar_dados_periodo("Jan/2026")
        assert r == {"cgr": 1000.0, "cgf": 600.0, "rpv": 400.0}

    def test_rpv_none_calcula_cgr_menos_cgf(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": 1000.0, "cgf": 300.0, "rpv": None
        }
        r = servico.buscar_dados_periodo("Jan/2026")
        assert r["rpv"] == 700.0

    def test_valores_none_viram_zero(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": None, "cgf": None, "rpv": None
        }
        r = servico.buscar_dados_periodo("Jan/2026")
        assert r == {"cgr": 0.0, "cgf": 0.0, "rpv": 0.0}


class TestSalvarValores:
    def test_retorna_rpv_recalculado(self, servico):
        servico.consolidacao.salvar_valores.return_value = {"rpv": 250.0}
        rpv = servico.salvar_valores("Jan/2026", cgr=1000, cgf=750)
        assert rpv == 250.0
        servico.consolidacao.salvar_valores.assert_called_once_with(
            "Jan/2026", cgr=1000, cgf=750
        )


class TestObterECriarPeriodo:
    def test_obter_delega(self, servico):
        servico.consolidacao.obter_periodos.return_value = [{"periodo": "Jan/2026"}]
        assert servico.obter_periodos() == [{"periodo": "Jan/2026"}]

    def test_criar_strip(self, servico):
        servico.criar_periodo("  Jan/2026  ")
        servico.consolidacao.criar_periodo.assert_called_once_with("Jan/2026")


class TestGerarTextoHistorico:
    def test_inclui_cabecalho_e_linhas(self, servico):
        servico.consolidacao.obter_periodos.return_value = [{"periodo": "Jan/2026"}]
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": 1000.0, "cgf": 600.0, "rpv": 400.0,
            "data_atualizacao": "2026-01-15 10:30:00",
        }
        txt = servico.gerar_texto_historico()
        assert "Período" in txt
        assert "CGR" in txt and "CGF" in txt and "RPV" in txt
        assert "Jan/2026" in txt
        assert "R$ 1.000,00" in txt
        assert "R$ 600,00" in txt
        assert "R$ 400,00" in txt

    def test_pula_periodo_sem_dados(self, servico):
        servico.consolidacao.obter_periodos.return_value = [{"periodo": "Jan/2026"}]
        servico.consolidacao.buscar_consolidacao.return_value = None
        txt = servico.gerar_texto_historico()
        # Cabeçalho presente, mas linha não
        assert "Período" in txt
        assert "Jan/2026" not in txt
