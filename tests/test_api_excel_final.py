"""Excel Final na web: gera a mesma planilha do desktop e devolve para download,
sem abrir o Excel no servidor. Banco temporário via PLATAFORMA_DB."""
from __future__ import annotations

import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters import excel_consolidado


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "xf_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    abertos = []
    monkeypatch.setattr(excel_consolidado.os, "startfile", lambda *a, **k: abertos.append(a), raising=False)
    from Src.api.main import app
    with TestClient(app) as c:
        c.abertos = abertos
        yield c


def test_gera_e_baixa_sem_abrir_o_excel(client):
    client.post("/api/scg/salvar", json={"periodo": "Mar/2026", "cgr": 1000.0, "cgf": 400.0, "ret": 30.0, "rp": -20.0})
    resp = client.post("/api/excel-final/gerar", params={"periodo": "Mar/2026"})
    assert resp.status_code == 200, resp.text
    assert "Excel_Final_ContaGrafica_Mar-2026.xlsx" in resp.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(resp.content))
    assert len(wb.sheetnames) > 3
    assert client.abertos == []  # não chamou os.startfile no servidor


def test_trimestre_e_periodo_invalido(client):
    assert client.get("/api/excel-final/trimestre", params={"periodo": "Mar/2026"}).status_code == 200
    assert client.post("/api/excel-final/gerar", params={"periodo": "março"}).status_code == 422


def test_aba_scg_mensal_usa_o_valor_gravado(client):
    """Mês sem itens de Auditoria (CGR digitado) e com SCG gravado: a aba SCG
    Mensal tem de trazer o gravado — antes recalculava pelos itens (CGR 0) e
    saía um SCG de −R$ 78 mi, diferente da aba Dashboard do mesmo arquivo."""
    client.post("/api/scg/salvar", json={"periodo": "Jul/2025", "cgr": 84_500_000.0, "cgf": 79_200_000.0, "ret": 1_120_000.0, "rp": -320_000.0})
    resp = client.post("/api/excel-final/gerar", params={"periodo": "Jul/2025"})
    ws = openpyxl.load_workbook(io.BytesIO(resp.content), data_only=True)["🧾 SCG Mensal"]
    linhas = [r for r in ws.iter_rows(values_only=True)]
    meses = next(r for r in linhas if r and r[0] == "DADOS")[2:-1]
    scg = next(r for r in linhas if r and isinstance(r[0], str) and r[0].startswith("SCG"))[2:-1]
    assert dict(zip(meses, scg))["Jul/2025"] == pytest.approx(84_500_000 - 79_200_000 + 1_120_000 - 320_000)
