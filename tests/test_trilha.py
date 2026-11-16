"""Trilha de alterações: cada salvar anota o que MUDOU (valor antigo e novo); valor igual não anota.
Valores fictícios; banco temporário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "trilha.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _trilha(banco: str, **filtros) -> list[dict]:
    with DatabasePMPV(db_path=banco) as db:
        return db.listar_alteracoes(**filtros)


def _mudancas(banco: str, tabela: str) -> list[tuple]:
    """(campo, antigo, novo), da mais antiga para a mais nova."""
    linhas = _trilha(banco, tabela=tabela)
    return [(l["campo"], l["valor_antigo"], l["valor_novo"]) for l in reversed(linhas)]


def test_pr_so_anota_quando_o_valor_muda(banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pr("Fev - Abr/2026", 100.0, -10.0, 1000.0, 0.09)
        db.salvar_pr("Fev - Abr/2026", 100.0, -10.0, 1000.0, 0.09)    # igual: nada a anotar
        db.salvar_pr("Fev - Abr/2026", 100.0, -10.0, 1000.0, 0.0876)  # só o PR mudou
    assert [m for m in _mudancas(banco, "pr_resultados") if m[1] is not None] == [("pr", 0.09, 0.0876)]
    # a 1ª gravação anotou os 4 campos (de "sem valor" para o valor) e a 3ª só o PR
    assert len(_mudancas(banco, "pr_resultados")) == 4 + 1


def test_primeira_gravacao_anota_antigo_vazio(banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pmpv_mensal("Fev/2026", 2.0)
    assert _mudancas(banco, "pmpv_mensal") == [("pmpv", None, 2.0)]


def test_pmpv_igual_nao_anota_de_novo(banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pmpv_mensal("Fev/2026", 2.0)
        db.salvar_pmpv_mensal("Fev/2026", 2.0)
        db.salvar_pmpv_mensal("Fev/2026", 2.1)
    assert _mudancas(banco, "pmpv_mensal") == [("pmpv", None, 2.0), ("pmpv", 2.0, 2.1)]


def test_sr_e_pv(banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_sr("Jul/2026", 40.0, 38.0, -0.02, -100.0)
        db.salvar_sr("Jul/2026", 40.0, 38.0, -0.02, -150.0)
        db.salvar_pv("Fev/2026", 2.0, 0.1, 2.1)
        db.salvar_pv("Fev/2026", 2.0, 0.1, 2.1)
    assert ("sr", -100.0, -150.0) in _mudancas(banco, "sr_resultados")
    assert len(_mudancas(banco, "sr_resultados")) == 4 + 1
    assert len(_mudancas(banco, "pv_resultados")) == 3


def test_pv_em_lote_anota_so_a_chave_do_trimestre(banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pv_lote(["Fev - Abr/2026", "Fev/2026", "Mar/2026", "Abr/2026"], 2.0, 0.1, 2.1)
    linhas = _trilha(banco, tabela="pv_resultados")
    assert {l["periodo"] for l in linhas} == {"Fev - Abr/2026"} and len(linhas) == 3


def test_consolidacao_anota_cada_campo_alterado(banco):
    with ServicosConsolidacao() as cons:
        cons.salvar_valores("Jul/2026", ret=100.0)
        cons.salvar_valores("Jul/2026", ret=100.0)   # igual: sem nova anotação do ret
        cons.salvar_valores("Jul/2026", ret=250.0)
    ret = [m for m in _mudancas(banco, "consolidacao") if m[0] == "ret"]
    assert ret == [("ret", 0.0, 100.0), ("ret", 100.0, 250.0)]
    scg = [m for m in _mudancas(banco, "consolidacao") if m[0] == "scg"]
    assert scg[-1] == ("scg", 100.0, 250.0)


# ── GET /trilha ──────────────────────────────────────────────────────────────

def test_rota_trilha_filtra_por_periodo_e_tabela(client, banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pr("Fev - Abr/2026", 1.0, 2.0, 3.0, 0.5)
        db.salvar_pmpv_mensal("Fev/2026", 2.0)
    todas = client.get("/api/trilha").json()
    assert {l["tabela"] for l in todas} == {"pr_resultados", "pmpv_mensal"}
    so_pr = client.get("/api/trilha", params={"periodo": "Fev - Abr/2026", "tabela": "pr_resultados"}).json()
    assert {l["campo"] for l in so_pr} == {"scg", "sr", "vp", "pr"}
    assert all(l["origem"] == "salvar" and l["valor_antigo"] is None for l in so_pr)
    assert set(so_pr[0]) == {"id", "tabela", "periodo", "campo", "valor_antigo", "valor_novo", "origem", "data_hora"}
    assert client.get("/api/trilha", params={"periodo": "Mai - Jul/2026"}).json() == []


def test_rota_trilha_recusa_tabela_e_periodo_invalidos(client):
    assert client.get("/api/trilha", params={"tabela": "usuarios"}).status_code == 422
    assert client.get("/api/trilha", params={"periodo": "Teste1"}).status_code == 422


def test_origem_cascata_na_aprovacao(client, banco, monkeypatch):
    from Src.Services.tarifa import servicos_selic
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", lambda meses, hoje=None, buscar=None: {
        "disponivel": True, "valores": {"Jul/2026": 3.0, "Ago/2026": 2.0, "Set/2026": 1.0},
        "fecha_em": "2026-09-30", "fonte": "Banco Central (série 11)"})
    with ServicosConsolidacao() as cons:
        for mes, scg in zip(("Jul/2026", "Ago/2026", "Set/2026"), (-1e6, 5e5, -2e5)):
            cons.salvar_valores(mes, ret=scg)
    with DatabasePMPV(db_path=banco) as db:
        for mes, vp, vf in zip(("Jul/2026", "Ago/2026", "Set/2026"), (40e6, 41e6, 42e6), (38e6, 39e6, 40e6)):
            db.salvar_vp_periodo(mes, vp)
            db.salvar_cgf_resumo(mes, 0, 0, 0, 0, vf)
        db.salvar_pr("Mai - Jul/2026", 0, 0, 1, -0.02)
        db.salvar_pr("Ago - Out/2026", 0, 0, 1, -0.03)
        for mes in ("Nov/2026", "Dez/2026", "Jan/2027"):
            db.salvar_vp_periodo(mes, 10e6)
            db.salvar_pmpv_mensal(mes, 2.0)
    assert client.post("/api/cascata/aplicar", json={"periodos": ["Jul/2026"]}).status_code == 200
    por_tabela = {l["tabela"]: l for l in client.get("/api/trilha", params={"periodo": "Nov - Jan/2027"}).json()}
    assert por_tabela["pr_resultados"]["origem"] == "cascata" and por_tabela["pr_resultados"]["valor_novo"] is not None
    sr = client.get("/api/trilha", params={"tabela": "sr_resultados"}).json()
    assert sr and all(l["origem"] == "cascata" for l in sr)
    # depois da aprovação, o salvar comum volta a ser "salvar"
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pmpv_mensal("Fev/2026", 2.0)
    assert client.get("/api/trilha", params={"tabela": "pmpv_mensal", "periodo": "Fev/2026"}).json()[0]["origem"] == "salvar"
