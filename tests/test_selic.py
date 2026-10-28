"""SELIC acumulada pela regra das planilhas ARPE (spec-selic-automatica/regra-selic.md).

Os dados do Banco Central (série 11, Jul/25 a Mar/26) estão gravados em
tests/fixtures: os testes não usam a rede."""
import json
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Src.api.errors import registrar_exception_handlers
from Src.api.routers import sr as rota_sr
from Src.Services import servicos_selic as s

DIARIOS = json.loads((Path(__file__).parent / "fixtures" / "bcb_sgs11_2025-07_2026-03.json").read_text(encoding="utf-8"))
FATORES = s.fatores_mensais(DIARIOS)

# Valores das planilhas da ARPE (NT 05/2026 e Conta Gráfica até maio/26), sem arredondar.
PLANILHA = {
    ("Jul/2025", "Ago/2025", "Set/2025"): (3.704615614, 2.398286877, 1.219929000),
    ("Out/2025", "Nov/2025", "Dez/2025"): (3.590363778, 2.285474229, 1.219929000),
    ("Jan/2026", "Fev/2026", "Mar/2026"): (3.411173969, 2.221160059, 1.212053593),
}


def buscar_fixture(inicio: date, fim: date) -> list[dict]:
    def dia(d):
        dd, mm, aa = d["data"].split("/")
        return date(int(aa), int(mm), int(dd))
    return [d for d in DIARIOS if inicio <= dia(d) <= fim]


def test_selic_mensal_tem_mais_casas_que_a_serie_4390():
    assert round((FATORES[(2025, 7)] - 1) * 100, 6) == 1.275733  # a 4390 dá 1,28


@pytest.mark.parametrize("meses,esperado", PLANILHA.items())
def test_acumulada_bate_com_a_planilha_arpe(meses, esperado):
    valores = s.selic_acumulada(FATORES, list(meses))
    for periodo, valor in zip(meses, esperado):
        assert valores[periodo] == pytest.approx(valor, abs=1e-6)


def test_ultimo_mes_do_trimestre_e_so_a_selic_dele():
    v = s.selic_acumulada(FATORES, ["Jan/2026", "Fev/2026", "Mar/2026"])
    assert v["Mar/2026"] == round((FATORES[(2026, 3)] - 1) * 100, 6)


def test_trimestre_encerrado_busca_so_os_meses_dele():
    pedidos = []

    def buscar(inicio, fim):
        pedidos.append((inicio, fim))
        return buscar_fixture(inicio, fim)

    r = s.selic_do_trimestre(["Jan/2026", "Fev/2026", "Mar/2026"], hoje=date(2026, 4, 2), buscar=buscar)
    assert r["disponivel"] is True
    assert r["valores"]["Jan/2026"] == pytest.approx(3.411174, abs=1e-6)
    assert pedidos == [(date(2026, 1, 1), date(2026, 3, 31))]


def test_trimestre_em_andamento_nao_usa_selic_parcial():
    def buscar(*_):
        raise AssertionError("não deveria chamar o Banco Central")

    r = s.selic_do_trimestre(["Out/2026", "Nov/2026", "Dez/2026"], hoje=date(2026, 10, 28), buscar=buscar)
    assert r == {"disponivel": False, "valores": {}, "fecha_em": "2026-12-31", "fonte": "Banco Central (série 11)"}


def test_mes_sem_dados_do_bc_avisa_qual_falta():
    with pytest.raises(s.SelicIndisponivel, match="Mar/2026"):
        s.selic_acumulada({(2026, 1): 1.01, (2026, 2): 1.01}, ["Jan/2026", "Fev/2026", "Mar/2026"])


@pytest.mark.parametrize("meses", [
    ["Fev/2026", "Mar/2026", "Abr/2026"],  # trimestre fiscal, não civil
    ["Jan/2026", "Mar/2026", "Fev/2026"],
    ["Jan/2026", "Fev/2026"],
    ["Xyz/2026", "Fev/2026", "Mar/2026"],
])
def test_periodo_que_nao_e_trimestre_civil_e_recusado(meses):
    with pytest.raises(ValueError):
        s.fim_do_trimestre(meses)


def test_bc_que_trava_uma_vez_e_responde_na_segunda(monkeypatch):
    chamadas = []

    class Resposta:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'[{"data":"02/01/2026","valor":"0.055131"}]'

    def urlopen(url, timeout):
        chamadas.append(url)
        if len(chamadas) == 1:
            raise TimeoutError("The read operation timed out")
        return Resposta()

    monkeypatch.setattr(s.urllib.request, "urlopen", urlopen)
    assert s.buscar_bcb(date(2026, 1, 1), date(2026, 3, 31)) == [{"data": "02/01/2026", "valor": "0.055131"}]
    assert len(chamadas) == 2


def test_bc_que_nunca_responde_vira_mensagem_para_o_usuario(monkeypatch):
    def urlopen(url, timeout):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(s.urllib.request, "urlopen", urlopen)
    with pytest.raises(s.SelicIndisponivel, match="digite a SELIC à mão"):
        s.buscar_bcb(date(2026, 1, 1), date(2026, 3, 31))


@pytest.fixture()
def cliente(monkeypatch):
    app = FastAPI()
    registrar_exception_handlers(app)
    app.include_router(rota_sr.router)
    return TestClient(app, raise_server_exceptions=False)


def test_endpoint_devolve_a_selic_do_trimestre(cliente, monkeypatch):
    monkeypatch.setattr(s, "buscar_bcb", buscar_fixture)
    r = cliente.get("/sr/selic", params={"meses": ["Out/2025", "Nov/2025", "Dez/2025"]})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["disponivel"] is True
    assert corpo["valores"]["Nov/2025"] == pytest.approx(2.285474, abs=1e-6)


def test_endpoint_com_bc_fora_do_ar_responde_503_com_mensagem_clara(cliente, monkeypatch):
    def fora(*_):
        raise s.SelicIndisponivel("Não foi possível buscar a SELIC no Banco Central: o site do BC não respondeu.")

    monkeypatch.setattr(s, "buscar_bcb", fora)
    r = cliente.get("/sr/selic", params={"meses": ["Jan/2026", "Fev/2026", "Mar/2026"]})
    assert r.status_code == 503
    assert "Banco Central" in r.json()["detail"]


def test_endpoint_com_periodo_invalido_responde_422(cliente):
    r = cliente.get("/sr/selic", params={"meses": ["Fev/2026", "Mar/2026", "Abr/2026"]})
    assert r.status_code == 422
    assert "trimestre civil" in r.json()["detail"]
