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
    # o SR automático também fica de fora: estes testes só olham quais trimestres são atualizados
    monkeypatch.setattr(auto, "atualizar_sr_sem_falhar", lambda p: {"atualizado": False, "pendencias": []})
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


# ── SR automático: o SR do trimestre civil é recalculado antes do PR ─────────

MESES_SR = ["Jul/2026", "Ago/2026", "Set/2026"]
VP_SR = [40_000_000.0, 41_000_000.0, 42_000_000.0]   # valores fictícios
VF_SR = [38_000_000.0, 39_000_000.0, 40_000_000.0]
SELIC_SR = {"Jul/2026": 3.0, "Ago/2026": 2.0, "Set/2026": 1.0}
# PR do trimestre da tarifa do próprio mês: Jul usa Mai–Jul; Ago e Set usam Ago–Out
PR_SR = {"Mai - Jul/2026": -0.0200, "Ago - Out/2026": -0.0300}


@pytest.fixture()
def banco_sr(tmp_path, monkeypatch):
    from Src.Services import servicos_selic
    caminho = str(tmp_path / "sr_auto.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", lambda meses, hoje=None, buscar=None: {
        "disponivel": True, "valores": dict(SELIC_SR), "fecha_em": "2026-09-30", "fonte": "Banco Central (série 11)"})
    return caminho


def _popular_sr(caminho: str, sem_vp_em: str | None = None) -> None:
    with DatabasePMPV(db_path=caminho) as db:
        for i, mes in enumerate(MESES_SR):
            if mes != sem_vp_em:
                db.salvar_vp_periodo(mes, VP_SR[i])
            db.salvar_cgf_resumo(mes, 0, 0, 0, 0, VF_SR[i])
        for chave, pr in PR_SR.items():
            db.salvar_pr(chave, 0, 0, 1, pr)


def test_meses_do_trimestre_civil():
    assert auto.meses_do_trimestre_civil("Ago/2026") == MESES_SR
    assert auto.meses_do_trimestre_civil("Dez/2026") == ["Out/2026", "Nov/2026", "Dez/2026"]


def test_sr_trimestre_completo_e_gravado(banco_sr):
    _popular_sr(banco_sr)
    r = auto.atualizar_sr_do_mes("Ago/2026")
    assert r["atualizado"] is True and r["pendencias"] == []
    assert r["trimestre"] == "Jul/2026_Set/2026" and r["sr_antes"] is None
    # SR do mês = (VP − VF) × PR do trimestre do próprio mês × (1 + SELIC%)
    esperado = [(VP_SR[i] - VF_SR[i]) * pr * (1 + SELIC_SR[m] / 100)
                for i, (m, pr) in enumerate(zip(MESES_SR, (-0.0200, -0.0300, -0.0300)))]
    with DatabasePMPV(db_path=banco_sr) as db:
        gravados = {g["mes"]: g for g in db.buscar_sr_trimestre("Jul/2026_Set/2026")}
    for mes, sr in zip(MESES_SR, esperado):
        assert gravados[mes]["sr_selic"] == pytest.approx(sr)
    assert r["sr"] == pytest.approx(sum(esperado))


def test_sr_com_pendencia_nao_grava_nada(banco_sr):
    _popular_sr(banco_sr, sem_vp_em="Set/2026")
    with DatabasePMPV(db_path=banco_sr) as db:   # um SR antigo que NÃO pode ser sobrescrito
        db.salvar_sr_trimestre("Jul/2026_Set/2026", [
            {"mes": m, "vp": 1.0, "vf": 1.0, "pr": 0.0, "selic_mensal": 0.0, "diferenca": 0.0,
             "sr_parcela": 0.0, "sr_selic": -100.0, "sr_anterior": 0.0, "total": -100.0} for m in MESES_SR])
    r = auto.atualizar_sr_do_mes("Jul/2026")
    assert r["atualizado"] is False and r["sr"] is None
    assert r["sr_antes"] == pytest.approx(-300.0)
    assert any("Sem VP de Set/2026" in p for p in r["pendencias"])
    with DatabasePMPV(db_path=banco_sr) as db:
        assert [g["sr_selic"] for g in db.buscar_sr_trimestre("Jul/2026_Set/2026")] == [-100.0] * 3


def test_sr_sem_internet_vira_pendencia_e_nao_zera(banco_sr, monkeypatch):
    from Src.Services import servicos_selic

    def falha(meses, hoje=None, buscar=None):
        raise servicos_selic.SelicIndisponivel("O BC não respondeu.")
    monkeypatch.setattr(servicos_selic, "selic_do_trimestre", falha)
    _popular_sr(banco_sr)
    r = auto.atualizar_sr_do_mes("Set/2026")
    assert r["atualizado"] is False and any("O BC não respondeu" in p for p in r["pendencias"])
    with DatabasePMPV(db_path=banco_sr) as db:
        assert db.buscar_sr_trimestre("Jul/2026_Set/2026") == []   # nada gravado com SELIC 0%


def test_sr_e_pr_juntos_sr_vem_primeiro(banco_sr):
    _popular_sr(banco_sr)
    r = auto.atualizar_sr_e_pr_sem_falhar("Ago/2026")
    assert r["sr_automatico"]["atualizado"] is True
    # o SR foi gravado; o PR segue sem SCG/PMPV, então avisa (pendência do PR) mas não quebra
    assert r["atualizado"] is False and r["pendencias"]
    assert r["meses_pr"] == ["Nov/2026", "Dez/2026", "Jan/2027"]


def test_sr_falha_inesperada_vira_pendencia(monkeypatch):
    def quebra(periodo):
        raise RuntimeError("banco caiu")
    monkeypatch.setattr(auto, "atualizar_sr_do_mes", quebra)
    r = auto.atualizar_sr_sem_falhar("Jul/2026")
    assert r["atualizado"] is False and "Salve pela tela do SR" in r["pendencias"][0]
    assert "banco caiu" not in r["pendencias"][0]


def test_api_salvar_scg_traz_sr_automatico(client):
    corpo = {"periodo": "Jul/2026", "cgr": 1000.0, "cgf": 900.0, "ret": 10.0, "rp": -5.0}
    resp = client.post("/api/scg/salvar", json=corpo)
    assert resp.status_code == 200, resp.text
    sr = resp.json()["pr_automatico"]["sr_automatico"]
    assert sr["trimestre"] == "Jul/2026_Set/2026"
    assert sr["atualizado"] is False and sr["pendencias"]   # banco vazio: falta VP, CGF, PR; nada vira zero


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
