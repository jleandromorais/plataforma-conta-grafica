from Src.Database.database import DatabasePMPV
from Src.Services.servicos_consolidacao import ServicosConsolidacao


class TestServicosConsolidacao:
    def test_calcular_rpv(self):
        assert ServicosConsolidacao.calcular_rpv(150.0, 40.0) == 110.0

    def test_calcular_scg(self):
        scg = ServicosConsolidacao.calcular_scg(150.0, 40.0, 10.0, 5.0)
        assert scg == 125.0

    def test_salvar_cgr_recalcula_rpv(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "consolidacao.db"))
        servicos = ServicosConsolidacao(db)

        try:
            servicos.salvar_cgf("Dez/2025", 30.0)
            dados = servicos.salvar_cgr("Dez/2025", 100.0)

            assert dados["cgr"] == 100.0
            assert dados["cgf"] == 30.0
            assert dados["rpv"] == 70.0
        finally:
            servicos.fechar()

    def test_recalcular_scg_persiste_resultado(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "consolidacao.db"))
        servicos = ServicosConsolidacao(db)

        try:
            servicos.salvar_valores("Jan/2026", cgr=200.0, cgf=50.0, ret=25.0, rp=10.0)
            dados = servicos.recalcular_scg("Jan/2026")

            assert dados["rpv"] == 150.0
            assert dados["scg"] == 185.0

            persistido = servicos.buscar_consolidacao("Jan/2026")
            assert persistido["scg"] == 185.0
        finally:
            servicos.fechar()


class TestSalvarModuloGravaScg:
    """Salvar CGR, CGF, RET, RP ou vários valores deixa a coluna `scg` crua certa (valores fictícios)."""

    def test_cada_modulo_grava_o_scg(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "consolidacao.db"))
        servicos = ServicosConsolidacao(db)
        try:
            servicos.salvar_cgr("Ago/2026", 1000.0)
            assert db.buscar_consolidacao_bruta("Ago/2026")["scg"] == 1000.0
            servicos.salvar_cgf("Ago/2026", 300.0)
            assert db.buscar_consolidacao_bruta("Ago/2026")["scg"] == 700.0
            servicos.salvar_ret("Ago/2026", 50.0)
            assert db.buscar_consolidacao_bruta("Ago/2026")["scg"] == 750.0
            dados = servicos.salvar_rp("Ago/2026", -20.0)
            assert db.buscar_consolidacao_bruta("Ago/2026")["scg"] == 730.0
            assert dados["scg"] == 730.0 and dados["rpv"] == 700.0
        finally:
            servicos.fechar()

    def test_salvar_valores_grava_o_scg(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "consolidacao.db"))
        servicos = ServicosConsolidacao(db)
        try:
            servicos.salvar_valores("Set/2026", cgr=500.0, cgf=100.0, ret=10.0, rp=5.0)
            assert db.buscar_consolidacao_bruta("Set/2026")["scg"] == 415.0
        finally:
            servicos.fechar()


class TestReparoDoHistorico:
    def _preparar(self, db):
        # Ago: 4 campos preenchidos e scg cru 0 (o caso real); Set: completo e certo;
        # Out: falta o RP (não pode ser gravado); Nov: scg cru velho mas completo.
        for periodo, cgr, cgf, ret, rp, scg in [
            ("Ago/2026", 1000.0, 400.0, 30.0, -20.0, 0.0),
            ("Set/2026", 800.0, 300.0, 10.0, 5.0, 515.0),
            ("Out/2026", 900.0, 100.0, 20.0, 0.0, 0.0),
            ("Nov/2026", 700.0, 200.0, 40.0, -10.0, 999.0),
        ]:
            db.criar_periodo_consolidacao(periodo)
            db.atualizar_campos_consolidacao(periodo, cgr=cgr, cgf=cgf, ret=ret, rp=rp, scg=scg)

    def test_simulacao_nao_grava(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "consolidacao.db"))
        servicos = ServicosConsolidacao(db)
        try:
            self._preparar(db)
            r = servicos.reparar_scg_historico()
            assert r["aplicado"] is False
            assert {m["periodo"] for m in r["meses"]} == {"Ago/2026", "Nov/2026"}
            assert db.buscar_consolidacao_bruta("Ago/2026")["scg"] == 0.0   # nada mudou
        finally:
            servicos.fechar()

    def test_aplicar_conserta_so_meses_completos(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "consolidacao.db"))
        servicos = ServicosConsolidacao(db)
        try:
            self._preparar(db)
            r = servicos.reparar_scg_historico(aplicar=True)
            assert db.buscar_consolidacao_bruta("Ago/2026")["scg"] == 610.0   # 1000 − 400 + 30 − 20
            assert db.buscar_consolidacao_bruta("Nov/2026")["scg"] == 530.0
            assert db.buscar_consolidacao_bruta("Out/2026")["scg"] == 0.0     # incompleto: intocado
            assert r["ignorados"] == [{"periodo": "Out/2026", "motivo": "falta RP"}]
            assert r["sem_divergencia"] == 1                                    # Set já estava certo
            # rodar de novo não acha mais nada para consertar
            assert servicos.reparar_scg_historico()["meses"] == []
        finally:
            servicos.fechar()
