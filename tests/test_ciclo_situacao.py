"""GET /ciclo/situacao: o roteiro de 5 passos de um trimestre. Só lê.

Valores fictícios; banco temporário (nunca o banco real); o Banco Central é simulado
(série diária sintética) e o "hoje" é fixado, para o resultado não depender do dia em que o teste roda.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.tarifa import servicos_selic
from Src.Services.tarifa.servicos_selic import fechamento_do_trimestre, ultimo_dia_util
from tests.test_cascata import _estado, _popular

TRIM = "Jul/2026_Set/2026"
CIVIL = ["Jul/2026", "Ago/2026", "Set/2026"]


def _serie(ate: date, desde: date = date(2026, 7, 1)) -> list[dict]:
    """Taxa diária fictícia (0,05%) em todos os dias de semana de `desde` até `ate`."""
    dias, d = [], desde
    while d <= ate:
        if d.weekday() < 5:
            dias.append({"data": d.strftime("%d/%m/%Y"), "valor": "0.05"})
        d += timedelta(days=1)
    return dias


def _hoje(monkeypatch, dia: date) -> None:
    class DataFixa(date):
        @classmethod
        def today(cls):
            return dia

    monkeypatch.setattr(servicos_selic, "date", DataFixa)


def _bc(monkeypatch, publicada_ate: date) -> None:
    monkeypatch.setattr(servicos_selic, "buscar_bcb",
                        lambda ini, fim: [d for d in _serie(publicada_ate, ini)
                                          if date(*map(int, d["data"].split("/")[::-1])) <= fim])


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "ciclo.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _passos(corpo: dict) -> dict:
    return {p["chave"]: p for p in corpo["passos"]}


def _situacao(client, trimestre: str = TRIM) -> dict:
    r = client.get("/api/ciclo/situacao", params={"trimestre": trimestre})
    assert r.status_code == 200, r.text
    return r.json()


# ── a SELIC fechou? ──────────────────────────────────────────────────────────

def test_selic_antes_do_fechamento_esta_aberta():
    r = fechamento_do_trimestre(CIVIL, hoje=date(2026, 9, 30), buscar=lambda *_: pytest.fail("não consulta o BC"))
    assert r["fechada"] is False and r["estado"] == "aberta"
    assert r["fecha_em"] == "2026-09-30" and r["libera_em"] == "2026-10-01"
    assert "fecha em 30/09/2026" in r["motivo"]


def test_selic_depois_do_fim_mas_sem_o_ultimo_dia_util_aguarda_a_publicacao():
    r = fechamento_do_trimestre(CIVIL, hoje=date(2026, 10, 1), buscar=lambda ini, fim: _serie(date(2026, 9, 29), ini))
    assert r["fechada"] is False and r["estado"] == "aguardando_publicacao"
    assert r["publicada_ate"] == "2026-09-29" and r["ultimo_dia_util"] == "2026-09-30"
    assert "30/09/2026" in r["motivo"]


def test_selic_com_o_ultimo_dia_util_publicado_esta_fechada():
    r = fechamento_do_trimestre(CIVIL, hoje=date(2026, 10, 1), buscar=lambda ini, fim: _serie(date(2026, 9, 30), ini))
    assert r["fechada"] is True and r["estado"] == "fechada" and r["publicada_ate"] == "2026-09-30"


def test_selic_com_mes_inteiro_sem_dados_nao_fecha():
    sem_julho = lambda ini, fim: _serie(date(2026, 9, 30), date(2026, 8, 1))  # noqa: E731
    r = fechamento_do_trimestre(CIVIL, hoje=date(2026, 10, 5), buscar=sem_julho)
    assert r["fechada"] is False and r["estado"] == "aguardando_publicacao"


def test_selic_banco_central_fora_do_ar_e_indisponivel():
    def fora(*_):
        raise servicos_selic.SelicIndisponivel("O BC não respondeu.")

    r = fechamento_do_trimestre(CIVIL, hoje=date(2026, 10, 5), buscar=fora)
    assert r["fechada"] is False and r["estado"] == "indisponivel" and r["motivo"] == "O BC não respondeu."


def test_ultimo_dia_util_pula_o_fim_de_semana():
    assert ultimo_dia_util(date(2029, 3, 31)) == date(2029, 3, 30)  # sábado -> sexta
    assert ultimo_dia_util(date(2026, 9, 30)) == date(2026, 9, 30)  # quarta


# ── a rota ───────────────────────────────────────────────────────────────────

def test_antes_do_fechamento_da_selic_o_sr_fica_bloqueado_com_a_data(client, banco, monkeypatch):
    _popular(banco)
    _hoje(monkeypatch, date(2026, 9, 15))
    corpo = _situacao(client)
    sr = _passos(corpo)["sr"]
    assert sr["estado"] == "bloqueado" and "fecha em 30/09/2026" in sr["motivo"]
    assert corpo["selic"]["estado"] == "aberta" and corpo["selic"]["libera_em"] == "2026-10-01"
    assert _passos(corpo)["pmpv_anterior"]["estado"] == "pronto" and _passos(corpo)["pasta_scg"]["estado"] == "pronto"
    assert corpo["proximo_passo"] == "sr"


def test_selic_aguardando_publicacao_bloqueia_o_sr(client, banco, monkeypatch):
    _popular(banco)
    _hoje(monkeypatch, date(2026, 10, 1))
    _bc(monkeypatch, date(2026, 9, 29))
    corpo = _situacao(client)
    assert corpo["selic"]["estado"] == "aguardando_publicacao" and corpo["selic"]["fechada"] is False
    assert _passos(corpo)["sr"]["estado"] == "bloqueado"


def test_depois_do_fechamento_o_sr_calculado_pede_aprovacao(client, banco, monkeypatch):
    _popular(banco)
    _hoje(monkeypatch, date(2026, 10, 2))
    _bc(monkeypatch, date(2026, 9, 30))
    antes = _estado(banco)
    corpo = _situacao(client)
    assert corpo["selic"]["fechada"] is True
    sr = _passos(corpo)["sr"]
    assert sr["estado"] == "atencao" and "ainda não gravado" in sr["motivo"] and "R$" in sr["motivo"]
    assert _estado(banco) == antes  # a situação só lê


def test_pmpv_novo_ausente_bloqueia_pr_e_pv_mas_o_sr_grava(client, banco, monkeypatch):
    _popular(banco, com_pmpv_novo=False)
    _hoje(monkeypatch, date(2026, 10, 2))
    _bc(monkeypatch, date(2026, 9, 30))
    # o SR grava sem o PMPV seguinte
    r = client.post("/api/cascata/aplicar", json={"periodos": ["Jul/2026"], "ate": "sr"})
    assert r.status_code == 200, r.text
    corpo = _situacao(client)
    passos = _passos(corpo)
    assert passos["sr"]["estado"] == "pronto"
    assert passos["pr_pv"]["estado"] == "bloqueado" and passos["pr_pv"]["rota"] == "/pmpv"
    assert "Nov/2026" in passos["pr_pv"]["motivo"]
    assert passos["tarifa_media"]["estado"] == "bloqueado"
    assert corpo["pmpv_novo"]["existe"] is False and corpo["pmpv_novo"]["meses_sem_vp"] == ["Nov/2026", "Dez/2026", "Jan/2027"]
    assert corpo["trimestre_pr"] == {"meses": ["Nov/2026", "Dez/2026", "Jan/2027"],
                                     "chave_pr": "Nov - Jan/2027", "chave_pv": "Nov - Jan/2026"}
    assert corpo["proximo_passo"] == "pr_pv"


def test_pr_pv_sem_sr_gravado_fica_bloqueado_e_com_tudo_gravado_fica_pronto(client, banco, monkeypatch):
    _popular(banco)
    _hoje(monkeypatch, date(2026, 10, 2))
    _bc(monkeypatch, date(2026, 9, 30))
    assert _passos(_situacao(client))["pr_pv"]["estado"] == "bloqueado"  # SR ainda não gravado

    assert client.post("/api/cascata/aplicar", json={"periodos": ["Jul/2026"], "ate": "sr"}).status_code == 200
    meio = _situacao(client)
    assert _passos(meio)["sr"]["estado"] == "pronto"
    assert _passos(meio)["pr_pv"]["estado"] == "atencao" and meio["pmpv_novo"]["existe"] is True

    r = client.post("/api/cascata/aplicar", json={"periodos": ["Jul/2026"], "a_partir_de": "pr"})
    assert r.status_code == 200, r.text
    fim = _situacao(client)
    assert [p["estado"] for p in fim["passos"]] == ["pronto"] * 5
    assert fim["proximo_passo"] is None


def test_sem_vp_ou_sem_scg_o_passo_diz_o_que_falta(client, banco, monkeypatch):
    _popular(banco, sem_vp_em="Set/2026")
    _hoje(monkeypatch, date(2026, 10, 2))
    _bc(monkeypatch, date(2026, 9, 30))
    passos = _passos(_situacao(client))
    assert passos["pmpv_anterior"]["estado"] == "falta" and "Set/2026" in passos["pmpv_anterior"]["motivo"]
    assert passos["sr"]["estado"] == "bloqueado" and "passo 1" in passos["sr"]["motivo"]


def test_banco_vazio_nao_quebra(client, monkeypatch):
    _hoje(monkeypatch, date(2026, 10, 2))
    _bc(monkeypatch, date(2026, 9, 30))
    corpo = _situacao(client)
    assert [p["estado"] for p in corpo["passos"]] == ["falta", "falta", "bloqueado", "bloqueado", "bloqueado"]
    assert corpo["proximo_passo"] == "pmpv_anterior"


@pytest.mark.parametrize("entrada", ["Ago/2026", "Jul/2026_Set/2026", "jul/2026_set/2026"])
def test_aceita_o_rotulo_do_sr_ou_um_mes_do_trimestre(client, entrada, monkeypatch):
    _hoje(monkeypatch, date(2026, 9, 15))
    corpo = _situacao(client, entrada)
    assert corpo["trimestre"] == TRIM and corpo["meses"] == CIVIL


@pytest.mark.parametrize("entrada", ["Teste1", "Jul/2026_Ago/2026", "Ago/2026_Out/2026", ""])
def test_trimestre_invalido_da_422(client, entrada):
    r = client.get("/api/ciclo/situacao", params={"trimestre": entrada})
    assert r.status_code == 422


def test_trimestre_e_obrigatorio(client):
    assert client.get("/api/ciclo/situacao").status_code == 422


def test_virada_de_ano_o_pr_do_ultimo_trimestre_civil_usa_os_anos_certos(client, monkeypatch):
    _hoje(monkeypatch, date(2026, 9, 15))
    corpo = _situacao(client, "Out/2026_Dez/2026")
    assert corpo["trimestre_pr"] == {"meses": ["Fev/2027", "Mar/2027", "Abr/2027"],
                                     "chave_pr": "Fev - Abr/2027", "chave_pv": "Fev - Abr/2027"}
    assert corpo["selic"]["fecha_em"] == "2026-12-31"
