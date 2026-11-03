"""Onde o CGR processado difere do gravado (Src/Services/diferencas_auditoria.py)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_auditoria_lote as lote
from Src.Services.diferencas_auditoria import comparar_com_gravado
from Src.Services.servicos_auditoria import XMLItem


def _item(empresa, numero, valor, tipo="NF-e", taxa=0.12, status="OK", caminho=None):
    return XMLItem(empresa, tipo, numero, valor, valor * taxa, taxa, 0, 0, 0, status, 0, caminho or f"{empresa}/{numero}.xml")


def _gravados(itens):
    return lote.itens_para_banco(itens)


def test_sem_diferenca():
    itens = [_item("Petrobras", "10", 1000.0), _item("TAG", "5", 200.0, tipo="CT-e")]
    r = comparar_com_gravado(itens, _gravados(itens))
    assert r["diferenca"] == pytest.approx(0.0)
    assert r["por_empresa"] == [] and r["notas"] == []


def test_nota_faltando_e_valor_diferente_por_empresa():
    gravado = [_item("Petrobras", "10", 1000.0), _item("Petrobras", "11", 500.0), _item("TAG", "5", 200.0, tipo="CT-e")]
    novo = [_item("PETROBRAS S.A.", "000010", 900.0, status="OCR"), _item("TAG", "5", 200.0, tipo="CT-e")]
    r = comparar_com_gravado(novo, _gravados(gravado))
    s = lambda v: lote.cgr_liquido_item(_item("x", "1", v))  # noqa: E731 — CGR de uma nota de valor v
    assert r["diferenca"] == pytest.approx(s(900) - s(1000) - s(500))
    assert [e["empresa"] for e in r["por_empresa"]] == ["Petrobras"]
    notas = {n["numero"]: n for n in r["notas"]}
    assert notas["11"]["situacao"] == "so_no_gravado"
    assert notas["10"]["situacao"] == "valor_diferente" and notas["10"]["ocr"] is True
    # a maior diferença vem primeiro
    assert r["notas"][0]["numero"] == "11"


def test_avisa_quando_notas_gravadas_nao_somam_o_cgr_gravado():
    gravado = [_item("Petrobras", "10", 1000.0)]
    r = comparar_com_gravado(gravado, _gravados(gravado), cgr_gravado=1.0)
    assert "regra antiga" in r["resumo"][0]
    assert comparar_com_gravado(gravado, _gravados(gravado), cgr_gravado=r["cgr_gravado_notas"])["resumo"] == ["As notas batem com as gravadas."]


def test_nota_sem_numero_casa_pelo_valor():
    gravado = [_item("GNLink", "0", 100.0, caminho="GNLink/Devolução.pdf")]
    novo = [_item("GNLink", "N/A", 100.0, caminho="GNLink/Devolução.pdf")]
    assert comparar_com_gravado(novo, _gravados(gravado))["notas"] == []


def test_frete_fora_do_cgr_nao_conta():
    gravado = [_item("Petrobras", "10", 1000.0)]
    novo = gravado + [_item("Transportadora X", "7", 300.0, tipo="CT-e")]
    assert comparar_com_gravado(novo, _gravados(gravado))["notas"] == []


def test_sem_notas_gravadas_mostra_ocr_e_empresas():
    novo = [_item("Petrobras", "10", 1000.0, status="OCR"), _item("TAG", "5", 200.0, tipo="CT-e")]
    r = comparar_com_gravado(novo, [])
    assert r["tem_notas_gravadas"] is False
    assert [n["numero"] for n in r["notas"]] == ["10"] and r["notas"][0]["ocr"] is True
    assert {e["empresa"] for e in r["por_empresa"]} == {"Petrobras", "TAG"}
    assert "OCR" in " ".join(r["resumo"])


def test_endpoint_compara_com_o_que_esta_gravado(tmp_path, monkeypatch):
    banco = tmp_path / "t.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.auth import usuario_atual
    from Src.api.main import app
    app.dependency_overrides[usuario_atual] = lambda: {"email": "t"}
    try:
        with TestClient(app) as c:
            gravado = [_item("Petrobras", "10", 1000.0), _item("Petrobras", "11", 500.0)]
            with DatabasePMPV() as db:
                db.salvar_auditoria_itens("Jul/2026", lote.itens_para_banco(gravado))
            novo = [{"empresa": "Petrobras", "tipo": "NF-e", "numero": "10", "valor_total": 1000.0, "icms": 120.0,
                     "icms_taxa": 0.12, "pis": 0, "cofins": 0, "volume": 0, "status": "OK", "volume_total": 0,
                     "caminho": "Petrobras/10.xml", "cgr_liquido": 0, "integra_cgr": True, "devolucao": False}]
            r = c.post("/api/auditoria/diferencas", json={"periodo": "Jul/2026", "itens": novo})
            assert r.status_code == 200, r.text
            j = r.json()
            assert j["tem_notas_gravadas"] is True
            assert [n["numero"] for n in j["notas"]] == ["11"]
            assert j["resumo"]
    finally:
        app.dependency_overrides.pop(usuario_atual, None)
