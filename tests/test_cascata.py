"""Cascata SR → PR → PV: a prévia não grava; só o /cascata/aplicar grava (SR → PR → PV).

Salvar a Auditoria, o CGF, o RET, o RP, o SCG, o SR, o PR ou o PMPV não regrava mais nada em silêncio:
devolve a prévia no campo `cascata`. Valores fictícios; banco temporário (nunca o banco real).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
from Src.Services.tarifa import servicos_pr_automatico as auto
from Src.Services.tarifa import servicos_selic
from Src.Services.tarifa.servicos_cascata import ServicosCascata

CIVIL = ["Jul/2026", "Ago/2026", "Set/2026"]
MESES_PR = ["Nov/2026", "Dez/2026", "Jan/2027"]
VP = [40_000_000.0, 41_000_000.0, 42_000_000.0]
VF = [38_000_000.0, 39_000_000.0, 40_000_000.0]
SELIC = {"Jul/2026": 3.0, "Ago/2026": 2.0, "Set/2026": 1.0}
SCG = [-1_000_000.0, 500_000.0, -200_000.0]
# O PR de cada mês do SR é o do trimestre da tarifa do PRÓPRIO mês.
PR_DOS_MESES = {"Mai - Jul/2026": -0.0200, "Ago - Out/2026": -0.0300}
# SR do mês = (VP − VF) × PR × (1 + SELIC%): −41.200, −61.200 e −60.600
SR_ESPERADO = (2e6 * -0.02 * 1.03) + (2e6 * -0.03 * 1.02) + (2e6 * -0.03 * 1.01)
# PR = (Σ SCG × (1 + SELIC%) + SR) ÷ VP de Nov, Dez e Jan (3 × 10.000.000) = −885.000 ÷ 30.000.000
PR_ESPERADO = -0.0295
PV_ESPERADO = 2.0 + PR_ESPERADO


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "cascata.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", lambda meses, hoje=None, buscar=None: {
        "disponivel": True, "valores": dict(SELIC), "fecha_em": "2026-09-30", "fonte": "Banco Central (série 11)"})
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _popular(banco: str, sem_vp_em: str | None = None, com_pmpv_novo: bool = True) -> None:
    with ServicosConsolidacao() as cons:
        for mes, scg in zip(CIVIL, SCG):
            cons.salvar_valores(mes, ret=scg)  # SCG = RPV + RET + RP: só o RET
    with DatabasePMPV(db_path=banco) as db:
        for mes, vp, vf in zip(CIVIL, VP, VF):
            if mes != sem_vp_em:
                db.salvar_vp_periodo(mes, vp)
            db.salvar_cgf_resumo(mes, 0, 0, 0, 0, vf)
        for chave, pr in PR_DOS_MESES.items():
            db.salvar_pr(chave, 0, 0, 1, pr)
        for mes in (MESES_PR if com_pmpv_novo else []):
            db.salvar_vp_periodo(mes, 10_000_000.0)
            db.salvar_pmpv_mensal(mes, 2.0)


def _estado(banco: str) -> dict:
    """Tudo o que a cascata poderia gravar: SR do trimestre, PR e PV."""
    with DatabasePMPV(db_path=banco) as db:
        return {"sr": db.buscar_sr_trimestre("Jul/2026_Set/2026"), "pr": db.buscar_pr("Nov - Jan/2027"),
                "pv": db.buscar_pv("Nov - Jan/2026")}


# ── prévia ───────────────────────────────────────────────────────────────────

def test_previa_calcula_a_cadeia_inteira_e_nao_grava(client, banco):
    _popular(banco)
    antes = _estado(banco)
    r = client.get("/api/cascata/previa", params={"periodos": ["Ago/2026"]})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["desatualizado"] is True and corpo["pendencias"] == []
    t = corpo["trimestres"][0]
    assert t["trimestre_sr"] == "Jul/2026_Set/2026" and t["periodo"] == "Ago/2026"
    assert t["sr_antes"] is None and t["sr_novo"] == pytest.approx(SR_ESPERADO)
    # o PR da prévia sai do SR NOVO (que ainda nem está gravado)
    assert t["chave_pr"] == "Nov - Jan/2027" and t["pr_antes"] is None and t["pr_novo"] == PR_ESPERADO
    assert t["chave_pv"] == "Nov - Jan/2026" and t["pv_novo"] == pytest.approx(PV_ESPERADO)
    assert t["meses_pr"] == MESES_PR
    assert _estado(banco) == antes  # a prévia não mexeu em nada


def test_previa_com_mais_de_um_mes_do_mesmo_trimestre_vale_uma_linha(client, banco):
    _popular(banco)
    r = client.get("/api/cascata/previa", params={"periodos": ["Set/2026", "Jul/2026", "Ago/2026"]})
    assert len(r.json()["trimestres"]) == 1


def test_previa_periodo_invalido_da_422(client):
    r = client.get("/api/cascata/previa", params={"periodos": ["Teste1"]})
    assert r.status_code == 422 and "não é válido" in r.json()["detail"]


def test_previa_com_pendencia_explica_o_que_falta(client, banco):
    _popular(banco, sem_vp_em="Set/2026")
    t = client.get("/api/cascata/previa", params={"periodos": ["Jul/2026"]}).json()["trimestres"][0]
    assert t["sr_novo"] is None
    assert any("Sem VP de Set/2026" in p for p in t["pendencias"])


@pytest.mark.parametrize("periodo, chave_pr, chave_pv", [
    ("Ago/2026", "Nov - Jan/2027", "Nov - Jan/2026"),   # virada de ano: o PR usa o ano do último mês, o PV o do 1º
    ("Dez/2026", "Fev - Abr/2027", "Fev - Abr/2027"),
    ("Abr/2026", "Ago - Out/2026", "Ago - Out/2026"),
])
def test_chaves_do_pr_e_do_pv_na_virada_de_ano(client, periodo, chave_pr, chave_pv):
    t = client.get("/api/cascata/previa", params={"periodos": [periodo]}).json()["trimestres"][0]
    assert (t["chave_pr"], t["chave_pv"]) == (chave_pr, chave_pv)


def test_previa_a_partir_do_pr_nao_recalcula_o_sr(client, banco):
    _popular(banco)
    t = client.get("/api/cascata/previa", params={"periodos": ["Jul/2026"], "a_partir_de": "pr"}).json()["trimestres"][0]
    assert t["sr_novo"] is None
    # sem SR salvo o PR não sai: o aviso é o de sempre da tela PR
    assert any("Salve o SR de Jul/2026 a Set/2026" in p for p in t["pendencias"])


# ── aplicar ──────────────────────────────────────────────────────────────────

def test_aplicar_grava_sr_pr_pv_e_depois_nao_ha_mais_pendencia(client, banco):
    _popular(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"]})
    assert r.status_code == 200, r.text
    t = r.json()["trimestres"][0]
    assert t["sr_novo"] == pytest.approx(SR_ESPERADO) and t["pr_novo"] == PR_ESPERADO
    assert t["pv_novo"] == pytest.approx(PV_ESPERADO) and r.json()["desatualizado"] is False

    estado = _estado(banco)
    assert sum(l["sr_selic"] for l in estado["sr"]) == pytest.approx(SR_ESPERADO)
    assert estado["pr"]["pr"] == PR_ESPERADO
    assert estado["pv"]["pv"] == pytest.approx(PV_ESPERADO)
    # outra prévia agora: tudo bate
    de_novo = client.get("/api/cascata/previa", params={"periodos": ["Ago/2026"]}).json()
    assert de_novo["desatualizado"] is False
    assert de_novo["trimestres"][0]["sr_antes"] == pytest.approx(SR_ESPERADO)


def test_aplicar_com_pendencia_da_422_e_nao_grava_nada(client, banco):
    _popular(banco, sem_vp_em="Set/2026")
    antes = _estado(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Jul/2026"]})
    assert r.status_code == 422
    assert "Sem VP de Set/2026" in r.json()["detail"] and "nada foi gravado" in r.json()["detail"]
    assert _estado(banco) == antes


def test_aplicar_ignora_numeros_da_tela(client, banco):
    """O pedido só tem os meses: não existe campo para mandar SR, PR ou PV."""
    _popular(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Jul/2026"], "pr_novo": 9.9999, "pv_novo": 9.9999})
    assert r.status_code == 200
    assert _estado(banco)["pr"]["pr"] == PR_ESPERADO


def test_aplicar_sem_periodos_da_422(client):
    assert client.post("/api/cascata/aplicar", json={"periodos": []}).status_code == 422


def test_aplicar_a_partir_do_pv_grava_so_o_pv(client, banco):
    _popular(banco)
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pr("Nov - Jan/2027", 0.0, 0.0, 0.0, -0.05)  # PR já salvo, PV ainda não
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Dez/2026"], "a_partir_de": "pv"})
    assert r.status_code == 200, r.text
    estado = _estado(banco)
    assert estado["pv"]["pv"] == pytest.approx(1.95) and estado["pr"]["pr"] == -0.05 and estado["sr"] == []


def test_sr_automatico_com_selic_zero_agora_recusa(banco, monkeypatch):
    """O furo: o SR automático usava `salvar_trimestre` e gravava com SELIC 0%. Agora usa o conferido."""
    _popular(banco)
    zerada = {**SELIC, "Ago/2026": 0.0}
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", lambda meses, hoje=None, buscar=None: {
        "disponivel": True, "valores": zerada, "fecha_em": "2026-09-30", "fonte": "Banco Central (série 11)"})
    r = auto.atualizar_sr_do_mes("Ago/2026")
    assert r["atualizado"] is False and r["sr"] is None
    assert any("Ago/2026: a SELIC está 0%" in p for p in r["pendencias"])
    assert _estado(banco)["sr"] == []


# ── as rotas de salvar só devolvem a prévia ──────────────────────────────────

def test_salvar_auditoria_nao_muda_o_pr_nem_o_pv(client, banco, monkeypatch):
    from Src.api.routers import auditoria
    _popular(banco)
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pr("Nov - Jan/2027", 0.0, 0.0, 0.0, -0.0069)  # PR velho
    antes = _estado(banco)
    monkeypatch.setattr(auditoria.lote, "salvar", lambda periodo, itens: {"cgr_liquido": 1.0, "rpv": 1.0, "qtd_itens": 0})
    resp = client.post("/api/auditoria/salvar", json={"periodo": "Ago/2026", "itens": []})
    assert resp.status_code == 200, resp.text
    assert _estado(banco) == antes  # PR, PV e SR exatamente como estavam
    assert antes["pr"]["pr"] == -0.0069
    cascata = resp.json()["cascata"]
    assert cascata["desatualizado"] is True
    assert cascata["trimestres"][0]["pr_antes"] == pytest.approx(-0.0069)
    assert cascata["trimestres"][0]["pr_novo"] == PR_ESPERADO


def test_salvar_scg_devolve_cascata_e_o_campo_legado_sem_gravar(client, banco):
    _popular(banco)
    antes = _estado(banco)
    resp = client.post("/api/scg/salvar", json={"periodo": "Jul/2026", "cgr": 1000.0, "cgf": 900.0, "ret": 10.0, "rp": -5.0})
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["pr_automatico"]["atualizado"] is False and corpo["pr_automatico"]["pr"] is None
    assert corpo["pr_automatico"]["sr_automatico"]["atualizado"] is False
    assert corpo["cascata"]["trimestres"][0]["chave_pr"] == "Nov - Jan/2027"
    assert _estado(banco) == antes


def test_salvar_o_sr_so_previa_o_pr(client, banco):
    _popular(banco)
    # o SR do trimestre já salvo (o /sr/trimestre/salvar grava só o SR; o PR e o PV ficam para a aprovação)
    linhas = [{"mes": m, "vp": vp, "vf": vf, "pr": pr, "selic_mensal": SELIC[m]}
              for m, vp, vf, pr in zip(CIVIL, VP, VF, (-0.02, -0.03, -0.03))]
    resp = client.post("/api/sr/trimestre/salvar", json={
        "labels_meses": CIVIL, "periodo_referencia": "Set/2026", "linhas": linhas})
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["total"] == pytest.approx(SR_ESPERADO)
    t = corpo["cascata"]["trimestres"][0]
    assert corpo["cascata"]["a_partir_de"] == "pr" and t["pr_novo"] == PR_ESPERADO
    assert corpo["pr_automatico"]["atualizado"] is False
    estado = _estado(banco)
    assert estado["pr"] is None and estado["pv"] is None  # o SR foi gravado; o PR e o PV não


def test_salvar_o_pr_so_previa_o_pv(client, banco):
    _popular(banco)
    client.post("/api/sr/trimestre/salvar", json={
        "labels_meses": CIVIL, "periodo_referencia": "Set/2026",
        "linhas": [{"mes": m, "vp": vp, "vf": vf, "pr": pr, "selic_mensal": SELIC[m]}
                   for m, vp, vf, pr in zip(CIVIL, VP, VF, (-0.02, -0.03, -0.03))]})
    resp = client.post("/api/pr/salvar", json={"periodo": "Nov - Jan/2027"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["pr"] == PR_ESPERADO
    assert resp.json()["cascata"]["a_partir_de"] == "pv"
    assert resp.json()["cascata"]["trimestres"][0]["pv_novo"] == pytest.approx(PV_ESPERADO)
    estado = _estado(banco)
    assert estado["pr"]["pr"] == PR_ESPERADO and estado["pv"] is None  # o PR é o que o analista pediu; o PV espera


# ── pendente ─────────────────────────────────────────────────────────────────

def test_pendente_lista_so_o_desatualizado(client, banco):
    _popular(banco)
    ServicosConsolidacao().criar_periodo("Teste1")  # período inválido: ignorado, não derruba
    antes = client.get("/api/cascata/pendente")
    assert antes.status_code == 200, antes.text
    assert antes.json()["desatualizado"] is True and len(antes.json()["trimestres"]) == 1
    assert antes.json()["periodos"] == [antes.json()["trimestres"][0]["periodo"]]

    client.post("/api/cascata/aplicar", json={"periodos": antes.json()["periodos"]})
    depois = client.get("/api/cascata/pendente").json()
    assert depois["desatualizado"] is False and depois["trimestres"] == []


def test_pendente_com_banco_vazio(client):
    r = client.get("/api/cascata/pendente")
    assert r.status_code == 200 and r.json()["trimestres"] == []


def test_servico_fecha_a_conexao_que_abriu(banco):
    with ServicosCascata() as servico:
        assert servico.previa(["Jul/2026"])["periodos"] == ["Jul/2026"]


# ── aprovação por etapa (`ate`) e trava 409 (`esperado`) ─────────────────────

def _salvar_sr(client) -> None:
    linhas = [{"mes": m, "vp": vp, "vf": vf, "pr": pr, "selic_mensal": SELIC[m]}
              for m, vp, vf, pr in zip(CIVIL, VP, VF, (-0.02, -0.03, -0.03))]
    r = client.post("/api/sr/trimestre/salvar", json={
        "labels_meses": CIVIL, "periodo_referencia": "Set/2026", "linhas": linhas})
    assert r.status_code == 200, r.text


def test_aprovar_so_o_sr_sem_o_pmpv_seguinte_grava_so_o_sr(client, banco):
    _popular(banco, com_pmpv_novo=False)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "ate": "sr"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["ate"] == "sr" and corpo["pendencias"] == []
    t = corpo["trimestres"][0]
    assert t["sr_novo"] == pytest.approx(SR_ESPERADO) and t["pr_novo"] is None and t["pv_novo"] is None
    estado = _estado(banco)
    assert sum(l["sr_selic"] for l in estado["sr"]) == pytest.approx(SR_ESPERADO)
    assert estado["pr"] is None and estado["pv"] is None


def test_sem_ate_e_sem_o_pmpv_seguinte_continua_recusando(client, banco):
    """Compatibilidade: o pedido antigo (sem `ate`) vai até o PV e exige o PMPV novo."""
    _popular(banco, com_pmpv_novo=False)
    antes = _estado(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"]})
    assert r.status_code == 422 and "PMPV" in r.json()["detail"]
    assert _estado(banco) == antes


def test_aprovar_o_pr_sem_sr_salvo_da_422_e_nao_grava(client, banco):
    _popular(banco)
    antes = _estado(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "a_partir_de": "pr", "ate": "pr"})
    assert r.status_code == 422 and "Salve o SR de Jul/2026 a Set/2026" in r.json()["detail"]
    assert _estado(banco) == antes


def test_aprovar_o_pr_sem_o_pmpv_novo_da_422(client, banco):
    _popular(banco, com_pmpv_novo=False)
    _salvar_sr(client)
    antes = _estado(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "a_partir_de": "pr", "ate": "pr"})
    assert r.status_code == 422 and "Sem VP para Nov/2026" in r.json()["detail"]
    assert _estado(banco) == antes


def test_aprovar_o_pr_grava_so_o_pr_e_depois_o_pv_separado(client, banco):
    _popular(banco)
    _salvar_sr(client)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "a_partir_de": "pr", "ate": "pr"})
    assert r.status_code == 200, r.text
    t = r.json()["trimestres"][0]
    assert t["pr_novo"] == PR_ESPERADO and t["pv_novo"] is None
    estado = _estado(banco)
    assert estado["pr"]["pr"] == PR_ESPERADO and estado["pv"] is None
    # segunda aprovação, separada: o PV
    r2 = client.post("/api/cascata/aplicar", json={"periodos": ["Dez/2026"], "a_partir_de": "pv", "ate": "pv"})
    assert r2.status_code == 200, r2.text
    assert _estado(banco)["pv"]["pv"] == pytest.approx(PV_ESPERADO)


def test_aprovar_o_pv_sem_o_pr_da_422(client, banco):
    _popular(banco)
    antes = _estado(banco)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Dez/2026"], "a_partir_de": "pv", "ate": "pv"})
    assert r.status_code == 422 and "falta o PR salvo" in r.json()["detail"]
    assert _estado(banco) == antes


@pytest.mark.parametrize("corpo", [
    {"a_partir_de": "pr", "ate": "sr"},   # ate antes de a_partir_de
    {"ate": "xx"},                         # etapa que não existe
])
def test_ate_invalido_da_422(client, corpo):
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], **corpo})
    assert r.status_code == 422


def test_previa_com_ate_sr_nao_calcula_pr_nem_pv(client, banco):
    _popular(banco, com_pmpv_novo=False)
    r = client.get("/api/cascata/previa", params={"periodos": ["Ago/2026"], "ate": "sr"})
    assert r.status_code == 200, r.text
    t = r.json()["trimestres"][0]
    assert r.json()["ate"] == "sr" and t["sr_novo"] == pytest.approx(SR_ESPERADO)
    assert t["pr_novo"] is None and t["pendencias"] == []


def test_esperado_igual_ao_calculo_grava(client, banco):
    _popular(banco)
    previa = client.get("/api/cascata/previa", params={"periodos": ["Ago/2026"]}).json()
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "esperado": previa["trimestres"]})
    assert r.status_code == 200, r.text
    assert _estado(banco)["pr"]["pr"] == PR_ESPERADO


def test_dado_alterado_entre_a_previa_e_o_aplicar_da_409_e_nao_grava(client, banco):
    _popular(banco)
    previa = client.get("/api/cascata/previa", params={"periodos": ["Ago/2026"]}).json()
    antes = _estado(banco)
    with DatabasePMPV(db_path=banco) as db:  # alguém muda o VP de Ago depois da prévia
        db.salvar_vp_periodo("Ago/2026", 45_000_000.0)
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "esperado": previa["trimestres"]})
    assert r.status_code == 409, r.text
    assert "mudaram desde a prévia" in r.json()["detail"] and "SR de Ago/2026" in r.json()["detail"]
    assert _estado(banco) == antes


def test_409_vale_so_para_as_etapas_pedidas(client, banco):
    """Aprovando só o SR, uma diferença no PR visto não trava (o PR nem entra na aprovação)."""
    _popular(banco)
    previa = client.get("/api/cascata/previa", params={"periodos": ["Ago/2026"]}).json()
    visto = [{**previa["trimestres"][0], "pr_novo": 0.5}]
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Ago/2026"], "ate": "sr", "esperado": visto})
    assert r.status_code == 200, r.text
