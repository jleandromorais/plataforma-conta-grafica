from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from Src.Services.servicos_scg import ServicosSCG


@pytest.fixture
def servico():
    with patch("Src.Services.servicos_scg.ServicosConsolidacao") as mock_cls:
        mock_cls.return_value = MagicMock()
        yield ServicosSCG()


class TestFormatarBRL:
    def test_basico(self):
        assert ServicosSCG.formatar_brl(1500) == "R$ 1.500,00"

    def test_none(self):
        assert ServicosSCG.formatar_brl(None) == "R$ 0,00"


class TestBuscarDadosPeriodo:
    def test_inexistente(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = None
        assert servico.buscar_dados_periodo("Jan/2026") is None

    def test_completo(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": 1000, "cgf": 700, "rpv": 300,
            "ret": 50, "rp": 20, "scg": 270,
        }
        r = servico.buscar_dados_periodo("Jan/2026")
        assert r == {"cgr": 1000, "cgf": 700, "rpv": 300, "ret": 50, "rp": 20, "scg": 270}

    def test_rpv_calculado_quando_falta(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": 1000, "cgf": 400, "rpv": None,
            "ret": 0, "rp": 0, "scg": 0,
        }
        assert servico.buscar_dados_periodo("Jan/2026")["rpv"] == 600

    def test_todos_none(self, servico):
        servico.consolidacao.buscar_consolidacao.return_value = {
            "cgr": None, "cgf": None, "rpv": None,
            "ret": None, "rp": None, "scg": None,
        }
        r = servico.buscar_dados_periodo("Jan/2026")
        assert all(v == 0.0 for v in r.values())


class TestSalvarERecalcular:
    def test_salvar_retorna_rpv(self, servico):
        servico.consolidacao.salvar_valores.return_value = {"rpv": 280.0}
        rpv = servico.salvar_valores_manuais("Jan/2026", 1000, 700, 30, 10)
        assert rpv == 280.0
        servico.consolidacao.salvar_valores.assert_called_once_with(
            "Jan/2026", cgr=1000, cgf=700, ret=30, rp=10
        )

    def test_calcular_scg_oficial_delega(self, servico):
        servico.consolidacao.recalcular_scg.return_value = {"scg": 999.0}
        assert servico.calcular_scg_oficial("Jan/2026") == {"scg": 999.0}


class TestObterCriarApagar:
    def test_obter(self, servico):
        servico.consolidacao.obter_periodos.return_value = [{"periodo": "Jan/2026"}]
        assert servico.obter_periodos() == [{"periodo": "Jan/2026"}]

    def test_criar_strip(self, servico):
        servico.criar_periodo("  Jan/2026 ")
        servico.consolidacao.criar_periodo.assert_called_once_with("Jan/2026")

    def test_apagar(self, servico):
        servico.apagar_periodo("Jan/2026")
        servico.consolidacao.apagar_periodo.assert_called_once_with("Jan/2026")


class TestGerarTextoHistorico:
    def test_inclui_scg_e_data(self, servico):
        servico.consolidacao.obter_periodos.return_value = [
            {"periodo": "Jan/2026", "scg": 1234.56, "data_atualizacao": "2026-01-15 10:00:00"},
        ]
        txt = servico.gerar_texto_historico()
        assert "Jan/2026" in txt
        assert "R$ 1.234,56" in txt
        assert "2026-01-15 10:00" in txt

    def test_scg_none_vira_zero(self, servico):
        servico.consolidacao.obter_periodos.return_value = [
            {"periodo": "Jan/2026", "scg": None, "data_atualizacao": None},
        ]
        txt = servico.gerar_texto_historico()
        assert "R$ 0,00" in txt
