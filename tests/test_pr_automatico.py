"""PR e PV regravados ao salvar o SCG ou o SR (servicos_pr_automatico).

O PR de Nov/26–Jan/27 usa o SCG e o SR de Jul–Set/26: salvar o SCG de
qualquer um desses meses regrava esse PR e o PV do mesmo trimestre.
"""
from unittest.mock import MagicMock, patch

import pytest

from Src.Services.tarifa import servicos_pr_automatico as auto
from Src.Services.tarifa.servicos_pr import ServicosPR, meses_apurados_do_pr


@pytest.mark.parametrize("periodo, meses_pr", [
    ("Jul/2026", ["Nov/2026", "Dez/2026", "Jan/2027"]),
    ("Ago/2026", ["Nov/2026", "Dez/2026", "Jan/2027"]),
    ("Set/2026", ["Nov/2026", "Dez/2026", "Jan/2027"]),
    ("Jan/2026", ["Mai/2026", "Jun/2026", "Jul/2026"]),
    ("Abr/2026", ["Ago/2026", "Set/2026", "Out/2026"]),
    ("Dez/2025", ["Fev/2026", "Mar/2026", "Abr/2026"]),
])
def test_meses_do_pr_do_civil(periodo, meses_pr):
    assert auto.meses_do_pr_do_civil(periodo) == meses_pr
    assert periodo in meses_apurados_do_pr(meses_pr)  # é o inverso da tela PR


def _apuracao(pendencias=()):
    return {"scg_selic": -300000.0, "sr": 41053.09, "vp": 135000000.0, "pr": -0.0019,
            "pendencias": list(pendencias)}


def test_grava_pr_e_pv_com_as_chaves_das_telas():
    repo = MagicMock()
    repo.buscar_pr.return_value = {"pr": 0.0}
    repo.buscar_pmpv_mensal.return_value = 2.452234
    repo.buscar_pv.return_value = {"pmpv": 2.4522, "pr": 0.0, "pv": 2.4522, "data_atualizacao": ""}

    with patch.object(ServicosPR, "apurar_trimestre", return_value=_apuracao()) as apurar:
        r = auto.atualizar_do_mes("Jul/2026", repo=repo)

    apurar.assert_called_once_with(["Nov/2026", "Dez/2026", "Jan/2027"])
    pr = round((-300000.0 + 41053.09) / 135000000.0, 4)
    # PR: chave com o ano do último mês, como a tela PR
    repo.salvar_pr.assert_called_once_with("Nov - Jan/2027", -300000.0, 41053.09, 135000000.0, pr)
    # PV: chave com o ano do 1º mês + os 3 meses, como a tela PV
    chaves, pmpv, pr_pv, pv = repo.salvar_pv_lote.call_args.args
    assert chaves == ["Nov - Jan/2026", "Nov/2026", "Dez/2026", "Jan/2027"]
    assert (pmpv, pr_pv) == (2.4522, pr)
    assert pv == pytest.approx(2.4522 + pr)
    assert r == {"meses_pr": ["Nov/2026", "Dez/2026", "Jan/2027"], "atualizado": True,
                 "pr_antes": 0.0, "pr": pr, "pv_antes": 2.4522, "pv": pytest.approx(2.4522 + pr), "pendencias": []}


def test_com_pendencia_nao_grava_nada():
    repo = MagicMock()
    with patch.object(ServicosPR, "apurar_trimestre", return_value=_apuracao(["Sem SCG gravado para Ago/2026."])):
        r = auto.atualizar_do_mes("Jul/2026", repo=repo)
    assert r["atualizado"] is False
    assert r["pendencias"] == ["Sem SCG gravado para Ago/2026."]
    repo.salvar_pr.assert_not_called()
    repo.salvar_pv_lote.assert_not_called()


def test_sem_pmpv_grava_pr_mas_avisa_do_pv():
    repo = MagicMock()
    repo.buscar_pr.return_value = None
    repo.buscar_pmpv_mensal.return_value = None
    repo.buscar_pv.return_value = None
    with patch.object(ServicosPR, "apurar_trimestre", return_value=_apuracao()):
        r = auto.atualizar_do_mes("Jul/2026", repo=repo)
    assert r["atualizado"] is True and r["pr_antes"] is None
    repo.salvar_pv_lote.assert_not_called()
    assert r["pv"] is None and any("PMPV" in p for p in r["pendencias"])


def test_falha_no_pr_vira_pendencia():
    with patch.object(auto, "atualizar_do_mes", side_effect=RuntimeError("banco caiu")):
        r = auto.atualizar_sem_falhar("Jul/2026")
    assert r["atualizado"] is False
    assert "Salve pela tela do PR" in r["pendencias"][0]
    assert "banco caiu" not in r["pendencias"][0]  # detalhe técnico fica no log


# ── API: salvar o SCG continua funcionando e devolve o PR automático ──────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    from Src.Database.database import DatabasePMPV
    caminho = tmp_path / "pr_auto.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    from fastapi.testclient import TestClient
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def test_api_salvar_scg_traz_pr_automatico(client):
    resp = client.post("/api/scg/salvar", json={"periodo": "Jul/2026", "cgr": 1000.0, "cgf": 900.0, "ret": 10.0, "rp": -5.0})
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["scg"] == pytest.approx(105.0)  # o SCG foi salvo normalmente
    pr = corpo["pr_automatico"]
    # banco vazio: falta SR, VP e o SCG de Ago/Set → nada gravado, motivo explicado
    assert pr["meses_pr"] == ["Nov/2026", "Dez/2026", "Jan/2027"]
    assert pr["atualizado"] is False and pr["pendencias"]
    assert client.get("/api/scg", params={"periodo": "Jul/2026"}).json()["scg"] == pytest.approx(105.0)
