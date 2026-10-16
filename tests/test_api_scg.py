"""Testes da API web do SCG (Src/api/routers/scg.py).

O SCG de um mês pode divergir entre (a) os valores recalculados dos itens dos
módulos — o que a tela desktop mostra no modo Automático — e (b) os gravados
na consolidação — o que o Excel Final usa. A API expõe os dois lados para a
tela web mostrar lado a lado. Banco temporário via PLATAFORMA_DB.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.servicos_scg import ServicosSCG


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "scg_teste.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _itens(periodo: str, cgr_nfe: float, cgr_cte_frete: float, rp: float):
    with DatabasePMPV() as db:
        db.salvar_auditoria_itens(periodo, [
            {"empresa": "PETROBRAS", "tipo": "NF-e", "numero": "1", "cgr_liquido": cgr_nfe},
            # CT-e de transportadora comum é frete: NÃO entra no CGR
            {"empresa": "Transportadora X", "tipo": "CT-e", "numero": "2", "cgr_liquido": cgr_cte_frete},
        ])
        # RP = despesas − receitas: despesa de rp+10 e receita de 10
        db.salvar_concilia_itens(periodo, [
            {"arquivo": "d.pdf", "categoria": "Despesa", "valor": rp + 10.0},
            {"arquivo": "r.pdf", "categoria": "Receita", "valor": 10.0},
        ])


def test_comparar_periodo_novo_mostra_modulos_e_gravado_vazio(client):
    _itens("Abr/2026", cgr_nfe=1000.0, cgr_cte_frete=999.0, rp=50.0)
    resp = client.get("/api/scg/comparar", params={"periodo": "Abr/2026"})
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["modulos"]["cgr"] == pytest.approx(1000.0)  # frete ficou de fora
    assert corpo["modulos"]["rp"] == pytest.approx(50.0)
    assert corpo["modulos"]["scg"] == pytest.approx(1050.0)  # RPV(1000-0) + RET 0 + RP 50
    assert corpo["modulos"] == pytest.approx(ServicosSCG.buscar_dados_fontes("Abr/2026"))


def test_comparar_mostra_divergencia_com_o_gravado(client):
    _itens("Mar/2026", cgr_nfe=1000.0, cgr_cte_frete=0.0, rp=50.0)
    client.post("/api/scg/salvar", json={"periodo": "Mar/2026", "cgr": 800.0, "cgf": 100.0, "ret": 10.0, "rp": -5.0})
    corpo = client.get("/api/scg/comparar", params={"periodo": "Mar/2026"}).json()
    assert corpo["gravado"]["cgr"] == pytest.approx(800.0)
    assert corpo["modulos"]["cgr"] == pytest.approx(1000.0)
    # CGF e RET vêm da consolidação nos dois lados
    assert corpo["modulos"]["cgf"] == pytest.approx(100.0)
    assert corpo["modulos"]["ret"] == pytest.approx(10.0)


def test_salvar_grava_e_recalcula_rpv_e_scg(client):
    resp = client.post("/api/scg/salvar", json={"periodo": "Fev/2026", "cgr": 1000.0, "cgf": 400.0, "ret": 30.0, "rp": -20.0})
    assert resp.status_code == 200
    d = resp.json()
    assert d["rpv"] == pytest.approx(600.0)
    assert d["scg"] == pytest.approx(610.0)
    assert client.get("/api/scg", params={"periodo": "Fev/2026"}).json()["scg"] == pytest.approx(610.0)


def test_salvar_igual_ao_desktop(client):
    """Mesmo resultado do 'Salvar manual' + 'Calcular SCG' da tela desktop."""
    client.post("/api/scg/salvar", json={"periodo": "Jan/2026", "cgr": 123.45, "cgf": 23.45, "ret": 7.0, "rp": 3.0})
    servico = ServicosSCG()
    try:
        servico.salvar_valores_manuais("Dez/2025", 123.45, 23.45, 7.0, 3.0)
        desktop = servico.calcular_scg_oficial("Dez/2025")
    finally:
        servico.consolidacao.fechar()
    web = client.get("/api/scg", params={"periodo": "Jan/2026"}).json()
    for k in ("cgr", "cgf", "rpv", "ret", "rp", "scg"):
        assert web[k] == pytest.approx(desktop[k])


def test_historico_marca_periodos_divergentes(client):
    _itens("Mai/2026", cgr_nfe=500.0, cgr_cte_frete=0.0, rp=0.0)
    client.post("/api/scg/salvar", json={"periodo": "Mai/2026", "cgr": 500.0, "cgf": 0.0, "ret": 0.0, "rp": 0.0})
    client.post("/api/scg/salvar", json={"periodo": "Jun/2026", "cgr": 900.0, "cgf": 0.0, "ret": 0.0, "rp": 0.0})
    hist = {h["periodo"]: h for h in client.get("/api/scg/historico").json()}
    assert hist["Mai/2026"]["diverge"] is False   # gravado = itens
    assert hist["Jun/2026"]["diverge"] is True    # gravado 900, sem itens (0)
    assert hist["Jun/2026"]["scg"] == pytest.approx(900.0)


def test_texto_historico_desktop_mostra_scg_real(banco):
    """Antes o histórico do desktop mostrava R$ 0,00 em todos os meses."""
    servico = ServicosSCG()
    try:
        servico.salvar_e_calcular("Jul/2026", 1000.0, 0.0, 0.0, 0.0)
        texto = servico.gerar_texto_historico()
    finally:
        servico.consolidacao.fechar()
    assert "1.000,00" in texto
