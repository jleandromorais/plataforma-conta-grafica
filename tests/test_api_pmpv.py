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
from Src.Services.tarifa.servicos_pmpv import ExcelPMPV, RegrasPMPV

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


def test_prova_real_refaz_o_pmpv_da_sessao(client):
    resultado = client.post("/api/pmpv/calcular", json=_payload_calculo()).json()
    sid = client.post("/api/pmpv/salvar", json={
        "nome": "PMPV_Fev_Abr_2026", "dados_por_mes": DADOS, "resultado": resultado, "periodos": PERIODOS,
    }).json()["sessao_id"]
    p = client.get("/api/pmpv/prova-real", params={"sessao_id": sid}).json()
    assert p["tem_linhas"] and p["tem_resultado"] and p["confere"] is True
    assert p["pmpv_calculado"] == pytest.approx(resultado["pmpv"])
    assert p["preco_final_calculado"] == pytest.approx(resultado["preco_final"])
    assert p["custo_total_calculado"] == pytest.approx(resultado["custo_total"])
    assert p["volume_total"] == pytest.approx(resultado["vp_mensal"])
    # A conta fecha mês a mês: Σ custo dos meses = custo total; PMPV do mês = custo ÷ volume.
    assert sum(m["custo"] for m in p["meses"]) == pytest.approx(p["custo_total_calculado"])
    assert [len(m["empresas"]) for m in p["meses"]] == [2, 1, 2]
    for m in p["meses"]:
        assert m["pmpv_do_mes"] == pytest.approx(m["custo"] / m["volume"])


def test_prova_real_detecta_resultado_gravado_diferente(client):
    resultado = client.post("/api/pmpv/calcular", json=_payload_calculo()).json()
    adulterado = {**resultado, "pmpv": resultado["pmpv"] + 0.5, "preco_final": resultado["preco_final"] + 0.5}
    sid = client.post("/api/pmpv/salvar", json={"nome": "X", "dados_por_mes": DADOS, "resultado": adulterado}).json()["sessao_id"]
    p = client.get("/api/pmpv/prova-real", params={"sessao_id": sid}).json()
    assert p["confere"] is False and p["diferenca_pmpv"] == pytest.approx(-0.5)


def test_prova_real_sessao_inexistente_404(client):
    assert client.get("/api/pmpv/prova-real", params={"sessao_id": 999}).status_code == 404


def _salvar(client, nome, dados=DADOS, periodos=PERIODOS):
    resultado = client.post("/api/pmpv/calcular", json=_payload_calculo()).json()
    return client.post("/api/pmpv/salvar", json={
        "nome": nome, "dados_por_mes": dados, "resultado": resultado, "periodos": periodos,
    }).json()["sessao_id"]


def _sessao_do_trimestre(client, periodos):
    return client.get("/api/pmpv/sessao-do-trimestre", params={"periodos": ",".join(periodos)})


def test_sessao_do_trimestre_devolve_as_empresas_salvas_de_cada_mes(client):
    # Nome com 3 sublinhados, como a tela web grava ("Fev - Abr" → "Fev___Abr").
    sid = _salvar(client, "PMPV_Fev___Abr_2026")
    r = _sessao_do_trimestre(client, PERIODOS)
    assert r.status_code == 200
    s = r.json()
    assert (s["encontrada"], s["sessao_id"], s["nome"]) == (True, sid, "PMPV_Fev___Abr_2026")
    assert s["data_criacao"] and s["conta_grafica"] == pytest.approx(-0.021)
    assert list(s["meses"]) == PERIODOS
    fev = {l["empresa"]: l for l in s["meses"]["Fev/2026"]}
    assert set(fev) == {"PETROBRAS", "GALP"}
    assert (fev["PETROBRAS"]["molecula"], fev["PETROBRAS"]["volume"]) == (2.1, 1_200_000)   # volume = QDC digitado
    assert [l["empresa"] for l in s["meses"]["Abr/2026"]] == ["PETROBRAS", "BRAVA"]


def test_sessao_do_trimestre_usa_a_mais_recente_e_nao_mistura_trimestres(client):
    _salvar(client, "PMPV_Fev_Abr_2026")
    nova = {**DADOS, "Mês 1": [_linha("ENEVA", 1.5, 0.1, 0.0, 10)]}
    sid_novo = _salvar(client, "PMPV_Fev_Abr_2026", dados=nova)
    _salvar(client, "PMPV_Mai___Jul_2026", periodos=["Mai/2026", "Jun/2026", "Jul/2026"])

    s = _sessao_do_trimestre(client, PERIODOS).json()
    assert s["sessao_id"] == sid_novo
    assert [l["empresa"] for l in s["meses"]["Fev/2026"]] == ["ENEVA"]
    # Outro ano do mesmo trimestre: nada salvo.
    assert _sessao_do_trimestre(client, ["Fev/2027", "Mar/2027", "Abr/2027"]).json() == {
        "encontrada": False, "sessao_id": None, "nome": None, "data_criacao": None,
        "pmpv": None, "conta_grafica": None, "preco_final": None, "meses": {},
    }


def test_sessao_do_trimestre_nov_jan_vira_o_ano(client):
    sid = _salvar(client, "PMPV_Nov___Jan_2025", periodos=["Nov/2025", "Dez/2025", "Jan/2026"])
    s = _sessao_do_trimestre(client, ["Nov/2025", "Dez/2025", "Jan/2026"]).json()
    assert (s["encontrada"], s["sessao_id"]) == (True, sid)
    assert list(s["meses"]) == ["Nov/2025", "Dez/2025", "Jan/2026"]


def test_sessao_do_trimestre_ignora_nome_de_sessao_antiga_e_pede_3_meses(client):
    _salvar(client, "PMPV_13042026_0906")   # formato antigo do desktop: não diz o trimestre
    assert _sessao_do_trimestre(client, PERIODOS).json()["encontrada"] is False
    assert _sessao_do_trimestre(client, ["Fev/2026"]).status_code == 422


def test_margem_regulatoria_conhecida_salva_e_ausente(client):
    # 2026 o sistema conhece (R$ 0,5410); 2027 ninguém informou; o analista pode informar.
    assert client.get("/api/pmpv/margem-regulatoria", params={"ano": 2026}).json() == {"ano": 2026, "margem": 0.541, "origem": "padrao"}
    assert client.get("/api/pmpv/margem-regulatoria", params={"ano": 2027}).json() == {"ano": 2027, "margem": None, "origem": "ausente"}
    salvo = client.post("/api/pmpv/margem-regulatoria", json={"ano": 2027, "margem": 0.6}).json()
    assert salvo == {"ano": 2027, "margem": 0.6, "origem": "salva"}
    assert client.get("/api/pmpv/margem-regulatoria", params={"ano": 2027}).json()["origem"] == "salva"
    # O que o analista salva vale mais que o padrão do sistema.
    assert client.post("/api/pmpv/margem-regulatoria", json={"ano": 2026, "margem": 0.55}).json()["margem"] == 0.55


def test_margem_regulatoria_rejeita_valor_ruim(client):
    assert client.post("/api/pmpv/margem-regulatoria", json={"ano": 2026, "margem": -1}).status_code == 422
    assert client.post("/api/pmpv/margem-regulatoria", json={"ano": 1999, "margem": 0.5}).status_code == 422
    assert client.get("/api/pmpv/margem-regulatoria", params={"ano": 3000}).status_code == 422


def test_calcular_com_margem_traz_a_tarifa_media(client):
    payload = _payload_calculo()
    sem = client.post("/api/pmpv/calcular", json=payload).json()
    assert "tarifa_media" not in sem  # sem margem, a resposta é a de antes
    com = client.post("/api/pmpv/calcular", json={**payload, "margem_regulatoria": 0.541}).json()
    # Tarifa Média = PV + margem, com PV = PMPV + PR (= preco_final).
    assert com["tarifa_media"] == pytest.approx(com["pmpv"] + (-0.021) + 0.541)
    assert com["tarifa_media"] == pytest.approx(com["preco_final"] + 0.541)
    assert com["preco_final"] == pytest.approx(sem["preco_final"])
