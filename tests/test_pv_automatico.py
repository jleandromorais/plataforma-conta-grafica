"""PV regravado ao salvar o PMPV ou o PR (servicos_pr_automatico.atualizar_pv). Valores fictícios."""
import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.tarifa import servicos_pr_automatico as auto


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "pv_auto.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    return caminho


@pytest.mark.parametrize("periodo, esperado", [
    ("Nov/2026", ("Nov - Jan", 2026)), ("Dez/2026", ("Nov - Jan", 2026)),
    ("Jan/2027", ("Nov - Jan", 2026)), ("Abr/2026", ("Fev - Abr", 2026)),
    ("Mai/2026", ("Mai - Jul", 2026)), ("Out/2026", ("Ago - Out", 2026)),
])
def test_trimestre_do_ciclo(periodo, esperado):
    assert auto._trimestre_do_ciclo(periodo) == esperado


def test_pmpv_com_pr_salvo_regrava_pv(banco):
    with DatabasePMPV(db_path=str(banco)) as db:
        for p in ("Fev/2026", "Mar/2026", "Abr/2026"):
            db.salvar_pmpv_mensal(p, 2.0)
        db.salvar_pr("Fev - Abr/2026", 0.0, 0.0, 0.0, 0.1)
    r = auto.atualizar_pv(["Fev/2026", "Mar/2026", "Abr/2026"])
    assert len(r) == 1 and r[0]["trimestre"] == "Fev - Abr/2026"
    assert r[0]["atualizado"] is True and r[0]["pv"] == pytest.approx(2.1)
    with DatabasePMPV(db_path=str(banco)) as db:
        assert db.buscar_pv("Mar/2026")["pv"] == pytest.approx(2.1)


def test_sem_pr_salvo_nao_grava(banco):
    with DatabasePMPV(db_path=str(banco)) as db:
        db.salvar_pmpv_mensal("Mai/2026", 2.0)
    r = auto.atualizar_pv(["Mai/2026"])[0]
    assert r["atualizado"] is False and r["pv"] is None
    assert any("falta o PR salvo de Mai - Jul/2026" in p for p in r["pendencias"])
    with DatabasePMPV(db_path=str(banco)) as db:
        assert not db.buscar_pv("Mai - Jul/2026")


def test_virada_de_ano(banco):
    with DatabasePMPV(db_path=str(banco)) as db:
        for p in ("Nov/2026", "Dez/2026", "Jan/2027"):
            db.salvar_pmpv_mensal(p, 2.0)
        db.salvar_pr("Nov - Jan/2027", 0.0, 0.0, 0.0, -0.05)  # o PR usa o ano do último mês
    r = auto.atualizar_pv(["Jan/2027"])[0]
    assert r["trimestre"] == "Nov - Jan/2026"  # o PV usa o ano do 1º mês
    assert r["pv"] == pytest.approx(1.95)
    with DatabasePMPV(db_path=str(banco)) as db:
        for chave in ("Nov - Jan/2026", "Nov/2026", "Dez/2026", "Jan/2027"):
            assert db.buscar_pv(chave)["pv"] == pytest.approx(1.95)


def test_api_pr_salvar_regrava_pv(banco, monkeypatch):
    # O /pr/salvar agora refaz a apuração no servidor (banco vazio daria 422): aqui a apuração é
    # trocada por uma pronta, sem pendência, porque o que se testa é o PV regravado junto.
    from Src.Services.tarifa.servicos_pr import ServicosPR
    monkeypatch.setattr(ServicosPR, "apurar_trimestre", lambda self, meses: {
        "scg_selic": 1000.0, "sr": 0.0, "vp": 10000.0, "pendencias": []})
    with DatabasePMPV(db_path=str(banco)) as db:
        for p in ("Ago/2026", "Set/2026", "Out/2026"):
            db.salvar_pmpv_mensal(p, 2.0)
    from Src.api.main import app
    with TestClient(app) as c:
        resp = c.post("/api/pr/salvar", json={"periodo": "Ago - Out/2026"})
    assert resp.status_code == 200, resp.text
    pv = resp.json()["pv_automatico"]
    assert pv["trimestre"] == "Ago - Out/2026" and pv["atualizado"] is True
    assert pv["pv"] == pytest.approx(2.0 + resp.json()["pr"])


def test_api_pmpv_mensal_continua_204_e_regrava_pv(banco):
    with DatabasePMPV(db_path=str(banco)) as db:
        db.salvar_pr("Fev - Abr/2026", 0.0, 0.0, 0.0, 0.1)
    from Src.api.main import app
    with TestClient(app) as c:
        assert c.post("/api/pmpv/mensal/Fev/2026", json={"pmpv": 2.0}).status_code == 204
    with DatabasePMPV(db_path=str(banco)) as db:
        assert db.buscar_pv("Fev - Abr/2026")["pv"] == pytest.approx(2.1)


def test_falha_vira_pendencia(monkeypatch):
    def quebra(_periodos):
        raise RuntimeError("x")
    monkeypatch.setattr(auto, "atualizar_pv", quebra)
    r = auto.atualizar_pv_sem_falhar(["Fev/2026"])
    assert r[0]["atualizado"] is False and "Salve pela tela do PV" in r[0]["pendencias"][0]
