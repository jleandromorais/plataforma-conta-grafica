"""GET /tarifa/media: PV gravado + MB (só leitura). Valores fictícios; banco temporário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.tarifa.servicos_margem import salvar_margem


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "tarifa.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _gravar_pv(banco: str, chave: str, pv: float) -> None:
    """Grava o PV do trimestre e o PMPV dos 3 meses com o mesmo valor (PR 0), para o PV gravado
    bater com o que os módulos calculam e não surgir o aviso de "PV desatualizado"."""
    from Src.common.periodos import periodos_do_trimestre
    label, ano = chave.rsplit("/", 1)
    with DatabasePMPV(db_path=banco) as db:
        for mes in periodos_do_trimestre(label, int(ano)):
            db.salvar_pmpv_mensal(mes, pv)
        db.salvar_pv(chave, pv, 0.0, pv)


def test_mb_ausente_da_tarifa_nula_e_aviso(client, banco):
    _gravar_pv(banco, "Fev - Abr/2027", 1.0)          # 2027 não tem MB padrão
    r = client.get("/api/tarifa/media", params={"trimestre": "Fev/2027_Abr/2027"})
    assert r.status_code == 200
    d = r.json()
    assert d["margens"] == [{"ano": 2027, "mb": None, "origem": "ausente"}]
    assert d["tarifas"] == [{"ano": 2027, "mb": None, "tarifa_media": None}]
    assert d["aviso"] and "2027" in d["aviso"]
    assert d["motivo"] and "MB" in d["motivo"]
    assert d["cruza_ano"] is False and d["pv_gravado"] == 1.0


def test_mb_padrao_com_pv_um_da_1_5410(client, banco):
    _gravar_pv(banco, "Fev - Abr/2026", 1.0)
    d = client.get("/api/tarifa/media", params={"trimestre": "Fev/2026_Abr/2026"}).json()
    assert d["chave_pv"] == "Fev - Abr/2026"
    assert d["margens"] == [{"ano": 2026, "mb": 0.541, "origem": "padrao"}]
    assert d["tarifas"][0]["tarifa_media"] == pytest.approx(1.5410)
    assert d["aviso"] is None and d["motivo"] is None


def test_nov_jan_com_duas_mbs_devolve_as_duas_sem_escolher(client, banco):
    salvar_margem(2025, 0.5000)
    salvar_margem(2026, 0.5410)
    _gravar_pv(banco, "Nov - Jan/2025", 2.0)           # chave com o ano do 1º mês
    d = client.get("/api/tarifa/media", params={"trimestre": "Dez/2025"}).json()
    assert d["trimestre"] == "Nov/2025_Jan/2026" and d["chave_pv"] == "Nov - Jan/2025"
    assert d["cruza_ano"] is True
    assert [t["ano"] for t in d["tarifas"]] == [2025, 2026]
    assert d["tarifas"][0]["tarifa_media"] == pytest.approx(2.5000)
    assert d["tarifas"][1]["tarifa_media"] == pytest.approx(2.5410)
    assert [m["origem"] for m in d["margens"]] == ["salva", "salva"]
    assert "não escolhe" in d["aviso"]


def test_nov_jan_com_mbs_iguais_nao_avisa_diferenca(client, banco):
    salvar_margem(2025, 0.5410)
    _gravar_pv(banco, "Nov - Jan/2025", 2.0)
    d = client.get("/api/tarifa/media", params={"trimestre": "Nov/2025_Jan/2026"}).json()
    assert len(d["tarifas"]) == 2 and d["aviso"] is None


def test_pv_nao_gravado_da_tarifa_nula_com_motivo(client, banco):
    salvar_margem(2026, 0.5410)
    d = client.get("/api/tarifa/media", params={"trimestre": "Mai/2026_Jul/2026"}).json()
    assert d["pv_gravado"] is None
    assert d["motivo"] == "grave o PV primeiro"
    assert d["tarifas"] == [{"ano": 2026, "mb": 0.541, "tarifa_media": None}]


def test_virada_de_ano_pv_de_jan_usa_a_chave_do_ano_anterior(client, banco):
    _gravar_pv(banco, "Nov - Jan/2026", 3.0)
    d = client.get("/api/tarifa/media", params={"trimestre": "Jan/2027"}).json()
    assert d["chave_pv"] == "Nov - Jan/2026" and d["pv_gravado"] == 3.0


@pytest.mark.parametrize("texto", ["Jul/2026_Set/2026", "Nov/2025_Dez/2025", "lixo", "Nov/2025_Jan/2026_Fev/2026"])
def test_trimestre_invalido_da_422(client, texto):
    r = client.get("/api/tarifa/media", params={"trimestre": texto})
    assert r.status_code == 422 and "trimestre" in r.json()["detail"].lower()


def test_nao_grava_nada(client, banco):
    _gravar_pv(banco, "Nov - Jan/2025", 2.0)
    with DatabasePMPV(db_path=banco) as db:
        antes = db.cursor.execute("SELECT COUNT(*) FROM pv_resultados").fetchone()[0]
    client.get("/api/tarifa/media", params={"trimestre": "Nov/2025_Jan/2026"})
    with DatabasePMPV(db_path=banco) as db:
        assert db.cursor.execute("SELECT COUNT(*) FROM pv_resultados").fetchone()[0] == antes


def test_exige_login(client):
    from Src.api.auth import usuario_atual
    from Src.api.main import app
    app.dependency_overrides.pop(usuario_atual, None)
    assert client.get("/api/tarifa/media", params={"trimestre": "Dez/2025"}).status_code == 401


def test_avisa_quando_pv_gravado_difere_dos_modulos(client, banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pv("Fev - Abr/2026", 1.0, 0.0, 1.0)     # sem PMPV mensal: os módulos dão outro valor
    d = client.get("/api/tarifa/media", params={"trimestre": "Fev/2026_Abr/2026"}).json()
    assert d["tarifas"][0]["tarifa_media"] == pytest.approx(1.5410)
    assert "difere" in d["aviso"]
