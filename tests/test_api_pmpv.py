"""Testes da API web do PMPV (Src/api/routers/pmpv.py).

Regra da migração: a API deve dar o MESMO resultado que o desktop. Como a tela
desktop (tela_pmpv.py) chama PMPVUseCases/RegrasPMPV/ExcelPMPV, os testes
comparam a resposta HTTP com essas chamadas diretas. Cada teste usa um banco
SQLite temporário via PLATAFORMA_DB.
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.servicos_pmpv import ExcelPMPV, RegrasPMPV

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
PERIODOS = ["Fev/2026", "Mar/2026", "Abr/2026"]
MEMORIA = Path(__file__).resolve().parents[1] / "_dados_referencia" / "Memória de Cálculo.xlsx"


def _linha(empresa, mol, trans, log, vol):
    return {"empresa": empresa, "molecula": mol, "transporte": trans,
            "logistica": log, "volume": vol, "campos_vazios": []}


DADOS = {
    "Mês 1": [_linha("PETROBRAS", 2.1, 0.3, 0.05, 1_200_000), _linha("GALP", 2.0, 0.25, 0.0, 300_000)],
    "Mês 2": [_linha("PETROBRAS", 2.2, 0.3, 0.05, 1_100_000)],
    "Mês 3": [_linha("PETROBRAS", 2.3, 0.31, 0.05, 1_000_000), _linha("BRAVA", 1.9, 0.2, 0.0, 50_000)],
}
DIAS = {"Mês 1": 28, "Mês 2": 31, "Mês 3": 30}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "pmpv_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass  # cria as tabelas
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _payload_calculo():
    return {"dados_extraidos": DADOS, "valor_cg": -0.021, "dias_config": DIAS,
            "lista_meses": MESES, "idx_start": 1}


def test_calcular_igual_ao_desktop(client):
    resp = client.post("/api/pmpv/calcular", json=_payload_calculo())
    assert resp.status_code == 200
    esperado = RegrasPMPV.calcular_resultados(DADOS, -0.021, DIAS, MESES, 1)
    obtido = resp.json()
    for chave in ("pmpv", "preco_final", "vp_mensal", "volume_total", "custo_total"):
        assert obtido[chave] == pytest.approx(esperado[chave])
    assert obtido["vp_por_mes"] == pytest.approx(esperado["vp_por_mes"])


def test_calcular_sem_volume_retorna_422_com_mensagem(client):
    payload = _payload_calculo()
    payload["dados_extraidos"] = {"Mês 1": [_linha("X", 1, 1, 1, 0)]}
    resp = client.post("/api/pmpv/calcular", json=payload)
    assert resp.status_code == 422
    assert "Volume Zero" in resp.json()["detail"]


def test_salvar_grava_sessao_pmpv_mensal_e_trimestre_ativo(client):
    resultado = client.post("/api/pmpv/calcular", json=_payload_calculo()).json()
    resp = client.post("/api/pmpv/salvar", json={
        "nome": "PMPV_Fev_Abr_2026", "dados_por_mes": DADOS,
        "resultado": resultado, "periodos": PERIODOS,
    })
    assert resp.status_code == 200
    assert resp.json()["sessao_id"] > 0

    for periodo in PERIODOS:
        mensal = client.get(f"/api/pmpv/mensal/{periodo}").json()
        assert mensal["pmpv"] == pytest.approx(resultado["pmpv"])
    assert client.get("/api/pmpv/trimestre-ativo").json()["meses"] == PERIODOS


def test_salvar_sem_periodos_continua_compativel(client):
    resultado = client.post("/api/pmpv/calcular", json=_payload_calculo()).json()
    resp = client.post("/api/pmpv/salvar", json={
        "nome": "antigo", "dados_por_mes": DADOS, "resultado": resultado,
    })
    assert resp.status_code == 200
    assert client.get("/api/pmpv/trimestre-ativo").json()["meses"] == []


def test_historico_lista_sessoes_da_mais_recente(client):
    assert client.get("/api/pmpv/historico").json() == []

    resultado = client.post("/api/pmpv/calcular", json=_payload_calculo()).json()
    for nome in ("PMPV_A", "PMPV_B"):
        client.post("/api/pmpv/salvar", json={
            "nome": nome, "dados_por_mes": DADOS, "resultado": resultado, "periodos": PERIODOS,
        })

    historico = client.get("/api/pmpv/historico").json()
    assert [h["nome"] for h in historico] == ["PMPV_B", "PMPV_A"]
    h = historico[0]
    assert h["pmpv"] == pytest.approx(resultado["pmpv"])
    assert h["conta_grafica"] == pytest.approx(-0.021)
    assert h["preco_final"] == pytest.approx(resultado["preco_final"])
    assert h["vp"] == pytest.approx(resultado["vp_mensal"])
    assert h["data_criacao"]


def test_trimestre_ativo_ida_e_volta(client):
    assert client.post("/api/pmpv/trimestre-ativo", json={"meses": PERIODOS}).status_code == 204
    assert client.get("/api/pmpv/trimestre-ativo").json()["meses"] == PERIODOS


def test_importar_memoria_rejeita_arquivo_que_nao_e_planilha(client):
    resp = client.post(
        "/api/pmpv/importar-memoria",
        files={"arquivo": ("notas.txt", io.BytesIO(b"oi"), "text/plain")},
        data={"periodos": ",".join(PERIODOS)},
    )
    assert resp.status_code == 422
    assert ".xlsx" in resp.json()["detail"]


@pytest.mark.skipif(not MEMORIA.exists(), reason="planilha de referência ausente")
def test_importar_memoria_igual_ao_desktop(client):
    # Nov/2025 e Dez/2025 existem na planilha de referência; Jan/2030 não, e
    # deve voltar como erro sem impedir os outros meses (igual ao desktop).
    periodos = ["Nov/2025", "Dez/2025", "Jan/2030"]
    with MEMORIA.open("rb") as f:
        resp = client.post(
            "/api/pmpv/importar-memoria",
            files={"arquivo": (MEMORIA.name, f, "application/vnd.ms-excel")},
            data={"periodos": ",".join(periodos)},
        )
    assert resp.status_code == 200
    corpo = resp.json()
    assert set(corpo["meses"]) == {"Nov/2025", "Dez/2025"}
    assert len(corpo["erros"]) == 1 and corpo["erros"][0].startswith("Jan/2030")

    for periodo in periodos:
        try:
            esperado = ExcelPMPV.ler_dados_memoria_calculo(str(MEMORIA), periodo)
        except ValueError:
            assert any(e.startswith(periodo) for e in corpo["erros"])
            continue
        if not esperado:
            assert any(e.startswith(periodo) for e in corpo["erros"])
            continue
        obtido = {l["empresa"]: l for l in corpo["meses"][periodo]}
        assert set(obtido) == set(esperado)
        for nome, d in esperado.items():
            assert obtido[nome]["molecula"] == pytest.approx(d["mol"])
            assert obtido[nome]["transporte"] == pytest.approx(d["trans"])
            assert obtido[nome]["logistica"] == pytest.approx(d["log"])
            assert obtido[nome]["volume"] == pytest.approx(d["volume"])
