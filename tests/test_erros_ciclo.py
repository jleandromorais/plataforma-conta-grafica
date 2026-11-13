"""Campo `erros` (frases em pt-BR) das provas reais e das diferenças. Só valores fictícios."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.api import erros_ciclo
from Src.Database.database import DatabasePMPV
from Src.Services.auditoria import servicos_auditoria_lote as lote
from Src.Services.comparacao.diferencas_auditoria import comparar_com_gravado
from Src.Services.auditoria.servicos_auditoria import XMLItem


def _item(numero, valor, status="OK", empresa="Petrobras"):
    return XMLItem(empresa, "NF-e", numero, valor, valor * 0.12, 0.12, 0, 0, 0, status, 0, f"{empresa}/{numero}.xml")


def test_diferenca_acima_da_tolerancia_gera_erro():
    gravado = [_item("10", 1000.0)]
    novo = [_item("10", 900.0, status="OCR")]
    d = comparar_com_gravado(novo, lote.itens_para_banco(gravado))
    erros = erros_ciclo.erros_diferencas_auditoria(d, "Jan/2026")
    assert erros and "Jan/2026" in erros[0] and "R$" in erros[0]
    assert any("OCR" in e for e in erros)


def test_sem_diferenca_sem_erro():
    itens = [_item("10", 1000.0)]
    d = comparar_com_gravado(itens, lote.itens_para_banco(itens))
    assert erros_ciclo.erros_diferencas_auditoria(d, "Jan/2026") == []


def test_ocr_suspeito_e_nota_xml_normal():
    assert erros_ciclo.erros_notas_ocr([_item("0", 500.0, status="OCR")], "Jan/2026")
    assert erros_ciclo.erros_notas_ocr([_item("7", 0.0, status="OCR")])
    assert erros_ciclo.erros_notas_ocr([_item("7", 500.0, status="OCR"), _item("0", 0.0)]) == []


def test_prova_real_cgf_e_pmpv_ausente():
    base = {"periodo": "Jan/2026", "tem_resumo": True, "pmpv": None, "volume_confere": True, "cgf_confere": False}
    assert "PMPV" in erros_ciclo.erros_prova_real_cgf(base)[0]
    ruim = {**base, "pmpv": 1.0, "cgf_gravado": 1000.0, "cgf_calculado": 900.0}
    assert "Jan/2026" in erros_ciclo.erros_prova_real_cgf(ruim)[0]
    assert erros_ciclo.erros_prova_real_cgf({**ruim, "tem_resumo": False}) == []


def test_prova_real_rp_ret_so_erra_quando_nao_confere():
    ok = {"periodo": "Jan/2026", "rp_gravado": 100.0, "rp_calculado": 100.0, "confere": True}
    assert erros_ciclo.erros_prova_real_rp(ok) == []
    assert "RP" in erros_ciclo.erros_prova_real_rp({**ok, "rp_calculado": 50.0, "confere": False})[0]
    ret = {"periodo": "Jan/2026", "ret_gravado": 100.0, "ret_calculado": 80.0, "confere": False}
    assert "RET" in erros_ciclo.erros_prova_real_ret(ret)[0]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "erros_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def test_rotas_devolvem_campo_erros(client):
    r = client.get("/api/cgf/prova-real", params={"periodo": "Jan/2026"})
    assert r.status_code == 200 and r.json()["erros"] == []
    r = client.post("/api/cgf/calcular-rs", json={"periodo": "Jan/2026", "volume_final": 100})
    assert r.status_code == 200 and "PMPV ausente" in r.json()["erros"][0]
    for rota in ("auditoria", "conciliacao", "ret", "rpv"):
        r = client.get(f"/api/{rota}/prova-real", params={"periodo": "Jan/2026"})
        assert r.status_code == 200 and r.json()["erros"] == [], rota
