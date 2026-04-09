from Src.Services.servicos_cgf import ServicosCGF


class TestServicosCGF:
    def test_processar_arquivos_normaliza_numero_br_e_detecta_consumo(self, tmp_path):
        arquivo_fat = tmp_path / "NF Faturada e complementar.csv"
        arquivo_canc = tmp_path / "NF canceladas e denegadas.csv"
        arquivo_dev = tmp_path / "NF devolução dez.25.csv"

        arquivo_fat.write_text(
            "Produto;Volume Faturado\n"
            "Venda;42.801.234,8660695\n"
            "Cons. Próprio;8.110,2058305\n",
            encoding="utf-8",
        )
        arquivo_canc.write_text(
            "Volume Canceladas\n"
            "100,0000\n",
            encoding="utf-8",
        )
        arquivo_dev.write_text(
            "Volume de Devolução\n"
            "200,0000\n",
            encoding="utf-8",
        )

        servicos = ServicosCGF()
        resultado = servicos.processar_arquivos(
            [str(arquivo_fat), str(arquivo_canc), str(arquivo_dev)],
            fat_col="Volume Faturado",
            fat_cons_col="Produto",
            fat_cons_val="consumo proprio",
            canc_col="Volume Devolução",
            dev_col="Volume Devolução",
        )

        assert resultado["volume_faturado"] == 42801234.8660695
        assert resultado["volume_consumo_proprio"] == 8110.2058305
        assert resultado["volume_canceladas"] == 100.0
        assert resultado["volume_devolucoes"] == 200.0
        assert resultado["volume_final"] == 42800934.8660695
        assert any("localizada automaticamente" in linha for linha in resultado["logs"])