from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from Src.Services.servicos_sr import ServicosSR


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def servico(db_mock):
    return ServicosSR(repo=db_mock)


class TestCalcularSR:
    def test_vp_maior_que_vf(self):
        # SR = (VP - VF) × PR
        assert ServicosSR.calcular_sr(100.0, 80.0, 2.5) == 50.0

    def test_vp_menor_que_vf_negativo(self):
        assert ServicosSR.calcular_sr(50.0, 80.0, 2.0) == -60.0

    def test_pr_zero(self):
        assert ServicosSR.calcular_sr(100.0, 50.0, 0.0) == 0.0

    def test_volumes_iguais(self):
        assert ServicosSR.calcular_sr(100.0, 100.0, 5.0) == 0.0


class TestFormatadores:
    def test_volume(self):
        assert ServicosSR.formatar_volume(1234.5) == "1.234,50 m³"

    def test_volume_zero(self):
        assert ServicosSR.formatar_volume(0) == "0,00 m³"

    def test_brl(self):
        assert ServicosSR.formatar_brl(1234.56) == "R$ 1.234,56"

    def test_brl_negativo(self):
        assert ServicosSR.formatar_brl(-100.0) == "R$ -100,00"


class TestListarSessoes:
    def test_delega_ao_db(self, servico, db_mock):
        db_mock.listar_sessoes_com_volumes.return_value = [
            {"id": 1, "nome": "S1", "data_criacao": "x", "vp": 100, "vf": 80}
        ]
        assert servico.listar_sessoes() == [
            {"id": 1, "nome": "S1", "data_criacao": "x", "vp": 100, "vf": 80}
        ]


class TestBuscarVpVf:
    def test_encontra_sessao(self, servico, db_mock):
        db_mock.listar_sessoes_com_volumes.return_value = [
            {"id": 1, "nome": "A", "vp": 100, "vf": 80},
            {"id": 2, "nome": "B", "vp": 200, "vf": 150},
        ]
        assert servico.buscar_vp_vf(2) == {"vp": 200, "vf": 150}

    def test_nao_encontrada(self, servico, db_mock):
        db_mock.listar_sessoes_com_volumes.return_value = []
        assert servico.buscar_vp_vf(42) is None

    def test_vp_vf_none_viram_zero(self, servico, db_mock):
        db_mock.listar_sessoes_com_volumes.return_value = [
            {"id": 1, "nome": "A", "vp": None, "vf": None},
        ]
        assert servico.buscar_vp_vf(1) == {"vp": 0.0, "vf": 0.0}


class TestInicializacao:
    def test_repo_default(self):
        # Sem passar repo, ele constrói um SqliteSRRepository sozinho.
        from Src.Services import servicos_sr as mod
        from unittest.mock import patch
        with patch.object(mod, "SqliteSRRepository") as mock_cls:
            s = ServicosSR()
            mock_cls.assert_called_once()
            assert s._repo is mock_cls.return_value
