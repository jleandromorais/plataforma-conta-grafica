"""Dashboard › Conferência do mês: CGR, CGF, RET e RP contra o mês anterior. Valores fictícios; banco temporário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "conferencia.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _gravar_mes(periodo: str, **valores: float) -> None:
    with ServicosConsolidacao() as cons:
        cons.salvar_valores(periodo, **valores)


def _nota(empresa: str, valor: float = 100.0) -> dict:
    return {"empresa": empresa, "tipo": "NF-e", "numero": "1", "valor_total": valor, "cgr_liquido": valor}


def _etapa(corpo: dict, nome: str) -> dict:
    return next(e for e in corpo["etapas"] if e["etapa"] == nome)


def test_empresa_que_mandou_no_mes_anterior_e_nao_neste_aparece_como_faltando(client, banco):
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_auditoria_itens("Ago/2026", [_nota("Empresa A"), _nota("Empresa B"), _nota("Empresa C")])
        db.salvar_auditoria_itens("Set/2026", [_nota("empresa a "), _nota("Empresa C")])  # B sumiu; "A" só mudou a caixa
        db.salvar_ret_itens("Ago/2026", [{"arquivo": "a.pdf", "tipo_encargo": "EAT", "empresa": "Fornecedor X", "valor_total": 10.0},
                                         {"arquivo": "b.pdf", "tipo_encargo": "EAT", "empresa": "Fornecedor Y", "valor_total": 10.0}])
        db.salvar_ret_itens("Set/2026", [{"arquivo": "a.pdf", "tipo_encargo": "EAT", "empresa": "Fornecedor X", "valor_total": 10.0}])
    r = client.get("/api/dashboard/conferencia", params={"periodo": "Set/2026"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["periodo"] == "Set/2026" and corpo["periodo_anterior"] == "Ago/2026"
    assert _etapa(corpo, "CGR")["empresas_faltando"] == ["Empresa B"]
    assert _etapa(corpo, "RET")["empresas_faltando"] == ["Fornecedor Y"]
    # CGF e RP não têm empresa por nota
    assert _etapa(corpo, "CGF")["empresas_faltando"] == [] and _etapa(corpo, "RP")["empresas_faltando"] == []


def test_variacao_de_25_por_cento_marca_e_de_15_nao_marca(client, banco):
    _gravar_mes("Ago/2026", cgr=1000.0, ret=1000.0)
    _gravar_mes("Set/2026", cgr=1250.0, ret=1150.0)   # +25% e +15%
    corpo = client.get("/api/dashboard/conferencia", params={"periodo": "Set/2026"}).json()
    cgr, ret = _etapa(corpo, "CGR"), _etapa(corpo, "RET")
    assert cgr["variacao_pct"] == pytest.approx(25.0) and cgr["fora_do_normal"] is True
    assert ret["variacao_pct"] == pytest.approx(15.0) and ret["fora_do_normal"] is False
    assert (cgr["total"], cgr["total_anterior"]) == (1250.0, 1000.0)
    assert corpo["limite_pct"] == 20.0


def test_queda_acima_de_20_por_cento_tambem_marca(client):
    _gravar_mes("Ago/2026", cgr=1000.0)
    _gravar_mes("Set/2026", cgr=700.0)
    cgr = _etapa(client.get("/api/dashboard/conferencia", params={"periodo": "Set/2026"}).json(), "CGR")
    assert cgr["variacao_pct"] == pytest.approx(-30.0) and cgr["fora_do_normal"] is True


def test_exatamente_20_por_cento_nao_marca(client):
    _gravar_mes("Ago/2026", cgr=1000.0)
    _gravar_mes("Set/2026", cgr=1200.0)
    assert _etapa(client.get("/api/dashboard/conferencia", params={"periodo": "Set/2026"}).json(), "CGR")["fora_do_normal"] is False


def test_mes_sem_dados_ou_anterior_zerado_nao_compara(client):
    _gravar_mes("Ago/2026", cgr=0.0)          # anterior zerado: não dá para calcular %
    _gravar_mes("Set/2026", cgr=500.0)
    corpo = client.get("/api/dashboard/conferencia", params={"periodo": "Set/2026"}).json()
    assert _etapa(corpo, "CGR")["variacao_pct"] is None and _etapa(corpo, "CGR")["fora_do_normal"] is False
    # RP não foi gravado em nenhum dos dois meses
    assert _etapa(corpo, "RP")["total"] is None or _etapa(corpo, "RP")["fora_do_normal"] is False


def test_virada_de_ano_compara_com_dezembro(client):
    _gravar_mes("Dez/2025", cgr=1000.0)
    _gravar_mes("Jan/2026", cgr=1500.0)
    corpo = client.get("/api/dashboard/conferencia", params={"periodo": "Jan/2026"}).json()
    assert corpo["periodo_anterior"] == "Dez/2025" and _etapa(corpo, "CGR")["fora_do_normal"] is True


def test_periodo_invalido_da_422(client):
    r = client.get("/api/dashboard/conferencia", params={"periodo": "Teste1"})
    assert r.status_code == 422 and "não é válido" in r.json()["detail"]


def test_nao_grava_nada(client, banco):
    _gravar_mes("Ago/2026", cgr=1000.0)
    with DatabasePMPV(db_path=banco) as db:
        antes = db.buscar_consolidacao("Set/2026")
    client.get("/api/dashboard/conferencia", params={"periodo": "Set/2026"})
    with DatabasePMPV(db_path=banco) as db:
        assert db.buscar_consolidacao("Set/2026") == antes
