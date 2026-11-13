"""
Testes para o módulo PV (Preço Final).

Fórmula: PV = PMPV + PR
"""
import pytest
from Src.Database.database import DatabasePMPV
from Src.Services.tarifa.servicos_pv import ServicosPV


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


# ── PV trimestral: PV = PMPV + PR do mesmo trimestre (NT_05_2026, Quadro 12) ──

def _db_com(tmp_path, pmpv: dict[str, float] | None = None, pr: dict[str, float] | None = None):
    db = DatabasePMPV(str(tmp_path / "pv_tri.db"))
    for periodo, valor in (pmpv or {}).items():
        db.salvar_pmpv_mensal(periodo, valor)
    for periodo, valor in (pr or {}).items():
        db.salvar_pr(periodo, 0.0, 0.0, 0.0, valor)
    return db


_FEV_ABR_PMPV = {"Fev/2026": 1.9988, "Mar/2026": 1.9988, "Abr/2026": 1.9988}


class TestPVTrimestral:
    def test_carrega_pmpv_e_pr_do_trimestre(self, tmp_path):
        db = _db_com(tmp_path, _FEV_ABR_PMPV, {"Fev - Abr/2026": -0.0321})
        try:
            r = ServicosPV(db).buscar_trimestre("Fev - Abr", 2026)
            assert r["chave"] == "Fev - Abr/2026"
            assert r["periodos"] == ["Fev/2026", "Mar/2026", "Abr/2026"]
            assert r["pmpv"] == pytest.approx(1.9988)
            assert r["pr"] == pytest.approx(-0.0321)
            assert r["pv"] == pytest.approx(1.9667)
            assert r["avisos"] == []
        finally:
            db.fechar()

    def test_salvar_grava_trimestre_e_os_3_meses(self, tmp_path):
        db = _db_com(tmp_path)
        try:
            r = ServicosPV(db).salvar_trimestre("Fev - Abr", 2026, pmpv=1.9988, pr=-0.0321)
            assert r["pv"] == pytest.approx(1.9667)
            assert r["gravado_em"] == ["Fev - Abr/2026", "Fev/2026", "Mar/2026", "Abr/2026"]
            for chave in ("Fev - Abr/2026", "Fev/2026", "Mar/2026", "Abr/2026"):
                row = db.buscar_pv(chave)
                assert row is not None, chave
                assert row["pv"] == pytest.approx(1.9667)
                assert row["pr"] == pytest.approx(-0.0321)
        finally:
            db.fechar()

    def test_sem_pr_avisa(self, tmp_path):
        db = _db_com(tmp_path, _FEV_ABR_PMPV)
        try:
            r = ServicosPV(db).buscar_trimestre("Fev - Abr", 2026)
            assert r["pr"] == 0.0 and r["pv"] == pytest.approx(1.9988)
            assert any("PR de Fev - Abr/2026" in a for a in r["avisos"])
        finally:
            db.fechar()

    def test_sem_pmpv_avisa(self, tmp_path):
        db = _db_com(tmp_path, pr={"Fev - Abr/2026": -0.0321})
        try:
            r = ServicosPV(db).buscar_trimestre("Fev - Abr", 2026)
            assert r["pmpv"] == 0.0
            assert any("PMPV de Fev - Abr/2026" in a for a in r["avisos"])
        finally:
            db.fechar()

    def test_pmpv_diferente_entre_meses_usa_o_primeiro_e_avisa(self, tmp_path):
        db = _db_com(tmp_path, {"Fev/2026": 1.99, "Mar/2026": 2.01, "Abr/2026": 2.01}, {"Fev - Abr/2026": 0.0})
        try:
            r = ServicosPV(db).buscar_trimestre("Fev - Abr", 2026)
            assert r["pmpv"] == pytest.approx(1.99)
            assert any("diferente" in a for a in r["avisos"])
        finally:
            db.fechar()

    def test_virada_de_ano(self, tmp_path):
        db = _db_com(
            tmp_path,
            {"Nov/2025": 2.1154, "Dez/2025": 2.1154, "Jan/2026": 2.1154},
            {"Nov - Jan/2026": -0.021},  # o módulo PR grava Nov/25–Jan/26 com o ano de Jan
        )
        try:
            r = ServicosPV(db).buscar_trimestre("Nov - Jan", 2025)
            assert r["chave"] == "Nov - Jan/2025"
            assert r["periodos"] == ["Nov/2025", "Dez/2025", "Jan/2026"]
            assert r["pr"] == pytest.approx(-0.021)
            assert r["pv"] == pytest.approx(2.0944)
            assert r["avisos"] == []
        finally:
            db.fechar()

    def test_trimestre_inexistente(self, tmp_path):
        db = _db_com(tmp_path)
        try:
            with pytest.raises(ValueError, match="Trimestre"):
                ServicosPV(db).buscar_trimestre("Jan - Mar", 2026)
        finally:
            db.fechar()


class TestPVTrimestralRevisao:
    def test_salvar_virada_de_ano_grava_os_meses_certos(self, tmp_path):
        db = _db_com(tmp_path)
        try:
            r = ServicosPV(db).salvar_trimestre("Nov - Jan", 2025, pmpv=2.1154, pr=-0.021)
            assert r["gravado_em"] == ["Nov - Jan/2025", "Nov/2025", "Dez/2025", "Jan/2026"]
            assert db.buscar_pv("Jan/2026")["pv"] == pytest.approx(2.0944)
        finally:
            db.fechar()

    def test_salvar_com_pmpv_zerado_e_recusado(self, tmp_path):
        db = _db_com(tmp_path)
        try:
            with pytest.raises(ValueError, match="PMPV está zerado"):
                ServicosPV(db).salvar_trimestre("Fev - Abr", 2026, pmpv=0.0, pr=-0.0321)
            assert db.buscar_pv("Fev/2026") is None
        finally:
            db.fechar()

    def test_listar_pv_nao_traz_chave_de_trimestre(self, tmp_path):
        db = _db_com(tmp_path)
        try:
            ServicosPV(db).salvar_trimestre("Fev - Abr", 2026, pmpv=1.9988, pr=-0.0321)
            periodos = {r["periodo"] for r in db.listar_pv()}
            assert periodos == {"Fev/2026", "Mar/2026", "Abr/2026"}
        finally:
            db.fechar()

    def test_pv_salvo_diferente_do_atual_avisa(self, tmp_path):
        db = _db_com(tmp_path, _FEV_ABR_PMPV, {"Fev - Abr/2026": -0.0321})
        try:
            servico = ServicosPV(db)
            servico.salvar_trimestre("Fev - Abr", 2026, pmpv=1.9988, pr=-0.05)  # PR digitado à mão
            r = servico.buscar_trimestre("Fev - Abr", 2026)
            assert r["salvo"]["pr"] == pytest.approx(-0.05)
            assert r["pv"] == pytest.approx(1.9667)  # atual pelos módulos
            assert any("difere" in a for a in r["avisos"])
        finally:
            db.fechar()

    def test_pmpv_faltando_em_um_mes_avisa(self, tmp_path):
        db = _db_com(tmp_path, {"Mar/2026": 1.9988, "Abr/2026": 1.9988}, {"Fev - Abr/2026": -0.0321})
        try:
            r = ServicosPV(db).buscar_trimestre("Fev - Abr", 2026)
            assert r["pmpv"] == pytest.approx(1.9988)
            assert any("PMPV não salvo em Fev/2026" in a for a in r["avisos"])
        finally:
            db.fechar()
