"""RET: serviço em lote (servicos_ret_lote) e API web. Banco temporário via
PLATAFORMA_DB. O teste principal usa a pasta real do 1º trimestre/2026."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_ret_lote as lote_ret
from Src.Services.servicos_ret import RegrasRET

RAIZ = Path(__file__).resolve().parents[1]
PASTA_TRI = RAIZ / "SCG-26 - Copia" / "RET - Recuperação de Encargos de Transporte" / "RET-jan-mar-26"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "ret_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def test_agrupar_por_mes_separa_o_trimestre():
    docs = [{"mes_ref": "Jan/2026", "tipo_encargo": "EAT", "valor_total": 100.0},
            {"mes_ref": "Fev/2026", "tipo_encargo": "EAT", "valor_total": 50.0},
            {"mes_ref": "", "tipo_encargo": "EC", "valor_total": 7.0}]
    grupos = lote_ret.agrupar_por_mes(docs, periodo_padrao="Mar/2026")
    assert set(grupos) == {"Jan/2026", "Fev/2026", "Mar/2026"}


def test_salvar_recusa_documento_sem_mes(client):
    resp = client.post("/api/ret/salvar", json={"documentos": [{
        "arquivo": "a.pdf", "caminho": "EAT/a.pdf", "tipo_encargo": "EAT", "empresa": "X",
        "nota_tipo": "Débito", "numero_nd": "1", "data_vencimento": "", "valor_total": 10.0,
    }]})
    assert resp.status_code == 422
    assert "mês" in resp.json()["detail"]


def test_processar_sem_pdf_retorna_422(client):
    resp = client.post("/api/ret/processar", files=[("arquivos", ("EAT/a.txt", b"x", "text/plain"))])
    assert resp.status_code == 422


@pytest.mark.skipif(not PASTA_TRI.exists(), reason="pasta real do RET ausente")
def test_pasta_real_do_trimestre_por_mes(client):
    docs, _, _ = lote_ret.processar_pasta(PASTA_TRI)
    esperado = {p: RegrasRET.calcular_ret(ds)["ret"] for p, ds in lote_ret.agrupar_por_mes(docs).items()}

    pdfs = sorted(PASTA_TRI.rglob("*.pdf"), key=str) + sorted(PASTA_TRI.rglob("*.PDF"), key=str)
    handles = [p.open("rb") for p in pdfs]
    try:
        arquivos = [("arquivos", (p.relative_to(PASTA_TRI).as_posix(), h, "application/pdf")) for p, h in zip(pdfs, handles)]
        resp = client.post("/api/ret/processar", files=arquivos, data={"pasta_raiz": PASTA_TRI.name})
    finally:
        for h in handles:
            h.close()
    assert resp.status_code == 200, resp.text
    r = resp.json()
    obtido = {m["periodo"]: m["ret"] for m in r["meses"]}
    assert obtido == pytest.approx(esperado)
    # valores conferidos contra a planilha oficial (Excel Final, aba RET)
    assert obtido["Jan/2026"] == pytest.approx(1_760_685.43, abs=0.01)
    assert obtido["Fev/2026"] == pytest.approx(549_420.99, abs=0.01)
    assert obtido["Mar/2026"] == pytest.approx(640_451.24, abs=0.01)

    salvos = client.post("/api/ret/salvar", json={"documentos": r["documentos"]}).json()
    assert {s["periodo"]: s["ret"] for s in salvos} == pytest.approx(esperado)  # um RET por mês
    assert client.get("/api/rpv", params={"periodo": "Jan/2026"}).status_code == 200
    hist = {h["periodo"]: h for h in client.get("/api/ret/historico").json()}
    assert hist["Mar/2026"]["ret_gravado"] == pytest.approx(640_451.24, abs=0.01)
