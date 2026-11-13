"""O PR é gravado com a conta do SERVIDOR, nunca com números da tela.

POST /api/pr/salvar refaz a apuração (SCG com SELIC + SR do trimestre civil ÷ VP) e o PR automático
(ao salvar SCG, SR e módulos) não grava com o SR faltando. Valores fictícios; banco temporário.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.tarifa import servicos_pr_automatico as auto
from Src.Services.tarifa.servicos_pr import meses_da_chave_pr

# PR Fev–Abr/2026 usa o trimestre civil Out–Dez/2025.
CIVIL = ["Out/2025", "Nov/2025", "Dez/2025"]
SCG = [-1_000_000.0, 500_000.0, -200_000.0]
SELIC = [3.0, 2.0, 1.0]
SR = [-10_000.0, -5_000.0, -2_000.0]
MESES_PR = ["Fev/2026", "Mar/2026", "Abr/2026"]
# (−1.030.000 + 510.000 − 202.000 − 17.000) ÷ 30.000.000 = −0,024633 → −0,0246
PR_ESPERADO = -0.0246


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "pr_servidor.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    return str(caminho)


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _popular(banco: str, sr: bool = True, meses_sr: list[str] | None = None) -> None:
    from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
    with ServicosConsolidacao() as cons:  # SCG = RPV + RET + RP: grava só o RET
        for mes, scg in zip(CIVIL, SCG):
            cons.salvar_valores(mes, ret=scg)
    with DatabasePMPV(db_path=banco) as db:
        for mes in MESES_PR:
            db.salvar_vp_periodo(mes, 10_000_000.0)
            db.salvar_pmpv_mensal(mes, 2.0)
        if sr:
            linhas = [{"mes": m, "selic_mensal": s, "sr_selic": v}
                      for m, s, v in zip(CIVIL, SELIC, SR) if m in (meses_sr or CIVIL)]
            db.salvar_sr_trimestre("Out/2025_Dez/2025", linhas)


def _pr_gravado(banco: str, chave: str):
    with DatabasePMPV(db_path=banco) as db:
        return db.buscar_pr(chave)


# ── chave do PR → meses (a chave usa o ano do ÚLTIMO mês) ─────────────────────

@pytest.mark.parametrize("chave, meses", [
    ("Fev - Abr/2026", ["Fev/2026", "Mar/2026", "Abr/2026"]),
    ("Nov - Jan/2026", ["Nov/2025", "Dez/2025", "Jan/2026"]),  # virada de ano
    ("Ago - Out/2026", ["Ago/2026", "Set/2026", "Out/2026"]),
])
def test_meses_da_chave_pr(chave, meses):
    assert meses_da_chave_pr(chave) == meses


@pytest.mark.parametrize("ruim", ["Jan/2026", "Jan - Mar/2026", "Fev - Abr", ""])
def test_chave_invalida_da_erro(ruim):
    with pytest.raises(ValueError):
        meses_da_chave_pr(ruim)


# ── POST /api/pr/salvar ──────────────────────────────────────────────────────

def test_salvar_sem_sr_da_422_e_nao_grava(client, banco):
    _popular(banco, sr=False)
    r = client.post("/api/pr/salvar", json={"periodo": "Fev - Abr/2026", "scg": 1.0, "sr": 0.0, "vp": 1.0})
    assert r.status_code == 422, r.text
    assert "Salve o SR de Out/2025 a Dez/2025 na tela SR." in r.json()["detail"]
    assert not _pr_gravado(banco, "Fev - Abr/2026")


def test_salvar_com_tudo_grava_o_valor_do_servidor_mesmo_com_zeros(client, banco):
    _popular(banco)
    r = client.post("/api/pr/salvar", json={"periodo": "Fev - Abr/2026", "scg": 0.0, "sr": 0.0, "vp": 0.0})
    assert r.status_code == 200, r.text
    assert r.json()["pr"] == PR_ESPERADO
    linha = _pr_gravado(banco, "Fev - Abr/2026")
    assert linha["pr"] == PR_ESPERADO
    assert linha["scg"] == pytest.approx(-722_000.0)  # SCG com SELIC
    assert linha["sr"] == pytest.approx(-17_000.0)
    assert linha["vp"] == pytest.approx(30_000_000.0)
    assert r.json()["pv_automatico"]["pv"] == pytest.approx(2.0 + PR_ESPERADO)


def test_salvar_aceita_pedido_so_com_a_chave(client, banco):
    _popular(banco)
    r = client.post("/api/pr/salvar", json={"periodo": "Fev - Abr/2026"})
    assert r.status_code == 200, r.text
    assert r.json()["pr"] == PR_ESPERADO


def test_salvar_sem_vp_da_422(client, banco):
    _popular(banco)
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_vp_periodo("Mar/2026", 0.0)
    r = client.post("/api/pr/salvar", json={"periodo": "Fev - Abr/2026"})
    assert r.status_code == 422
    assert "Sem VP para Mar/2026" in r.json()["detail"]
    assert not _pr_gravado(banco, "Fev - Abr/2026")


def test_salvar_com_sr_pela_metade_da_422(client, banco):
    _popular(banco, meses_sr=["Out/2025", "Nov/2025"])
    r = client.post("/api/pr/salvar", json={"periodo": "Fev - Abr/2026"})
    assert r.status_code == 422
    assert "Falta o SR de Dez/2025" in r.json()["detail"]
    assert not _pr_gravado(banco, "Fev - Abr/2026")


def test_salvar_chave_fora_do_formato_da_422(client):
    r = client.post("/api/pr/salvar", json={"periodo": "Jan/2026", "scg": 1.0, "sr": 1.0, "vp": 1.0})
    assert r.status_code == 422
    assert "não é um trimestre da tarifa" in r.json()["detail"]


# ── PR automático (ao salvar SCG, SR e módulos) ───────────────────────────────

def test_pr_automatico_sem_sr_nao_grava(banco):
    _popular(banco, sr=False)
    r = auto.atualizar_do_mes("Nov/2025")
    assert r["meses_pr"] == MESES_PR
    assert r["atualizado"] is False and r["pr"] is None
    assert "Salve o SR de Out/2025 a Dez/2025 na tela SR." in r["pendencias"]
    assert not _pr_gravado(banco, "Fev - Abr/2026")


def test_pr_automatico_com_tudo_grava(banco):
    _popular(banco)
    r = auto.atualizar_do_mes("Nov/2025")
    assert r["atualizado"] is True and r["pr"] == PR_ESPERADO
    assert _pr_gravado(banco, "Fev - Abr/2026")["pr"] == PR_ESPERADO


# ── rota antiga removida ─────────────────────────────────────────────────────

def test_rota_pr_trimestral_nao_existe_mais(client):
    r = client.post("/api/pr/trimestral", json={"periodos": MESES_PR})
    assert r.status_code == 404
