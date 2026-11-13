"""GET /api/scg/prova-real: a conta do SCG gravado (RPV + RET + RP) refeita e a origem de cada número.
Só lê, não grava. Banco temporário via PLATAFORMA_DB; valores fictícios.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV


@pytest.fixture()
def client(tmp_path, monkeypatch):
    caminho = tmp_path / "scg_prova.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _salvar(client, periodo: str, cgr: float, cgf: float, ret: float, rp: float) -> None:
    r = client.post("/api/scg/salvar", json={"periodo": periodo, "cgr": cgr, "cgf": cgf, "ret": ret, "rp": rp})
    assert r.status_code == 200, r.text


def _prova(client, periodo: str):
    return client.get("/api/scg/prova-real", params={"periodo": periodo})


def test_confere_e_refaz_rpv_e_scg(client):
    _salvar(client, "Fev/2026", 1000.0, 400.0, 30.0, -20.0)
    r = _prova(client, "Fev/2026")
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["gravado"] is True
    assert (p["cgr"], p["cgf"], p["ret"], p["rp"]) == (1000.0, 400.0, 30.0, -20.0)
    assert p["rpv"] == pytest.approx(600.0)
    assert p["rpv_calculado"] == pytest.approx(600.0)  # CGR − CGF
    assert p["scg_calculado"] == pytest.approx(610.0)  # RPV + RET + RP
    assert p["scg_gravado"] == pytest.approx(610.0)
    assert p["diferenca"] == pytest.approx(0.0)
    assert p["confere"] is True
    assert set(p["origens"]) == {"cgr", "cgf", "ret", "rp"}


def test_mes_sem_consolidacao(client):
    p = _prova(client, "Dez/2026").json()
    assert p["gravado"] is False and p["confere"] is False
    assert p["scg_gravado"] is None and p["diferenca"] is None
    assert p["scg_calculado"] == 0.0


def test_periodo_invalido_422(client):
    assert _prova(client, "Teste").status_code == 422


def test_scg_alterado_por_fora_nao_confere(client):
    _salvar(client, "Fev/2026", 1000.0, 400.0, 30.0, -20.0)
    with DatabasePMPV() as db:  # alguém mexeu direto no banco
        db.cursor.execute("UPDATE consolidacao SET scg = 999.0 WHERE periodo = 'Fev/2026'")
        db.conn.commit()
    p = _prova(client, "Fev/2026").json()
    assert p["scg_gravado"] == pytest.approx(999.0)
    assert p["scg_calculado"] == pytest.approx(610.0)
    assert p["diferenca"] == pytest.approx(-389.0)
    assert p["confere"] is False


def _gravar_cru(periodo: str, cgr: float, cgf: float, ret: float, rp: float, scg: float) -> None:
    """Mês como ficou em produção: 4 campos preenchidos e a coluna `scg` crua velha."""
    with DatabasePMPV() as db:
        db.criar_periodo_consolidacao(periodo)
        db.atualizar_campos_consolidacao(periodo, cgr=cgr, cgf=cgf, ret=ret, rp=rp, scg=scg)


def test_mes_com_campos_iguais_e_scg_cru_zero_nao_confere(client):
    _gravar_cru("Ago/2026", 1000.0, 400.0, 30.0, -20.0, 0.0)
    p = _prova(client, "Ago/2026").json()
    assert p["scg_gravado"] == 0.0 and p["scg_calculado"] == pytest.approx(610.0)
    assert p["diferenca"] == pytest.approx(610.0) and p["confere"] is False   # "a salvar"


def test_reparar_historico_simula_e_depois_conserta(client):
    _gravar_cru("Ago/2026", 1000.0, 400.0, 30.0, -20.0, 0.0)
    _gravar_cru("Set/2026", 800.0, 300.0, 10.0, 0.0, 0.0)   # falta o RP: não pode ser gravado

    simulacao = client.post("/api/scg/reparar-historico").json()   # padrão: só simula
    assert simulacao["aplicado"] is False
    assert [m["periodo"] for m in simulacao["meses"]] == ["Ago/2026"]
    assert simulacao["ignorados"] == [{"periodo": "Set/2026", "motivo": "falta RP"}]
    assert _prova(client, "Ago/2026").json()["confere"] is False   # nada foi gravado

    feito = client.post("/api/scg/reparar-historico", params={"aplicar": True}).json()
    assert feito["aplicado"] is True
    assert _prova(client, "Ago/2026").json()["confere"] is True
    assert _prova(client, "Set/2026").json()["scg_gravado"] == 0.0   # incompleto continua intocado


def test_salvar_pelos_modulos_deixa_a_prova_real_conferindo(client):
    # Salvar cada módulo (pelo serviço, como o CGF/RET/RP fazem) passa a gravar o scg cru.
    from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
    with ServicosConsolidacao() as c:
        c.salvar_cgr("Ago/2026", 1000.0)
        c.salvar_cgf("Ago/2026", 400.0)
        c.salvar_ret("Ago/2026", 30.0)
        c.salvar_rp("Ago/2026", -20.0)
    p = _prova(client, "Ago/2026").json()
    assert p["scg_gravado"] == pytest.approx(610.0) and p["confere"] is True


def test_origens_refletem_os_modulos(client):
    _salvar(client, "Mar/2026", 1000.0, 0.0, 0.0, 0.0)
    _salvar(client, "Abr/2026", 1000.0, 0.0, 0.0, 0.0)
    with DatabasePMPV() as db:
        db.salvar_auditoria_itens("Mar/2026", [{"empresa": "PETROBRAS", "tipo": "NF-e", "numero": "1", "cgr_liquido": 1000.0}])
        db.salvar_concilia_itens("Mar/2026", [{"arquivo": "d.pdf", "categoria": "Despesa", "valor": 10.0}])
        db.salvar_ret_itens("Mar/2026", [{"arquivo": "a.pdf", "tipo_encargo": "EAT", "empresa": "X", "valor_total": 100.0}])
    com = _prova(client, "Mar/2026").json()["origens"]
    assert com["cgr"]["tem_itens"] is True and com["cgr"]["valor_das_notas"] == pytest.approx(1000.0)
    assert com["cgr"]["confere"] is True
    assert com["ret"]["tem_itens"] is True and com["ret"]["valor_calculado"] is not None
    assert com["rp"]["tem_itens"] is True and com["rp"]["valor_calculado"] is not None
    assert com["cgf"]["tem_resumo"] is False and com["cgf"]["valor_calculado"] is None
    sem = _prova(client, "Abr/2026").json()["origens"]  # mês gravado só com os totais
    assert sem["cgr"] == {"tem_itens": False, "valor_das_notas": None, "confere": False}
    assert sem["ret"] == {"tem_itens": False, "valor_calculado": None, "confere": False}
    assert sem["rp"] == {"tem_itens": False, "valor_calculado": None, "confere": False}
