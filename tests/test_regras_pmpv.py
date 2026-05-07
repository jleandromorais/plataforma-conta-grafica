from Src.Database.database import DatabasePMPV
from Src.Services.servicos_pmpv import RegrasPMPV


class TestRegrasPMPV:
    def test_calcular_resultados_separa_vf_real_do_volume_ponderado(self):
        dados = {
            "Mês 1": [
                {
                    "empresa": "PETROBRAS",
                    "molecula": 2.0,
                    "transporte": 0.1,
                    "logistica": 0.0,
                    "volume": 1000.0,
                    "campos_vazios": [],
                }
            ],
            "Mês 2": [],
            "Mês 3": [],
        }

        resultado = RegrasPMPV.calcular_resultados(
            dados_extraidos=dados,
            valor_cg=0.0,
            dias_config={"Mês 1": 30, "Mês 2": 31, "Mês 3": 28},
            lista_meses=["Janeiro", "Fevereiro", "Março"],
            idx_start=0,
        )

        assert resultado["vp_mensal"] == 30000.0
        assert resultado["vf_total"] == 30000.0
        assert resultado["vf_por_mes"]["Janeiro"] == 30000.0
        assert resultado["volume_total"] == 30000.0
        assert resultado["volume_total_calculo"] == 30000.0
        assert resultado["vf_calculo_por_mes"]["Janeiro"] == 30000.0
        assert round(resultado["pmpv"], 4) == 2.1


class TestDatabasePMPVVolumes:
    def test_listar_sessoes_com_volumes_retorna_vf_real(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "volumes.db"))

        try:
            sessao_id = db.criar_sessao("Sessão VF")
            db.salvar_dados_mes(
                sessao_id,
                1,
                [
                    {
                        "empresa": "PETROBRAS",
                        "molecula": 2.0,
                        "transporte": 0.1,
                        "logistica": 0.0,
                        "volume": 42801234.8661,
                    }
                ],
            )
            db.salvar_resultado(sessao_id, 1492433000.0, 42801234.8661, 42801234.8661, 0.0, 2.1154, 0.0, 2.1154)

            sessoes = db.listar_sessoes_com_volumes()

            assert len(sessoes) == 1
            assert round(sessoes[0]["vp"], 4) == 42801234.8661
            assert round(sessoes[0]["vf"], 4) == 42801234.8661
        finally:
            db.fechar()