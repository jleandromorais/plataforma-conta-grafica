"""PR e PV regravados ao salvar Auditoria, CGF, RET ou RP.

Esses módulos mudam o SCG da consolidação e o PR sai dele; antes, o PR e o PV gravados
ficavam velhos até alguém salvar o SCG ou o SR de novo. Valores fictícios; banco temporário."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_pr_automatico as auto


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "pr_modulos.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def chamadas(monkeypatch):
    """Registra os períodos que o `atualizar_sem_falhar` recebeu, sem mexer no banco."""
    visto: list[str] = []
    monkeypatch.setattr(auto, "atualizar_sem_falhar", lambda p: visto.append(p) or {"atualizado": False})
    return visto


# ── atualizar_dos_meses ──────────────────────────────────────────────────────

def test_meses_do_mesmo_trimestre_atualizam_uma_vez(chamadas):
    auto.atualizar_dos_meses(["Jul/2026", "Ago/2026", "Set/2026"])
    assert chamadas == ["Jul/2026"]


def test_trimestres_diferentes_atualizam_cada_um(chamadas):
    auto.atualizar_dos_meses(["Jun/2026", "Jul/2026", "Out/2026"])
    assert chamadas == ["Jun/2026", "Jul/2026", "Out/2026"]


def test_periodo_com_ano_curto_e_normalizado(chamadas):
    auto.atualizar_dos_meses(["jul/26"])
    assert chamadas == ["Jul/2026"]


def test_periodo_invalido_ou_vazio_e_ignorado(chamadas):
    assert auto.atualizar_dos_meses(["", "Teste2", "jan"]) == []
    assert chamadas == []


# ── os quatro "salvar" chamam a atualização ──────────────────────────────────

def test_api_conciliacao_salvar_atualiza_pr_e_pv(client, chamadas):
    itens = [{"arquivo": "d.pdf", "caminho": "despesas/d.pdf", "categoria": "Despesa", "valor": 500.0,
              "status": "OK", "metodo": "x"}]
    resp = client.post("/api/conciliacao/salvar", json={"periodo": "Jul/2026", "itens": itens})
    assert resp.status_code == 200, resp.text
    assert chamadas == ["Jul/2026"]


def test_api_cgf_salvar_atualiza_pr_e_pv(client, chamadas):
    corpo = {"periodo": "Ago/2026", "pmpv": 2.5, "volume_faturado": 1000.0, "volume_canceladas": 0.0,
             "volume_devolucoes": 100.0, "volume_consumo_proprio": 0.0, "volume_final": 900.0}
    resp = client.post("/api/cgf/salvar", json=corpo)
    assert resp.status_code == 200, resp.text
    assert chamadas == ["Ago/2026"]


def test_cgf_recusado_nao_atualiza(client, chamadas):
    corpo = {"periodo": "Ago/2026", "pmpv": 0, "volume_faturado": 1000.0, "volume_canceladas": 0.0,
             "volume_devolucoes": 100.0, "volume_consumo_proprio": 0.0, "volume_final": 900.0}
    assert client.post("/api/cgf/salvar", json=corpo).status_code == 422  # sem PMPV: nada foi gravado
    assert chamadas == []


def test_api_auditoria_salvar_atualiza_pr_e_pv(client, chamadas, monkeypatch):
    from Src.api.routers import auditoria
    monkeypatch.setattr(auditoria.lote, "salvar", lambda periodo, itens: {"cgr_liquido": 1.0, "rpv": 1.0, "qtd_itens": 0})
    resp = client.post("/api/auditoria/salvar", json={"periodo": "Set/2026", "itens": []})
    assert resp.status_code == 200, resp.text
    assert chamadas == ["Set/2026"]


def test_api_ret_salvar_atualiza_os_meses_salvos(client, chamadas, monkeypatch):
    from Src.api.routers import ret
    monkeypatch.setattr(ret.lote_ret, "agrupar_por_mes", lambda docs, periodo_padrao="": {})
    monkeypatch.setattr(ret.lote_ret, "salvar_meses", lambda grupos: [
        {"periodo": "Jul/2026", "ret": 10.0, "qtd_documentos": 1},
        {"periodo": "Ago/2026", "ret": 20.0, "qtd_documentos": 1},
    ])
    doc = {"arquivo": "a.pdf", "caminho": "EAT/a.pdf", "tipo_encargo": "EAT", "empresa": "X", "nota_tipo": "ND",
           "numero_nd": "1", "data_vencimento": "01/08/2026", "valor_total": 10.0}
    resp = client.post("/api/ret/salvar", json={"documentos": [doc]})
    assert resp.status_code == 200, resp.text
    assert chamadas == ["Jul/2026"]  # Jul e Ago são do mesmo trimestre civil: uma atualização só


# ── a cadeia inteira, gravando de verdade no banco temporário ────────────────

def test_salvar_cgf_regrava_o_pr_velho_e_o_pv(client, tmp_path):
    """PR velho no banco + salvar um módulo do trimestre → PR e PV novos gravados.
    Só a apuração (leitura do SCG/SR/VP) é fixa; a gravação do PR e do PV é a real."""
    from unittest.mock import patch

    from Src.Services.servicos_pr import ServicosPR

    caminho = str(tmp_path / "pr_modulos.db")
    with DatabasePMPV(db_path=caminho) as db:
        for p in ("Nov/2026", "Dez/2026", "Jan/2027"):
            db.salvar_pmpv_mensal(p, 2.0)
        db.salvar_pr("Nov - Jan/2027", 0.0, 0.0, 0.0, -0.0069)  # PR velho, de antes do módulo mudar

    apuracao = {"scg_selic": -300000.0, "sr": 41053.09, "vp": 135000000.0, "pr": -0.0019, "pendencias": []}
    corpo = {"periodo": "Jul/2026", "pmpv": 2.5, "volume_faturado": 1000.0, "volume_canceladas": 0.0,
             "volume_devolucoes": 100.0, "volume_consumo_proprio": 0.0, "volume_final": 900.0}
    with patch.object(ServicosPR, "apurar_trimestre", return_value=apuracao):
        resp = client.post("/api/cgf/salvar", json=corpo)
    assert resp.status_code == 200, resp.text

    novo_pr = round((-300000.0 + 41053.09) / 135000000.0, 4)
    with DatabasePMPV(db_path=caminho) as db:
        assert db.buscar_pr("Nov - Jan/2027")["pr"] == pytest.approx(novo_pr)   # o PR velho foi trocado
        assert db.buscar_pv("Nov - Jan/2026")["pv"] == pytest.approx(2.0 + novo_pr)  # e o PV foi gravado
