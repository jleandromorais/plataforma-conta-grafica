"""Testes da API web do CGF (Src/api/routers/cgf.py).

A tela desktop (tela_cgf.py) usa ServicosCGF.processar_arquivos; os testes
conferem que a API dá o mesmo resultado com as mesmas planilhas, e que salvar
exige PMPV (o desktop gravava m³ no campo do CGF em R$ quando faltava).
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.servicos_cgf import ServicosCGF

RAIZ = Path(__file__).resolve().parents[1]
REAIS = [RAIZ / "NF Faturadas e complementares 01.26.xlsx",
         RAIZ / "NF Canceladas e denegadas 01.26.xlsx",
         RAIZ / "NF Devolvidas 01.26.xlsx"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "cgf_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _arquivos_sinteticos():
    fat = pd.DataFrame({"Produto": ["Gás", "Gás", "Consumo Proprio"], "Volume Faturado": ["1.000,50", "2000", "300"]})
    canc = pd.DataFrame({"Volume Canc/Deneg": [40.0]})
    dev = pd.DataFrame({"Volume Devolução": [100.25]})
    xl = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return [
        ("arquivos", ("NF Faturadas 03.26.xlsx", _xlsx(fat), xl)),
        ("arquivos", ("NF Canceladas 03.26.xlsx", _xlsx(canc), xl)),
        ("arquivos", ("NF Devolvidas 03.26.xlsx", _xlsx(dev), xl)),
    ]


def test_processar_calcula_volumes_e_detecta_periodo(client):
    resp = client.post("/api/cgf/processar", files=_arquivos_sinteticos())
    assert resp.status_code == 200
    r = resp.json()
    assert r["volume_faturado"] == pytest.approx(3000.5)      # sem o consumo próprio
    assert r["volume_consumo_proprio"] == pytest.approx(300.0)
    assert r["volume_canceladas"] == pytest.approx(40.0)
    assert r["volume_devolucoes"] == pytest.approx(100.25)
    assert r["volume_final"] == pytest.approx(3000.5 - 100.25)  # canceladas não entram
    assert r["periodo_detectado"] == "Mar/2026"
    assert r["arquivos_ignorados"] == []


def test_processar_avisa_arquivo_sem_tipo_no_nome(client):
    xl = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    arquivos = _arquivos_sinteticos() + [("arquivos", ("planilha qualquer.xlsx", _xlsx(pd.DataFrame({"a": [1]})), xl))]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    assert r["arquivos_ignorados"] == ["planilha qualquer.xlsx"]


def test_processar_rejeita_arquivo_que_nao_e_planilha(client):
    resp = client.post("/api/cgf/processar", files=[("arquivos", ("NF Faturadas.pdf", b"%PDF", "application/pdf"))])
    assert resp.status_code == 422


@pytest.mark.skipif(not all(p.exists() for p in REAIS), reason="planilhas de NF de exemplo ausentes")
def test_processar_planilhas_reais_igual_ao_desktop(client):
    esperado = ServicosCGF().processar_arquivos(
        [str(p) for p in REAIS], "Volume Faturado", "Produto", "consumo proprio", "Volume Canc/Deneg", "Volume Devolução",
    )
    handles = [p.open("rb") for p in REAIS]
    try:
        r = client.post("/api/cgf/processar", files=[("arquivos", (p.name, h, "application/octet-stream")) for p, h in zip(REAIS, handles)]).json()
    finally:
        for h in handles:
            h.close()
    for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final"):
        assert r[k] == pytest.approx(esperado[k])
    assert r["periodo_detectado"] == "Jan/2026"


def test_salvar_exige_pmpv(client):
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    payload = {k: r[k] for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final")}
    resp = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mar/2026", "pmpv": 0})
    assert resp.status_code == 422
    assert "PMPV" in resp.json()["detail"]
    assert client.get("/api/rpv", params={"periodo": "Mar/2026"}).status_code == 404  # nada gravado


def test_salvar_grava_cgf_em_reais_e_resumo(client):
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    payload = {k: r[k] for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final")}
    resp = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mar/2026", "pmpv": 2.5})
    assert resp.status_code == 200
    assert resp.json()["cgf_rs"] == pytest.approx(r["volume_final"] * 2.5)

    assert client.get("/api/rpv", params={"periodo": "Mar/2026"}).json()["cgf"] == pytest.approx(r["volume_final"] * 2.5)
    hist = {h["periodo"]: h for h in client.get("/api/cgf/historico").json()}
    assert hist["Mar/2026"]["volume_final"] == pytest.approx(r["volume_final"])
    assert hist["Mar/2026"]["cgf_rs"] == pytest.approx(r["volume_final"] * 2.5)


def test_cgf_usa_pmpv_com_4_casas_como_o_desktop(client):
    """O desktop carrega o PMPV como f"{pmpv:.4f}" antes de multiplicar."""
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    payload = {k: r[k] for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final")}
    pmpv_banco = 2.282982647346896
    cgf = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mai/2026", "pmpv": pmpv_banco}).json()["cgf_rs"]
    assert cgf == pytest.approx(r["volume_final"] * float(f"{pmpv_banco:.4f}"))
