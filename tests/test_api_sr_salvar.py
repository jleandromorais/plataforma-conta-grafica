"""POST /api/sr/trimestre/salvar: o servidor confere as entradas e grava a conta DELE.

Valores fictícios; banco temporário. O PR automático que roda depois do salvar não acha
SCG/VP neste banco e só devolve pendências (não atrapalha o teste).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV

FECHADO = ["Jan/2025", "Fev/2025", "Mar/2025"]   # trimestre que já fechou
ABERTO = ["Jan/2099", "Fev/2099", "Mar/2099"]    # trimestre que ainda não fechou


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "sr_salvar.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    return str(caminho)


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _linha(mes: str, **troca) -> dict:
    # (1.000.000 − 900.000) × −0,0300 = −3.000; × 1,02 = −3.060,00
    linha = {"mes": mes, "vp": 1_000_000.0, "vf": 900_000.0, "pr": -0.03, "selic_mensal": 2.0,
             "sr_anterior": 0.0, "diferenca": 0.0, "sr_parcela": 0.0, "sr_selic": 0.0, "total": 0.0}
    return {**linha, **troca}


def _salvar(client, meses: list[str], linhas: list[dict]):
    return client.post("/api/sr/trimestre/salvar",
                       json={"labels_meses": meses, "periodo_referencia": meses[-1], "linhas": linhas})


def _gravado(banco: str, meses: list[str]) -> list[dict]:
    with DatabasePMPV(db_path=banco) as db:
        return db.buscar_sr_trimestre(f"{meses[0]}_{meses[-1]}")


def test_grava_o_valor_recalculado_pelo_servidor(client, banco):
    r = _salvar(client, FECHADO, [_linha(m) for m in FECHADO])  # a tela mandou sr_selic = 0
    assert r.status_code == 200, r.text
    assert r.json()["total"] == pytest.approx(-9_180.0)
    linhas = _gravado(banco, FECHADO)
    assert [l["sr_selic"] for l in linhas] == pytest.approx([-3_060.0] * 3)
    assert [l["diferenca"] for l in linhas] == pytest.approx([100_000.0] * 3)
    with DatabasePMPV(db_path=banco) as db:
        assert db.buscar_sr("Mar/2025")["sr"] == pytest.approx(-3_060.0)


def test_aceita_linha_sem_os_campos_calculados(client, banco):
    linhas = [{"mes": m, "vp": 1_000_000.0, "vf": 900_000.0, "pr": -0.03, "selic_mensal": 2.0} for m in FECHADO]
    r = _salvar(client, FECHADO, linhas)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == pytest.approx(-9_180.0)


@pytest.mark.parametrize("campo, trecho", [
    ("pr", "o PR está zerado ou ausente"),
    ("vp", "o VP está zerado"),
    ("selic_mensal", "a SELIC está 0%. Busque a SELIC"),
])
def test_zero_em_trimestre_fechado_da_422_e_nao_grava(client, banco, campo, trecho):
    linhas = [_linha(m) for m in FECHADO]
    linhas[1][campo] = 0.0
    r = _salvar(client, FECHADO, linhas)
    assert r.status_code == 422
    detalhe = r.json()["detail"]
    assert f"Fev/2025: {trecho}" in detalhe
    assert "Jan/2025" not in detalhe  # só o mês com problema
    assert _gravado(banco, FECHADO) == []


def test_pr_zero_aponta_a_chave_do_pr_do_mes(client):
    linhas = [_linha(m) for m in FECHADO]
    linhas[0]["pr"] = 0.0
    r = _salvar(client, FECHADO, linhas)
    assert "Salve o PR do trimestre Nov - Jan/2025" in r.json()["detail"]  # Jan/2025 → Nov/24–Jan/25


def test_selic_zero_em_trimestre_aberto_diz_que_nao_fechou(client, banco):
    r = _salvar(client, ABERTO, [_linha(m, selic_mensal=0.0) for m in ABERTO])
    assert r.status_code == 422
    assert "o trimestre ainda não fechou (fecha em 31/03/2099)" in r.json()["detail"]
    assert _gravado(banco, ABERTO) == []


def test_selic_digitada_a_mao_e_aceita(client, banco):
    r = _salvar(client, ABERTO, [_linha(m, selic_mensal=1.5) for m in ABERTO])
    assert r.status_code == 200, r.text
    assert [l["selic_mensal"] for l in _gravado(banco, ABERTO)] == [1.5] * 3


def test_numero_de_linhas_diferente_dos_meses_da_422(client, banco):
    r = _salvar(client, FECHADO, [_linha(FECHADO[0])])
    assert r.status_code == 422
    assert _gravado(banco, FECHADO) == []
