"""GET /api/sr/historico e /api/sr/prova-real: a conta do SR gravado refeita e comparada com as
fontes de hoje (só lê, não grava). Números do Quadro 6 da NT (Jan-Mar/26). Banco temporário via
PLATAFORMA_DB; a SELIC do Banco Central é sempre falsa: nenhum teste chama a internet.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.application.use_cases.sr_use_cases import SRUseCases
from Src.Database.database import DatabasePMPV
from Src.Services import servicos_selic

TRI = "Jan/2026_Mar/2026"
MESES = ["Jan/2026", "Fev/2026", "Mar/2026"]
VP = [48143000.0, 42224000.0, 46748000.0]
VF = [41805735.80, 39940612.96, 44979282.33]
PR = [-0.0210, -0.0321, -0.0321]
SELIC = {"Jan/2026": 3.411174, "Fev/2026": 2.22116, "Mar/2026": 1.212054}


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "sr_prova.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", lambda meses, hoje=None, buscar=None: {
        "disponivel": True, "valores": dict(SELIC), "fecha_em": "2026-03-31", "fonte": "Banco Central (série 11)"})
    return str(caminho)


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _fontes(banco: str) -> None:
    """VP, VF e PR que as fontes dizem hoje."""
    with DatabasePMPV(db_path=banco) as db:
        for i, mes in enumerate(MESES):
            db.salvar_vp_periodo(mes, VP[i])
            db.salvar_cgf_resumo(mes, 0, 0, 0, 0, VF[i])
        db.salvar_pr("Nov - Jan/2026", 0, 0, 1, PR[0])
        db.salvar_pr("Fev - Abr/2026", 0, 0, 1, PR[1])


def _gravar(banco: str, selic: dict | None = None, trimestre: str = TRI, meses=MESES) -> None:
    """Grava o trimestre como o /trimestre/salvar faz: com a conta de calcular_trimestre."""
    selic = SELIC if selic is None else selic
    entradas = [{"mes": m, "vp": VP[i], "vf": VF[i], "pr": PR[i], "selic_mensal": selic.get(m, 0.0), "sr_anterior": 0.0}
                for i, m in enumerate(meses)]
    linhas = SRUseCases.calcular_trimestre(entradas)["linhas"]
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_sr_trimestre(trimestre, linhas)


def _prova(client, trimestre: str = TRI):
    return client.get("/api/sr/prova-real", params={"trimestre": trimestre})


def test_prova_real_fecha_com_a_planilha_oficial(client, banco):
    _fontes(banco)
    _gravar(banco)
    r = _prova(client)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["gravado"] is True and j["labels_meses"] == MESES
    for linha, sr in zip(j["linhas"], [-137622.23, -74924.76, -57463.99]):
        assert linha["conta_confere"] is True
        assert linha["sr_selic_recalculado"] == pytest.approx(sr, abs=0.05)
        assert linha["diferenca"] == pytest.approx(linha["vp"] - linha["vf"])
        assert linha["sr_parcela"] == pytest.approx(linha["diferenca"] * linha["pr"])
        assert linha["fontes"]["diferem"] == []
    assert j["total_gravado"] == pytest.approx(-270010.98, abs=0.1)
    assert j["total_recalculado"] == pytest.approx(j["total_gravado"])
    assert j["conta_confere"] is True and j["fontes_disponiveis"] is True
    assert "difere_gravado" not in [a["codigo"] for a in j["alertas"]]


def test_prova_real_nao_grava_nada(client, banco):
    _fontes(banco)
    _gravar(banco)
    with DatabasePMPV(db_path=banco) as db:
        antes = db.buscar_sr_trimestre(TRI)
    _prova(client)
    with DatabasePMPV(db_path=banco) as db:
        assert db.buscar_sr_trimestre(TRI) == antes


def test_gravado_com_selic_zero_e_fonte_dando_selic(client, banco):
    _fontes(banco)
    _gravar(banco, selic={m: 0.0 for m in MESES})
    j = _prova(client).json()
    assert j["conta_confere"] is True  # a conta do gravado está certa; o que está errado é o insumo
    assert all("selic_mensal" in l["fontes"]["diferem"] for l in j["linhas"])
    assert j["linhas"][0]["fontes"]["selic_mensal"] == pytest.approx(3.411174)
    assert "selic_zero_gravada" in [a["codigo"] for a in j["alertas"]]


def test_conta_gravada_errada_nao_confere(client, banco):
    _fontes(banco)
    _gravar(banco)
    with DatabasePMPV(db_path=banco) as db:
        db.cursor.execute("UPDATE sr_trimestre SET sr_selic = sr_selic + 5 WHERE mes = 'Fev/2026'")
        db.conn.commit()
    j = _prova(client).json()
    assert [l["conta_confere"] for l in j["linhas"]] == [True, False, True]
    assert j["conta_confere"] is False


def test_fonte_com_vp_diferente_aparece_em_diferem(client, banco):
    _fontes(banco)
    _gravar(banco)
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_vp_periodo("Mar/2026", VP[2] + 5000)
    j = _prova(client).json()
    assert j["linhas"][2]["fontes"]["diferem"] == ["vp"]
    assert j["linhas"][0]["fontes"]["diferem"] == []
    assert "difere_gravado" in [a["codigo"] for a in j["alertas"]]


def test_selic_fora_do_ar_nao_derruba(client, banco, monkeypatch):
    _fontes(banco)
    _gravar(banco)

    def fora_do_ar(meses, hoje=None, buscar=None):
        raise servicos_selic.SelicIndisponivel("O Banco Central não respondeu.")
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", fora_do_ar)
    r = _prova(client)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["conta_confere"] is True
    assert j["fontes_disponiveis"] is True
    assert j["linhas"][0]["fontes"]["selic_mensal"] is None
    assert "selic_mensal" not in j["linhas"][0]["fontes"]["diferem"]
    assert "selic_indisponivel" in [a["codigo"] for a in j["alertas"]]


def test_trimestre_inexistente(client):
    j = _prova(client, "Out/2025_Dez/2025").json()
    assert j["gravado"] is False and j["linhas"] == []
    assert j["conta_confere"] is False and j["fontes_disponiveis"] is False
    assert j["labels_meses"] == ["Out/2025", "Nov/2025", "Dez/2025"]


@pytest.mark.parametrize("ruim", ["Jan/2026", "Jan/2026_Abr/2026", "Jan/2026_Fev/2026", "xx_yy", "", "Jan/2026_Mar/2026_Jun/2026"])
def test_trimestre_mal_formado_422(client, ruim):
    assert _prova(client, ruim).status_code == 422


def test_historico_lista_do_mais_recente_ao_mais_antigo(client, banco):
    assert client.get("/api/sr/historico").json() == []
    _gravar(banco)
    _gravar(banco, trimestre="Out/2025_Dez/2025", meses=["Out/2025", "Nov/2025", "Dez/2025"])
    lista = client.get("/api/sr/historico").json()
    assert [h["trimestre"] for h in lista] == [TRI, "Out/2025_Dez/2025"]
    assert lista[0]["labels_meses"] == MESES and lista[0]["qtd_meses"] == 3
    assert lista[0]["total"] == pytest.approx(-270010.98, abs=0.1)
    assert lista[0]["data_atualizacao"]
