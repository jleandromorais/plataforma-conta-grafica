"""Conciliação RP: serviço (servicos_concilia_lote) e API web. Banco
temporário via PLATAFORMA_DB. RP = despesas − receitas (planilha oficial)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_concilia_lote as lote
from Src.Services.servicos_concilia import PdfItem

RAIZ = Path(__file__).resolve().parents[1]
JAN = RAIZ / "SCG-26 - Copia" / "RP - Recuperação de Penalidades" / "Jan-26"
PASTA_DESP = JAN / "Penalidade-01 jan-26 Penalidade Falha de Programação (Despesa)"
PASTA_REC = JAN / "Receita-01 jan-26 Penalidade Falha de Programação (Receita)"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "rp_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _item(cat, valor, status="OK"):
    return PdfItem(file_name="a.pdf", file_path="a.pdf", category=cat, amount=valor, status=status, method="x")


def test_rp_e_despesas_menos_receitas_liquido_de_pis_cofins():
    t = lote.totais([_item("Despesa", 100.0), _item("Receita", 30.0), _item("Despesa", -10.0)])  # -10 = cancelada
    assert t["rp"] == pytest.approx(60.0 * 0.9075)
    assert t["total_receitas"] == pytest.approx(30.0 * 0.9075)


def test_salvar_grava_rp_e_scg_dos_modulos_bate(client):
    itens = [
        {"arquivo": "d.pdf", "caminho": "despesas/d.pdf", "categoria": "Despesa", "valor": 500.0, "status": "OK", "metodo": "x"},
        {"arquivo": "r.pdf", "caminho": "receitas/r.pdf", "categoria": "Receita", "valor": 200.0, "status": "OK", "metodo": "x"},
    ]
    resp = client.post("/api/conciliacao/salvar", json={"periodo": "Abr/2026", "itens": itens})
    assert resp.status_code == 200
    assert resp.json()["rp"] == pytest.approx(300.0 * 0.9075)
    comp = client.get("/api/scg/comparar", params={"periodo": "Abr/2026"}).json()
    assert comp["gravado"]["rp"] == pytest.approx(300.0 * 0.9075)
    assert comp["modulos"]["rp"] == pytest.approx(300.0 * 0.9075)  # mesma regra nos dois lados
    hist = {h["periodo"]: h for h in client.get("/api/conciliacao/historico").json()}
    assert hist["Abr/2026"]["rp_dos_itens"] == pytest.approx(hist["Abr/2026"]["rp_gravado"])


def test_salvar_recusa_periodo_invalido(client):
    resp = client.post("/api/conciliacao/salvar", json={"periodo": "jan", "itens": []})
    assert resp.status_code == 422


def test_relatorio(client):
    itens = [{"arquivo": "d.pdf", "caminho": "d.pdf", "categoria": "Despesa", "valor": 5.0, "status": "OK", "metodo": "x"}]
    resp = client.post("/api/conciliacao/relatorio", json={"periodo": "Abr/2026", "itens": itens})
    assert resp.status_code == 200 and resp.content[:2] == b"PK"


@pytest.mark.skipif(not (PASTA_DESP.exists() and PASTA_REC.exists()), reason="pastas reais de RP ausentes")
def test_pastas_reais_de_janeiro_igual_ao_desktop(client):
    """Mesmo resultado que a tela desktop lendo as pastas direto do disco, e
    igual à coluna jan-26 da planilha oficial "Conta Gráfica" (Penalidades).

    (Os itens gravados em Jan/2026 somam menos: na época, 3 PDFs de despesa
    não foram lidos — ficaram com valor 0 e status REVISAR.)"""
    esperado = lote.totais(lote.processar(PASTA_REC, PASTA_DESP))

    def campo(nome, pasta):
        return [(nome, (p.relative_to(pasta).as_posix(), p.read_bytes(), "application/pdf")) for p in sorted(pasta.rglob("*.pdf"))]

    resp = client.post("/api/conciliacao/processar", files=campo("receitas", PASTA_REC) + campo("despesas", PASTA_DESP))
    assert resp.status_code == 200, resp.text
    t = resp.json()["totais"]
    for k in ("total_despesas", "total_receitas", "rp"):
        assert t[k] == pytest.approx(esperado[k])
    # Planilha: PFP = 892.216,54; despesas = 86.214,11 + 14.306,72 + 89.541,95
    # (Petrolina = 15.764,98 bruto); Saldo de penalidade = −702.153,76.
    assert t["total_receitas"] == pytest.approx(892_216.54, abs=0.01)
    assert t["total_despesas"] == pytest.approx(190_062.78, abs=0.01)
    assert t["rp"] == pytest.approx(-702_153.76, abs=0.01)
