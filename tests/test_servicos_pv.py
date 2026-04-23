"""
Testes para o módulo PV (Preço Final).

Fórmula: PV = PMPV + PR
"""
import pytest
from Src.Database.database import DatabasePMPV
from Src.Services.servicos_pv import ServicosPV


class TestServicosPV:
    def test_calcular_pv_formula_basica(self):
        pv = ServicosPV.calcular_pv(pmpv=4.5, pr=1.25)
        assert pv == pytest.approx(5.75)

    def test_calcular_pv_normaliza_nulos(self):
        pv = ServicosPV.calcular_pv(pmpv=None, pr=2.0)
        assert pv == pytest.approx(2.0)

    def test_formatar_brl_quatro_casas(self):
        assert ServicosPV.formatar_brl(12.3456) == "R$ 12,3456"

    def test_parse_brl(self):
        assert ServicosPV.parse_brl("R$ 1.234,5678") == pytest.approx(1234.5678)

    def test_parse_brl_invalido(self):
        assert ServicosPV.parse_brl("abc") == 0.0

    def test_salvar_e_buscar_pv(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pv_test.db"))
        servicos = ServicosPV(db)
        try:
            pv = servicos.salvar_valores("Dez/2025", pmpv=4.0, pr=1.5)
            assert pv == pytest.approx(5.5)

            row = db.buscar_pv("Dez/2025")
            assert row is not None
            assert row["pmpv"] == pytest.approx(4.0)
            assert row["pr"] == pytest.approx(1.5)
            assert row["pv"] == pytest.approx(5.5)
        finally:
            db.fechar()

    def test_listar_pv(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pv_list.db"))
        servicos = ServicosPV(db)
        try:
            servicos.salvar_valores("Jan/2026", pmpv=3.0, pr=2.0)
            servicos.salvar_valores("Fev/2026", pmpv=3.5, pr=2.5)

            lista = db.listar_pv()
            assert len(lista) == 2
        finally:
            db.fechar()

    def test_salvar_pv_sobrescreve_periodo(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pv_overwrite.db"))
        servicos = ServicosPV(db)
        try:
            servicos.salvar_valores("Mar/2026", pmpv=4.0, pr=1.0)
            servicos.salvar_valores("Mar/2026", pmpv=5.0, pr=1.5)

            row = db.buscar_pv("Mar/2026")
            assert row["pmpv"] == pytest.approx(5.0)
            assert row["pv"] == pytest.approx(6.5)

            lista = db.listar_pv()
            assert len(lista) == 1
        finally:
            db.fechar()

    def test_periodo_normalizado_busca_variante_curta(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pv_norm.db"))
        servicos = ServicosPV(db)
        try:
            servicos.salvar_valores("Dez/25", pmpv=4.0, pr=1.0)
            row = db.buscar_pv("Dez/2025")
            assert row is not None
            assert row["pv"] == pytest.approx(5.0)
        finally:
            db.fechar()

    def test_tabela_pv_resultados_criada(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pv_table.db"))
        try:
            db.cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='pv_resultados'"
            )
            assert db.cursor.fetchone() is not None
        finally:
            db.fechar()
