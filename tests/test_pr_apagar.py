"""DELETE /api/pr: apagar o PR salvo de um trimestre (simulação por padrão). Valores fictícios; banco temporário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "pr_apagar.db")
    with DatabasePMPV(db_path=caminho) as db:
        db.salvar_pr("Fev - Abr/2026", 1000.0, 0.0, 100.0, 0.0876)
        db.salvar_pr("Mai - Jul/2026", 1000.0, 0.0, 100.0, 0.01)
        db.salvar_pv_lote(["Fev - Abr/2026", "Fev/2026"], 2.0, 0.0876, 2.0876)
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _pr(banco: str, chave: str):
    with DatabasePMPV(db_path=banco) as db:
        return db.buscar_pr(chave)


def test_sem_aplicar_so_simula_e_nao_apaga(client, banco):
    r = client.delete("/api/pr", params={"periodo": "Fev - Abr/2026"})
    assert r.status_code == 200, r.text
    assert r.json() == {"periodo": "Fev - Abr/2026", "aplicado": False, "total_linhas": 1,
                        "tabelas": [{"tabela": "pr_resultados", "linhas": 1}]}
    assert _pr(banco, "Fev - Abr/2026")["pr"] == 0.0876


def test_aplicar_apaga_so_este_pr_e_deixa_o_pv(client, banco):
    r = client.delete("/api/pr", params={"periodo": "Fev - Abr/2026", "aplicar": "true"})
    assert r.status_code == 200 and r.json()["aplicado"] is True and r.json()["total_linhas"] == 1
    assert not _pr(banco, "Fev - Abr/2026")
    assert _pr(banco, "Mai - Jul/2026")["pr"] == 0.01      # outro trimestre intacto
    with DatabasePMPV(db_path=banco) as db:
        assert db.buscar_pv("Fev - Abr/2026")["pv"] == 2.0876  # o PV não é tocado


def test_apagar_o_que_nao_existe_da_404(client):
    r = client.delete("/api/pr", params={"periodo": "Ago - Out/2026", "aplicar": "true"})
    assert r.status_code == 404 and "Não há PR salvo para Ago - Out/2026" in r.json()["detail"]


@pytest.mark.parametrize("ruim", ["Jan/2026", "Teste1", "Fev - Abr"])
def test_chave_fora_do_formato_da_422_e_nao_apaga(client, banco, ruim):
    r = client.delete("/api/pr", params={"periodo": ruim, "aplicar": "true"})
    assert r.status_code == 422
    assert _pr(banco, "Fev - Abr/2026")["pr"] == 0.0876


def test_virada_de_ano_apaga_a_chave_com_o_ano_do_ultimo_mes(client, banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pr("Nov - Jan/2027", 0.0, 0.0, 0.0, -0.05)
    r = client.delete("/api/pr", params={"periodo": "Nov - Jan/2027", "aplicar": "true"})
    assert r.status_code == 200
    assert not _pr(banco, "Nov - Jan/2027")


def test_apagar_fica_na_trilha(client, banco):
    client.delete("/api/pr", params={"periodo": "Fev - Abr/2026", "aplicar": "true"})
    ultima = client.get("/api/trilha", params={"periodo": "Fev - Abr/2026", "tabela": "pr_resultados"}).json()[0]
    assert ultima["origem"] == "apagar" and ultima["valor_antigo"] == 0.0876 and ultima["valor_novo"] is None
