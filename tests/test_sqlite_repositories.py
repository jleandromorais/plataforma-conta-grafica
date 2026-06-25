from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from Src.infrastructure.repositories.sqlite_repositories import (
    SqliteConsolidacaoRepository,
    SqlitePMPVRepository,
)


# ════════════════════════════════════════════════════════════════════════════
# SqliteConsolidacaoRepository
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def repo(db_mock):
    return SqliteConsolidacaoRepository(db=db_mock)


class TestConsolidacaoListarPeriodos:
    def test_delega(self, repo, db_mock):
        db_mock.listar_periodos.return_value = [{"periodo": "Jan/2026"}]
        assert repo.listar_periodos() == [{"periodo": "Jan/2026"}]
        db_mock.listar_periodos.assert_called_once()


class TestConsolidacaoCriarApagar:
    def test_criar_periodo(self, repo, db_mock):
        db_mock.criar_periodo_consolidacao.return_value = 42
        assert repo.criar_periodo_consolidacao("Jan/2026", "obs") == 42
        db_mock.criar_periodo_consolidacao.assert_called_once_with("Jan/2026", "obs")

    def test_criar_periodo_obs_default(self, repo, db_mock):
        repo.criar_periodo_consolidacao("Jan/2026")
        db_mock.criar_periodo_consolidacao.assert_called_once_with("Jan/2026", "")

    def test_apagar_periodo(self, repo, db_mock):
        repo.apagar_periodo("Jan/2026")
        db_mock.apagar_periodo.assert_called_once_with("Jan/2026")


class TestConsolidacaoBuscar:
    def test_buscar_consolidacao(self, repo, db_mock):
        db_mock.buscar_consolidacao.return_value = {"cgr": 100.0}
        assert repo.buscar_consolidacao("Jan/2026") == {"cgr": 100.0}
        db_mock.buscar_consolidacao.assert_called_once_with("Jan/2026")


class TestConsolidacaoAtualizar:
    @pytest.mark.parametrize("metodo,valor", [
        ("atualizar_cgr", 1000.0),
        ("atualizar_cgf", 700.0),
        ("atualizar_ret", 50.0),
        ("atualizar_rp", 20.0),
    ])
    def test_atualizar_simples_delega(self, repo, db_mock, metodo, valor):
        getattr(repo, metodo)("Jan/2026", valor)
        getattr(db_mock, metodo).assert_called_once_with("Jan/2026", valor)

    def test_atualizar_campos_kwargs(self, repo, db_mock):
        repo.atualizar_campos_consolidacao("Jan/2026", cgr=1000.0, cgf=700.0)
        db_mock.atualizar_campos_consolidacao.assert_called_once_with(
            "Jan/2026", cgr=1000.0, cgf=700.0
        )


class TestConsolidacaoSalvarERPV:
    def test_salvar_rpv(self, repo, db_mock):
        repo.salvar_rpv("Jan/2026", 300.0)
        db_mock.salvar_rpv.assert_called_once_with("Jan/2026", 300.0)

    def test_salvar_scg(self, repo, db_mock):
        repo.salvar_scg("Jan/2026", 250.0)
        db_mock.salvar_scg.assert_called_once_with("Jan/2026", 250.0)

    def test_fechar(self, repo, db_mock):
        repo.fechar()
        db_mock.fechar.assert_called_once()


class TestConsolidacaoConstrutorDefault:
    def test_sem_db_constroi_padrao(self, monkeypatch):
        from Src.infrastructure.repositories import sqlite_repositories as mod
        mock_db_cls = MagicMock()
        monkeypatch.setattr(mod, "DatabasePMPV", mock_db_cls)
        r = SqliteConsolidacaoRepository()
        mock_db_cls.assert_called_once()
        assert r.db is mock_db_cls.return_value


# ════════════════════════════════════════════════════════════════════════════
# SqlitePMPVRepository
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def pmpv_repo(db_mock):
    return SqlitePMPVRepository(db=db_mock)


class TestPMPVSessao:
    def test_criar_sessao(self, pmpv_repo, db_mock):
        db_mock.criar_sessao.return_value = 7
        assert pmpv_repo.criar_sessao("Sessao X", "obs") == 7
        db_mock.criar_sessao.assert_called_once_with("Sessao X", "obs")

    def test_criar_sessao_obs_default(self, pmpv_repo, db_mock):
        pmpv_repo.criar_sessao("X")
        db_mock.criar_sessao.assert_called_once_with("X", "")


class TestPMPVDados:
    def test_salvar_dados_mes(self, pmpv_repo, db_mock):
        dados = [{"empresa": "ACME", "vp": 100}]
        pmpv_repo.salvar_dados_mes(1, 3, dados)
        db_mock.salvar_dados_mes.assert_called_once_with(1, 3, dados)

    def test_salvar_resultado(self, pmpv_repo, db_mock):
        pmpv_repo.salvar_resultado(1, 100, 80, 70, 5000, 50.0, 60.0, 70.0)
        db_mock.salvar_resultado.assert_called_once_with(1, 100, 80, 70, 5000, 50.0, 60.0, 70.0)


class TestPMPVMensal:
    def test_salvar(self, pmpv_repo, db_mock):
        pmpv_repo.salvar_pmpv_mensal("Jan/2026", 1.234)
        db_mock.salvar_pmpv_mensal.assert_called_once_with("Jan/2026", 1.234)

    def test_listar(self, pmpv_repo, db_mock):
        db_mock.listar_pmpv_mensal.return_value = [{"periodo": "Jan/2026", "pmpv": 1.0}]
        assert pmpv_repo.listar_pmpv_mensal() == [{"periodo": "Jan/2026", "pmpv": 1.0}]

    def test_buscar(self, pmpv_repo, db_mock):
        db_mock.buscar_pmpv_mensal.return_value = {"pmpv": 2.5}
        assert pmpv_repo.buscar_pmpv_mensal("Jan/2026") == {"pmpv": 2.5}
        db_mock.buscar_pmpv_mensal.assert_called_once_with("Jan/2026")


class TestPMPVOutros:
    def test_listar_periodos(self, pmpv_repo, db_mock):
        db_mock.listar_periodos.return_value = []
        assert pmpv_repo.listar_periodos() == []

    def test_fechar(self, pmpv_repo, db_mock):
        pmpv_repo.fechar()
        db_mock.fechar.assert_called_once()

    def test_construtor_default(self, monkeypatch):
        from Src.infrastructure.repositories import sqlite_repositories as mod
        mock_cls = MagicMock()
        monkeypatch.setattr(mod, "DatabasePMPV", mock_cls)
        r = SqlitePMPVRepository()
        mock_cls.assert_called_once()
        assert r.db is mock_cls.return_value
