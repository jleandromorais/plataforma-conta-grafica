"""API do PV trimestral (GET /api/pv/trimestre, POST /api/pv/trimestre/salvar).

PV = PMPV + PR do mesmo trimestre fiscal; ao salvar, grava a chave do
trimestre e repete nos 3 meses. Banco temporário via PLATAFORMA_DB.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "pv_tri.db"
    with DatabasePMPV(db_path=str(banco)) as db:
        for p in ("Fev/2026", "Mar/2026", "Abr/2026"):
            db.salvar_pmpv_mensal(p, 1.9988)
        db.salvar_pr("Fev - Abr/2026", 0.0, 0.0, 0.0, -0.0321)
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c, banco


def test_buscar_trimestre(client):
    c, _ = client
    r = c.get("/api/pv/trimestre", params={"trimestre": "Fev - Abr", "ano": 2026})
    assert r.status_code == 200
    d = r.json()
    assert d["chave"] == "Fev - Abr/2026"
    assert d["periodos"] == ["Fev/2026", "Mar/2026", "Abr/2026"]
    assert d["pv"] == pytest.approx(1.9667)
    assert d["avisos"] == []


def test_salvar_trimestre_grava_os_3_meses(client):
    c, banco = client
    r = c.post("/api/pv/trimestre/salvar", json={"trimestre": "Fev - Abr", "ano": 2026, "pmpv": 1.9988, "pr": -0.0321})
    assert r.status_code == 200
    assert r.json()["gravado_em"] == ["Fev - Abr/2026", "Fev/2026", "Mar/2026", "Abr/2026"]
    with DatabasePMPV(db_path=str(banco)) as db:
        assert db.buscar_pv("Mar/2026")["pv"] == pytest.approx(1.9667)


def test_trimestre_invalido_retorna_422_com_mensagem(client):
    c, _ = client
    r = c.get("/api/pv/trimestre", params={"trimestre": "Jan - Mar", "ano": 2026})
    assert r.status_code == 422
    assert "Fev - Abr" in r.json()["detail"]


@pytest.mark.parametrize("ano", [0, 1999, 2099, 99999])
def test_ano_fora_da_faixa_retorna_422(client, ano):
    c, _ = client
    assert c.get("/api/pv/trimestre", params={"trimestre": "Fev - Abr", "ano": ano}).status_code == 422
    r = c.post("/api/pv/trimestre/salvar", json={"trimestre": "Fev - Abr", "ano": ano, "pmpv": 1.9988, "pr": 0.0})
    assert r.status_code == 422


def test_salvar_trimestre_invalido_retorna_422(client):
    c, _ = client
    r = c.post("/api/pv/trimestre/salvar", json={"trimestre": "Jan - Mar", "ano": 2026, "pmpv": 1.9988, "pr": 0.0})
    assert r.status_code == 422
    assert "Fev - Abr" in r.json()["detail"]


def test_historico_lista_os_trimestres_gravados(client):
    c, _ = client
    assert c.get("/api/pv/historico").json() == []  # nada gravado ainda
    c.post("/api/pv/trimestre/salvar", json={"trimestre": "Fev - Abr", "ano": 2026, "pmpv": 1.9988, "pr": -0.0321})
    h = c.get("/api/pv/historico").json()
    assert [(x["chave"], x["trimestre"], x["ano"]) for x in h] == [("Fev - Abr/2026", "Fev - Abr", 2026)]
    assert h[0]["pv"] == pytest.approx(1.9667)  # só o trimestre: os 3 meses ficam de fora


def test_prova_real_do_pv_confere_quando_os_modulos_nao_mudaram(client):
    c, _ = client
    c.post("/api/pv/trimestre/salvar", json={"trimestre": "Fev - Abr", "ano": 2026, "pmpv": 1.9988, "pr": -0.0321})
    p = c.get("/api/pv/prova-real", params={"trimestre": "Fev - Abr", "ano": 2026}).json()
    assert p["tem_salvo"] and p["conta_confere"] and p["pmpv_confere"] and p["pr_confere"] and p["confere"]
    assert p["pv_da_soma"] == pytest.approx(p["pmpv_gravado"] + p["pr_gravado"]) == pytest.approx(1.9667)


def test_prova_real_do_pv_acusa_pr_que_mudou_depois_de_gravar(client):
    c, banco = client
    c.post("/api/pv/trimestre/salvar", json={"trimestre": "Fev - Abr", "ano": 2026, "pmpv": 1.9988, "pr": -0.0321})
    with DatabasePMPV(db_path=str(banco)) as db:
        db.salvar_pr("Fev - Abr/2026", 0.0, 0.0, 0.0, -0.0400)  # o módulo PR passou a dar outro valor
    p = c.get("/api/pv/prova-real", params={"trimestre": "Fev - Abr", "ano": 2026}).json()
    assert p["conta_confere"] is True and p["pr_confere"] is False and p["confere"] is False
    assert p["pr_gravado"] == pytest.approx(-0.0321) and p["pr_atual"] == pytest.approx(-0.0400)


def test_prova_real_do_pv_sem_gravar(client):
    c, _ = client
    p = c.get("/api/pv/prova-real", params={"trimestre": "Fev - Abr", "ano": 2026}).json()
    assert p["tem_salvo"] is False and p["confere"] is False and p["pv_gravado"] is None
    assert p["pv_atual"] == pytest.approx(1.9667)  # o que os módulos dão hoje
