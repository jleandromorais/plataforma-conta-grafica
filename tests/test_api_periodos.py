"""Testes de DELETE /api/periodos/{nome} (limpeza de períodos com nome inválido).

Só usa banco temporário e valores fictícios.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV


def _notas(n: int) -> list[dict]:
    return [{"empresa": "Empresa A", "tipo": "NF-e", "numero": str(i), "valor_total": 1000.0} for i in range(n)]


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "periodos_teste.db"
    with DatabasePMPV(db_path=str(caminho)) as db:
        db.salvar_auditoria_itens("Teste2", _notas(3))
        db.salvar_auditoria_itens("Jan/2026", _notas(2))
        db.salvar_pmpv_mensal("Jan/2026", 2.5)
        db.salvar_pr("Nov - Jan/2027", 1000.0, 0.0, 100.0, 10.0)  # chave de trimestre real
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _contar(banco, tabela: str, periodo: str) -> int:
    with DatabasePMPV(db_path=str(banco)) as db:
        db.cursor.execute(f"SELECT COUNT(*) FROM {tabela} WHERE periodo = ?", (periodo,))
        return db.cursor.fetchone()[0]


def test_simulacao_por_padrao_nao_apaga(client, banco):
    r = client.delete("/api/periodos/Teste2")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["aplicado"] is False
    assert corpo["total_linhas"] == 3
    assert corpo["tabelas"] == [{"tabela": "auditoria_itens", "linhas": 3}]
    assert _contar(banco, "auditoria_itens", "Teste2") == 3


def test_aplicar_apaga_so_o_invalido(client, banco):
    r = client.delete("/api/periodos/Teste2?aplicar=true")
    assert r.status_code == 200
    assert r.json()["aplicado"] is True
    assert r.json()["total_linhas"] == 3
    assert _contar(banco, "auditoria_itens", "Teste2") == 0
    # o que é real continua lá
    assert _contar(banco, "auditoria_itens", "Jan/2026") == 2
    assert _contar(banco, "pmpv_mensal", "Jan/2026") == 1
    assert _contar(banco, "pr_resultados", "Nov - Jan/2027") == 1


@pytest.mark.parametrize("nome", ["Jan/2026", "jan/26", "JAN/2026"])
def test_periodo_valido_e_recusado(client, banco, nome):
    r = client.delete(f"/api/periodos/{nome}?aplicar=true")
    assert r.status_code == 400
    assert "período real" in r.json()["detail"]
    assert _contar(banco, "auditoria_itens", "Jan/2026") == 2


@pytest.mark.parametrize("nome", ["Nov - Jan/2027", "Q1/2026"])
def test_trimestre_real_e_recusado(client, banco, nome):
    r = client.delete(f"/api/periodos/{nome}?aplicar=true")
    assert r.status_code == 400
    assert _contar(banco, "pr_resultados", "Nov - Jan/2027") == 1


@pytest.mark.parametrize("nome", ["teste2", "TESTE2", "tEsTe2"])
def test_variacoes_de_caixa_acham_o_mesmo_periodo(client, banco, nome):
    sim = client.delete(f"/api/periodos/{nome}")
    assert sim.status_code == 200 and sim.json()["total_linhas"] == 3
    r = client.delete(f"/api/periodos/{nome}?aplicar=true")
    assert r.status_code == 200
    assert _contar(banco, "auditoria_itens", "Teste2") == 0


def test_inexistente_da_404(client):
    r = client.delete("/api/periodos/NaoExiste")
    assert r.status_code == 404
    assert "Não encontrei" in r.json()["detail"]


def test_exige_login(client):
    from Src.api.auth import usuario_atual
    from Src.api.main import app
    app.dependency_overrides.pop(usuario_atual, None)
    assert client.delete("/api/periodos/Teste2?aplicar=true").status_code in (401, 403)
