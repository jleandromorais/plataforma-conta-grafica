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
    # Fev: 458.580,09 na planilha Conta Gráfica (linha 42). O 549.420,99 antigo vinha da leitura
    # errada dos PDFs com número quebrado ("1 .335,86"), corrigida em 3353905.
    assert obtido["Fev/2026"] == pytest.approx(458_580.09, abs=0.01)
    assert obtido["Mar/2026"] == pytest.approx(640_451.24, abs=0.01)

    salvos = client.post("/api/ret/salvar", json={"documentos": r["documentos"]}).json()
    assert {s["periodo"]: s["ret"] for s in salvos} == pytest.approx(esperado)  # um RET por mês
    assert client.get("/api/rpv", params={"periodo": "Jan/2026"}).status_code == 200
    hist = {h["periodo"]: h for h in client.get("/api/ret/historico").json()}
    assert hist["Mar/2026"]["ret_gravado"] == pytest.approx(640_451.24, abs=0.01)


# ---------------------------------------------------------------- prova real

def _doc(tipo: str, valor: float, empresa: str = "Empresa A", mes: str = "Jan/2026") -> dict:
    return {"arquivo": f"{tipo}_{empresa}.pdf", "caminho": f"{tipo}/{mes}/a.pdf", "tipo_encargo": tipo,
            "empresa": empresa, "nota_tipo": "Débito", "numero_nd": "1", "data_vencimento": "",
            "valor_total": valor, "mes_ref": mes}


def _salvar(client, docs):
    resp = client.post("/api/ret/salvar", json={"documentos": docs})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_prova_real_ret_confere_com_o_gravado(client):
    # Valores fictícios: EAT 100.000 e EC 50.000 → RET = 100.000 × 0,9075 + 50.000 = 140.750
    _salvar(client, [_doc("EAT", 60_000.0, "Empresa A"), _doc("EAT", 40_000.0, "Empresa B"),
                     _doc("EC", 50_000.0, "Empresa A")])
    r = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["tem_itens"] is True
    assert (p["qtd_documentos"], p["qtd_eat"], p["qtd_ec"], p["qtd_outros"]) == (3, 2, 1, 0)
    assert p["eat_bruto"] == pytest.approx(100_000.0)
    assert p["pis_cofins_rate"] == pytest.approx(0.0925)
    assert p["eat_liquido"] == pytest.approx(90_750.0)
    assert p["ec"] == pytest.approx(50_000.0)
    assert p["ret_calculado"] == pytest.approx(140_750.0)
    assert p["ret_gravado"] == pytest.approx(140_750.0)
    assert p["diferenca"] == pytest.approx(0.0)
    assert p["confere"] is True
    assert [(e["empresa"], e["tipo_encargo"], e["qtd"]) for e in p["por_empresa"]] == [
        ("Empresa A", "EAT", 1), ("Empresa A", "EC", 1), ("Empresa B", "EAT", 1)]
    assert [e["valor"] for e in p["por_empresa"]] == [60_000.0, 50_000.0, 40_000.0]  # maior primeiro
    assert p["data_atualizacao"] != ""


def test_prova_real_ret_reproduz_jan_2026_so_com_ec(client):
    # Jan/2026 da planilha oficial: EAT 0,00 + EC = 1.760.685,43
    _salvar(client, [_doc("EC", 1_000_000.00), _doc("EC", 760_685.43, "Empresa B")])
    p = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    assert p["eat_bruto"] == 0.0
    assert p["ret_calculado"] == pytest.approx(1_760_685.43, abs=0.01)
    assert p["confere"] is True


def test_prova_real_ret_sem_itens(client):
    p = client.get("/api/ret/prova-real", params={"periodo": "Fev/2026"}).json()
    assert p["tem_itens"] is False
    assert p["confere"] is False
    assert p["ret_calculado"] is None and p["ret_gravado"] is None and p["diferenca"] is None
    assert p["por_empresa"] == []


def test_prova_real_ret_periodo_invalido_422(client):
    r = client.get("/api/ret/prova-real", params={"periodo": "Teste2"})
    assert r.status_code == 422
    assert "período" in r.json()["detail"]


def test_prova_real_ret_gravado_diferente_dos_itens(client, tmp_path):
    _salvar(client, [_doc("EAT", 100_000.0), _doc("EC", 50_000.0)])
    with DatabasePMPV(db_path=str(tmp_path / "ret_teste.db")) as db:
        db.cursor.execute("UPDATE consolidacao SET ret = ? WHERE periodo = ?", (100_000.0, "Jan/2026"))
        db.conn.commit()
    p = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    assert p["ret_gravado"] == pytest.approx(100_000.0)
    assert p["diferenca"] == pytest.approx(40_750.0)
    assert p["confere"] is False


def test_prova_real_ret_outros_nao_entram(client):
    _salvar(client, [_doc("EAT", 100_000.0), _doc("EC", 50_000.0),
                     _doc("TOP", 9_999.0), _doc("Outros", 777.0), _doc("Penalidades (Receita)", 5_000.0)])
    p = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    assert p["qtd_documentos"] == 5 and p["qtd_outros"] == 3
    assert p["ret_calculado"] == pytest.approx(140_750.0)
    assert p["confere"] is True
    assert {e["tipo_encargo"] for e in p["por_empresa"]} == {"EAT", "EC"}
