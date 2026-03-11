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
