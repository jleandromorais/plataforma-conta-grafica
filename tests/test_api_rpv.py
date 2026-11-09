"""Testes da API web do RPV (Src/api/routers/rpv.py).

A tela desktop (tela_rpv.py) usa ServicosRPV; os testes conferem que a API
grava e lê exatamente o que o serviço grava/lê. Banco temporário via
PLATAFORMA_DB.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.servicos_rpv import ServicosRPV


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "rpv_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def test_periodo_inexistente_retorna_404(client):
    resp = client.get("/api/rpv", params={"periodo": "Jan/2030"})
    assert resp.status_code == 404


def test_salvar_cria_periodo_e_calcula_rpv(client):
    resp = client.post("/api/rpv/salvar", json={"periodo": "Mar/2026", "cgr": 3_982_585.0, "cgf": 5_172_827.66})
    assert resp.status_code == 200
    assert resp.json()["rpv"] == pytest.approx(3_982_585.0 - 5_172_827.66)

    lido = client.get("/api/rpv", params={"periodo": "Mar/2026"}).json()
    assert lido == pytest.approx({"cgr": 3_982_585.0, "cgf": 5_172_827.66, "rpv": 3_982_585.0 - 5_172_827.66})


def test_api_e_desktop_leem_o_mesmo_valor(client):
    client.post("/api/rpv/salvar", json={"periodo": "Abr/2026", "cgr": 100.0, "cgf": 40.0})
    servico = ServicosRPV()  # mesmo caminho da tela desktop
    try:
        assert servico.buscar_dados_periodo("Abr/2026") == client.get("/api/rpv", params={"periodo": "Abr/2026"}).json()
    finally:
        servico.consolidacao.fechar()


def test_salvar_de_novo_substitui_valores(client):
    client.post("/api/rpv/salvar", json={"periodo": "Mai/2026", "cgr": 10.0, "cgf": 5.0})
    client.post("/api/rpv/salvar", json={"periodo": "Mai/2026", "cgr": 1.0, "cgf": 9.0})
    assert client.get("/api/rpv", params={"periodo": "Mai/2026"}).json()["rpv"] == pytest.approx(-8.0)


def test_historico_lista_periodos_salvos(client):
    client.post("/api/rpv/salvar", json={"periodo": "Jan/2026", "cgr": 50.0, "cgf": 20.0})
    client.post("/api/rpv/salvar", json={"periodo": "Fev/2026", "cgr": 10.0, "cgf": 30.0})
    hist = {h["periodo"]: h for h in client.get("/api/rpv/historico").json()}
    assert hist["Jan/2026"]["rpv"] == pytest.approx(30.0)
    assert hist["Fev/2026"]["rpv"] == pytest.approx(-20.0)
    assert hist["Fev/2026"]["data_atualizacao"]


def test_prova_real_rpv_cgr_menos_cgf(client):
    client.post("/api/rpv/salvar", json={"periodo": "Mar/2026", "cgr": 3_982_585.0, "cgf": 5_172_827.66})
    p = client.get("/api/rpv/prova-real", params={"periodo": "Mar/2026"}).json()
    assert p["gravado"] is True
    assert p["rpv_calculado"] == pytest.approx(3_982_585.0 - 5_172_827.66)
    assert p["rpv_gravado"] == pytest.approx(p["rpv_calculado"])
    assert p["confere"] is True
    # Gravado só com os totais (sem notas nem resumo): dá para provar o RPV, não a origem.
    assert p["origem_cgr"]["tem_notas"] is False and p["origem_cgf"]["tem_resumo"] is False


def test_prova_real_rpv_mes_sem_dados(client):
    p = client.get("/api/rpv/prova-real", params={"periodo": "Dez/2030"}).json()
    assert p["gravado"] is False and p["confere"] is False and p["rpv_gravado"] is None


def test_prova_real_rpv_periodo_invalido(client):
    assert client.get("/api/rpv/prova-real", params={"periodo": "Teste"}).status_code == 422
