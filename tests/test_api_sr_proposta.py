"""POST /api/sr/trimestre/proposta: o SR do trimestre calculado sozinho (só lê, não grava).

Números do Quadro 6 da NT Mai–Jul/26 (Jan–Mar/26). Banco temporário via PLATAFORMA_DB;
a SELIC do Banco Central é sempre falsa: nenhum teste chama a internet.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.tarifa import servicos_selic

MESES = ["Jan/2026", "Fev/2026", "Mar/2026"]
VP = [48143000.0, 42224000.0, 46748000.0]
VF = [41805735.80, 39940612.96, 44979282.33]
SELIC = {"Jan/2026": 3.411174, "Fev/2026": 2.22116, "Mar/2026": 1.212054}


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "sr_proposta.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", lambda meses, hoje=None, buscar=None: {
        "disponivel": True, "valores": dict(SELIC), "fecha_em": "2026-03-31", "fonte": "Banco Central (série 11)"})
    return str(caminho)


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _popular(banco: str, vp: bool = True, prs: bool = True, vf: bool = True) -> None:
    with DatabasePMPV(db_path=banco) as db:
        for i, mes in enumerate(MESES):
            if vp:
                db.salvar_vp_periodo(mes, VP[i])
            if vf:
                db.salvar_cgf_resumo(mes, 0, 0, 0, 0, VF[i])
        if prs:
            db.salvar_pr("Nov - Jan/2026", 0, 0, 1, -0.0210)
            db.salvar_pr("Fev - Abr/2026", 0, 0, 1, -0.0321)


def _contar_sr(banco: str) -> int:
    with DatabasePMPV(db_path=banco) as db:
        return len(db.buscar_sr_trimestre("Jan/2026_Mar/2026"))


def _propor(client):
    r = client.post("/api/sr/trimestre/proposta", json={"labels_meses": MESES})
    assert r.status_code == 200, r.text
    return r.json()


def test_proposta_fecha_com_a_planilha_oficial(client, banco):
    _popular(banco)
    j = _propor(client)
    esperado = [-137622.23, -74924.76, -57463.99]
    for linha, sr in zip(j["linhas"], esperado):
        assert linha["sr_selic"] == pytest.approx(sr, abs=0.05)
    assert [l["pr"] for l in j["linhas"]] == [-0.0210, -0.0321, -0.0321]
    assert [l["pr_origem"] for l in j["linhas"]] == ["salvo"] * 3
    assert [l["pr_chave"] for l in j["linhas"]] == ["Nov - Jan/2026", "Fev - Abr/2026", "Fev - Abr/2026"]
    assert j["total"] == pytest.approx(-270010.98, abs=0.1)
    assert j["pode_gravar"] is True and j["bloqueios"] == []
    assert j["total_gravado"] is None and j["diferenca_total"] is None
    assert all(l["gravado"] is None for l in j["linhas"])
    assert all(a["codigo"] != "difere_gravado" for l in j["linhas"] for a in l["alertas"])
    assert j["selic"]["disponivel"] is True


def test_proposta_nao_grava_nada(client, banco):
    _popular(banco)
    _propor(client)
    assert _contar_sr(banco) == 0
    with DatabasePMPV(db_path=banco) as db:
        assert db.buscar_sr("Jan/2026") is None


def test_mes_sem_vp_bloqueia(client, banco):
    _popular(banco, vp=False)
    j = _propor(client)
    assert j["pode_gravar"] is False
    assert any("Sem VP de Jan/2026" in b for b in j["bloqueios"])
    assert "sem_vp" in [a["codigo"] for a in j["linhas"][0]["alertas"]]


def test_pr_ausente_bloqueia(client, banco):
    _popular(banco, prs=False)
    j = _propor(client)
    assert j["pode_gravar"] is False
    assert j["linhas"][0]["pr_origem"] == "ausente" and j["linhas"][0]["pr_chave"] == ""
    assert "Nov–Jan/2026" in j["linhas"][0]["alertas"][0]["mensagem"]
    assert "pr_ausente" in [a["codigo"] for a in j["linhas"][0]["alertas"]]


def test_vf_ausente_bloqueia(client, banco):
    # Sem VF o SR do mês sairia VP × PR inteiro: não se grava assim.
    _popular(banco, vf=False)
    j = _propor(client)
    assert j["pode_gravar"] is False
    assert "vf_ausente" in [a["codigo"] for a in j["linhas"][0]["alertas"]]
    assert any("Sem CGF gravado em Jan/2026" in b for b in j["bloqueios"])


def test_selic_indisponivel_zera_e_avisa(client, banco, monkeypatch):
    _popular(banco)

    def falha(meses, hoje=None, buscar=None):
        raise servicos_selic.SelicIndisponivel("O BC não respondeu.")
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", falha)
    j = _propor(client)
    assert j["selic"]["disponivel"] is False and j["selic"]["fecha_em"] == "2026-03-31"
    assert [l["selic_mensal"] for l in j["linhas"]] == [0, 0, 0]
    assert "selic_indisponivel" in [a["codigo"] for a in j["linhas"][0]["alertas"]]
    # Gravar com SELIC 0% repetiria o erro do SR de Jan–Mar/26: bloqueia (a frase aparece uma vez só).
    assert j["pode_gravar"] is False and j["bloqueios"] == ["O BC não respondeu."]


def test_gravado_com_selic_zero_e_diferencas(client, banco):
    _popular(banco)
    # Grava o trimestre como o analista teria feito, mas com SELIC 0.
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_sr_trimestre("Jan/2026_Mar/2026", [
            {"mes": m, "vp": VP[i], "vf": VF[i], "pr": [-0.0210, -0.0321, -0.0321][i], "selic_mensal": 0.0,
             "diferenca": VP[i] - VF[i], "sr_parcela": 0, "sr_selic": -100.0, "sr_anterior": 0.0, "total": -100.0}
            for i, m in enumerate(MESES)])
    j = _propor(client)
    codigos = [a["codigo"] for a in j["linhas"][0]["alertas"]]
    assert "selic_zero_gravada" in codigos and "difere_gravado" in codigos
    assert j["linhas"][0]["gravado"]["selic_mensal"] == 0.0
    assert j["total_gravado"] == pytest.approx(-300.0)
    assert j["diferenca_total"] == pytest.approx(j["total"] + 300.0)


def test_corpo_invalido_da_422(client):
    r = client.post("/api/sr/trimestre/proposta", json={"labels_meses": ["Jan/2026"]})
    assert r.status_code == 422


def test_pr_estimado_bloqueia(client, banco):
    # Sem PR salvo no módulo PR, mas com VP e SCG do mês, o carregamento só consegue ESTIMAR o PR
    # por (SCG + SR) ÷ VP. Essa estimativa não pode ser gravada (já deu SR errado em Fev/26).
    _popular(banco, prs=False)
    from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
    with ServicosConsolidacao() as cons:   # o SCG é a soma de RPV + RET + RP: grava o RET e ele recalcula
        cons.salvar_valores("Fev/2026", ret=3_318_892.52)
    j = _propor(client)
    fev = next(l for l in j["linhas"] if l["mes"] == "Fev/2026")
    assert fev["pr_origem"] == "estimado"
    assert "pr_estimado" in [a["codigo"] for a in fev["alertas"]]
    assert j["pode_gravar"] is False
    assert any("Fev/2026" in b and "estimativa" in b for b in j["bloqueios"])
