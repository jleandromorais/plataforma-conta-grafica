from datetime import datetime

import pytest

from Src.Database.database import DatabasePMPV
from Src.application.use_cases.pmpv_use_cases import PMPVUseCases
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository


class TestPMPVUseCases:
    def test_salvar_sessao_completa(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pmpv_use_cases.db"))
        repo = SqlitePMPVRepository(db)
        use_cases = PMPVUseCases(repo)

        dados = {
            "Janeiro": [
                {"empresa": "PETROBRAS", "molecula": 1.0, "transporte": 0.5, "logistica": 0.2, "volume": 100}
            ],
            "Fevereiro": [],
            "Março": [],
        }
        resultado = {
            "volume_total": 3100.0,
            "custo_total": 5270.0,
            "pmpv": 1.7,
            "conta_grafica": -0.02,
            "preco_final": 1.68,
        }

        try:
            sid = use_cases.salvar_sessao_completa("Sessao Teste", dados, resultado)
            assert sid > 0
            assert db.carregar_dados_mes(sid, 1)
        finally:
            use_cases.fechar()

    def test_salvar_pmpv_mensal(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pmpv_use_cases.db"))
        use_cases = PMPVUseCases(SqlitePMPVRepository(db))

        try:
            use_cases.salvar_pmpv_mensal("Jan/2026", 2.1234)
            assert db.buscar_pmpv_mensal("Jan/2026") == 2.1234
        finally:
            use_cases.fechar()


# ── Importar Memória de Cálculo: mensagens de erro que dizem o que fazer ──────

def _memoria(tmp_path, meses, empresas=None, nome="memoria.xlsx"):
    """Planilha no layout da Memória: linha 1 com as datas (a partir da col. D);
    por empresa, uma linha de título (C = nome, D.. = datas) e as linhas A/B/C/E."""
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "PMPV"
    datas = [datetime(a, m, 1) for a, m in meses]
    for j, d in enumerate(datas):
        ws.cell(row=1, column=4 + j, value=d)
    linha = 3
    for emp, valores in (empresas or {"PETROBRAS": {"A": 1.5, "B": 0.4, "C": 0.1, "E": 1000}}).items():
        ws.cell(row=linha, column=3, value=emp)
        for j, d in enumerate(datas):
            ws.cell(row=linha, column=4 + j, value=d)
        for letra, v in valores.items():
            linha += 1
            ws.cell(row=linha, column=2, value=letra)
            for j in range(len(datas)):
                ws.cell(row=linha, column=4 + j, value=v)
        linha += 2
    caminho = tmp_path / nome
    wb.save(caminho)
    return str(caminho)


_FEV_ABR = [(2026, 2), (2026, 3), (2026, 4)]


class TestImportarMemoriaErros:
    def test_trimestre_errado_informa_os_meses_da_planilha(self, tmp_path):
        r = PMPVUseCases.importar_memoria(_memoria(tmp_path, _FEV_ABR), ["Ago/2026", "Set/2026", "Out/2026"])
        assert r["meses"] == {}
        assert r["meses_encontrados"] == ["Fev/2026", "Mar/2026", "Abr/2026"]
        assert r["erros"] == ["A planilha não tem Ago/2026, Set/2026, Out/2026. Ela tem Fev/2026, Mar/2026, Abr/2026."]

    def test_trimestre_certo_continua_igual(self, tmp_path):
        r = PMPVUseCases.importar_memoria(_memoria(tmp_path, _FEV_ABR), ["Fev/2026", "Mar/2026", "Abr/2026"])
        assert set(r["meses"]) == {"Fev/2026", "Mar/2026", "Abr/2026"}
        assert r["meses"]["Fev/2026"][0]["volume"] == 1000
        assert r["erros"] == []

    def test_trimestre_parcial_importa_o_que_existe(self, tmp_path):
        r = PMPVUseCases.importar_memoria(_memoria(tmp_path, _FEV_ABR), ["Mar/2026", "Abr/2026", "Mai/2026"])
        assert set(r["meses"]) == {"Mar/2026", "Abr/2026"}
        assert r["erros"] == ["Mai/2026 não está na planilha (ela vai de Fev/2026 a Abr/2026)."]

    def test_aceita_o_mes_em_outro_formato(self, tmp_path):
        r = PMPVUseCases.importar_memoria(_memoria(tmp_path, _FEV_ABR), ["fev-26"])
        assert set(r["meses"]) == {"fev-26"}

    def test_celula_com_texto_aponta_empresa_e_linha(self, tmp_path):
        caminho = _memoria(tmp_path, _FEV_ABR, {"GALP": {"A": "N/D", "E": 500}})
        r = PMPVUseCases.importar_memoria(caminho, ["Fev/2026"])
        assert r["meses"] == {}
        assert "GALP" in r["erros"][0] and "linha A" in r["erros"][0] and "'N/D'" in r["erros"][0]
        assert "could not convert" not in r["erros"][0]

    def test_data_antiga_no_cabecalho_e_ignorada(self, tmp_path):
        r = PMPVUseCases.importar_memoria(_memoria(tmp_path, [(1900, 1)] + _FEV_ABR), ["Fev/2026"])
        assert r["meses_encontrados"] == ["Fev/2026", "Mar/2026", "Abr/2026"]

    def test_planilha_sem_linha_de_meses(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        wb = openpyxl.Workbook()
        wb.active.title = "PMPV"
        wb.active["B2"] = "sem datas aqui"
        caminho = tmp_path / "vazia.xlsx"
        wb.save(caminho)
        with pytest.raises(ValueError, match="linha de meses"):
            PMPVUseCases.importar_memoria(str(caminho), ["Jan/2026"])

    def test_arquivo_corrompido_nao_vaza_erro_tecnico(self, tmp_path):
        caminho = tmp_path / "quebrada.xlsx"
        caminho.write_bytes(b"isto nao e um excel")
        with pytest.raises(ValueError) as exc:
            PMPVUseCases.importar_memoria(str(caminho), ["Jan/2026"])
        msg = str(exc.value)
        assert "Não consegui abrir a planilha" in msg
        assert "zip" not in msg.lower() and "Traceback" not in msg
