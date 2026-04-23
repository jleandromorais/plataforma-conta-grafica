"""
Testes para o módulo PR (Preço Regulatório Final).

Fórmula: PR = (SGR + SR) / VP
SGR é tratado como SCG por compatibilidade com o sistema atual.
"""
import pytest
from Src.Database.database import DatabasePMPV
from Src.Services.servicos_pr import ServicosPR


class TestServicosPR:
    # ── Testes de cálculo puro ──────────────────────────────────────────────

    def test_calcular_pr_formula_basica(self):
        pr = ServicosPR.calcular_pr(scg=100.0, sr=50.0, vp=10.0)
        assert pr == pytest.approx(15.0)

    def test_calcular_pr_divisao_por_zero_retorna_zero(self):
        pr = ServicosPR.calcular_pr(scg=500.0, sr=200.0, vp=0.0)
        assert pr == 0.0

    def test_calcular_pr_vp_zero_explicito(self):
        assert ServicosPR.calcular_pr(0.0, 0.0, 0.0) == 0.0

    def test_calcular_pr_valores_nulos_normalizados(self):
        pr = ServicosPR.calcular_pr(None, None, 5.0)
        assert pr == 0.0

    def test_calcular_pr_resultado_negativo(self):
        pr = ServicosPR.calcular_pr(scg=-100.0, sr=0.0, vp=10.0)
        assert pr == pytest.approx(-10.0)

    def test_calcular_pr_sgr_e_sr_somados(self):
        pr = ServicosPR.calcular_pr(scg=300.0, sr=200.0, vp=50.0)
        assert pr == pytest.approx(10.0)

    # ── Testes de formatação ────────────────────────────────────────────────

    def test_formatar_brl(self):
        assert ServicosPR.formatar_brl(1234.56) == "R$ 1.234,56"

    def test_formatar_pr_quatro_casas(self):
        assert ServicosPR.formatar_pr(15.1234) == "R$ 15,1234"

    def test_formatar_volume(self):
        assert ServicosPR.formatar_volume(1000.0) == "1.000,00 m³"

    def test_parse_brl_virgula(self):
        assert ServicosPR.parse_brl("1.234,56") == pytest.approx(1234.56)

    def test_parse_brl_invalido_retorna_zero(self):
        assert ServicosPR.parse_brl("abc") == 0.0

    # ── Testes de persistência no banco ────────────────────────────────────

    def test_salvar_e_buscar_pr(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pr_test.db"))
        servicos = ServicosPR(db)
        try:
            pr = servicos.salvar_valores("Dez/2025", scg=200.0, sr=100.0, vp=20.0)
            assert pr == pytest.approx(15.0)

            row = db.buscar_pr("Dez/2025")
            assert row is not None
            assert row["scg"] == pytest.approx(200.0)
            assert row["sr"] == pytest.approx(100.0)
            assert row["vp"] == pytest.approx(20.0)
            assert row["pr"] == pytest.approx(15.0)
        finally:
            db.fechar()

    def test_listar_pr(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pr_list.db"))
        servicos = ServicosPR(db)
        try:
            servicos.salvar_valores("Jan/2026", scg=100.0, sr=50.0, vp=5.0)
            servicos.salvar_valores("Fev/2026", scg=200.0, sr=100.0, vp=10.0)

            lista = db.listar_pr()
            assert len(lista) == 2
        finally:
            db.fechar()

    def test_salvar_pr_sobrescreve_periodo(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pr_overwrite.db"))
        servicos = ServicosPR(db)
        try:
            servicos.salvar_valores("Mar/2026", scg=100.0, sr=0.0, vp=10.0)
            servicos.salvar_valores("Mar/2026", scg=200.0, sr=50.0, vp=10.0)

            row = db.buscar_pr("Mar/2026")
            assert row["scg"] == pytest.approx(200.0)
            assert row["pr"] == pytest.approx(25.0)

            lista = db.listar_pr()
            assert len(lista) == 1
        finally:
            db.fechar()

    def test_vp_zero_salva_pr_zero(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pr_zero_vp.db"))
        servicos = ServicosPR(db)
        try:
            pr = servicos.salvar_valores("Abr/2026", scg=500.0, sr=300.0, vp=0.0)
            assert pr == 0.0

            row = db.buscar_pr("Abr/2026")
            assert row["pr"] == 0.0
        finally:
            db.fechar()

    def test_periodo_normalizado_busca_variante_curta(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pr_norm.db"))
        servicos = ServicosPR(db)
        try:
            servicos.salvar_valores("Dez/25", scg=100.0, sr=50.0, vp=5.0)
            row = db.buscar_pr("Dez/2025")
            assert row is not None
            assert row["pr"] == pytest.approx(30.0)
        finally:
            db.fechar()

    def test_tabela_pr_resultados_criada(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pr_table.db"))
        try:
            db.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pr_resultados'"
            )
            assert db.cursor.fetchone() is not None
        finally:
            db.fechar()
