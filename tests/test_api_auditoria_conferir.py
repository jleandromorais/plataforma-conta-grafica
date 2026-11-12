"""Conferência da planilha da Conta Gráfica (POST /auditoria/planilha/conferir) e o campo
`notas_em_ambas` da comparação (as notas que batem nos dois lados).

Planilhas sintéticas, montadas aqui com openpyxl: nenhum valor real."""
from __future__ import annotations

from datetime import datetime

import openpyxl
import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_auditoria_lote as lote
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem

CABECALHO = ["Mês", "Supridor", "Nota Fiscal", "Vol m³", "Compra R$ c/tributos", "Compra R$ s/tributos", "Custo", "ICMS", "PIS"]
TRIMESTRE = "Jul/2026,Ago/2026,Set/2026"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cgr(valor, taxa=0.12):
    return round(RegrasAuditoria.calcular_s_tributos(valor, taxa), 2)


def _item(empresa="TAG", numero="1", valor=1000.0, taxa=0.12, tipo="CT-e"):
    return XMLItem(empresa, tipo, numero, valor, valor * taxa, taxa, 0, 0, 0, "OK", 0, f"{empresa}/x.xml")


def _planilha_apuracao(destino, meses=((7, "Jul26"), (8, "Ago26"), (9, "Set26")), valores=(1000.0, 2000.0)):
    """Modelo "Conta Gráfica e Apuração de Custos": uma aba por mês, uma linha por nota."""
    wb = openpyxl.Workbook()
    wb.active.title = "Capa"
    for mes, aba in meses:
        ws = wb.create_sheet(aba)
        ws.append(["RELATÓRIO MENSAL"])
        ws.append(CABECALHO)
        for numero, valor in zip((f"{mes}01", f"{mes}02"), valores):
            ws.append([datetime(2026, mes, 1), "TAG", numero, 0, valor, _cgr(valor), None, 0.12, 0.02])
    wb.save(destino)
    return destino


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "conferir_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _conferir(client, conteudo: bytes, nome="conta grafica.xlsx", meses=TRIMESTRE):
    resp = client.post("/api/auditoria/planilha/conferir",
                       files={"planilha": (nome, conteudo, XLSX)}, data={"meses": meses})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── POST /auditoria/planilha/conferir ────────────────────────────────────────

def test_planilha_boa_com_os_3_meses(client, tmp_path):
    r = _conferir(client, _planilha_apuracao(tmp_path / "p.xlsx").read_bytes())
    assert r["ok"] is True and r["aviso"] is None
    assert (r["modelo"], r["modelo_rotulo"]) == ("por_nota", "Conta Gráfica e Apuração de Custos")
    assert r["meses"] == [
        {"periodo": "Jul/2026", "tem": True, "abas": ["Jul26"], "qtd_notas": 2},
        {"periodo": "Ago/2026", "tem": True, "abas": ["Ago26"], "qtd_notas": 2},
        {"periodo": "Set/2026", "tem": True, "abas": ["Set26"], "qtd_notas": 2},
    ]


def test_planilha_sem_um_mes(client, tmp_path):
    caminho = _planilha_apuracao(tmp_path / "p.xlsx", meses=((7, "Jul26"), (8, "Ago26")))
    r = _conferir(client, caminho.read_bytes())
    assert r["ok"] is True
    assert [(m["periodo"], m["tem"]) for m in r["meses"]] == [("Jul/2026", True), ("Ago/2026", True), ("Set/2026", False)]
    assert r["meses"][2] == {"periodo": "Set/2026", "tem": False, "abas": [], "qtd_notas": None}
    assert "Set/2026" in r["aviso"]


def test_arquivo_que_nao_e_xlsx(client):
    r = _conferir(client, b"isto nao e uma planilha")
    assert r["ok"] is False and r["modelo"] is None
    assert r["aviso"].startswith("Não consegui abrir esta planilha")
    assert [m["tem"] for m in r["meses"]] == [False, False, False]


def test_xlsx_de_outra_coisa(client, tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Plan1"
    wb.active.append(["Nome", "Telefone"])
    wb.active.append(["Fulano", "1234"])
    wb.save(tmp_path / "outra.xlsx")
    r = _conferir(client, (tmp_path / "outra.xlsx").read_bytes())
    assert r["ok"] is False and r["modelo"] == "generico"
    assert "não parece a planilha da Conta Gráfica" in r["aviso"]


def test_modelo_alexandre_conta_o_mes_so_com_o_cgr(client, tmp_path):
    """Mês sem notas na aba de NFs, mas com CGR na aba Conta Gráfica: dá para comparar o total."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Custo do Gás Realizado - NFs"
    ws.append(["MÊS", "JUL-2026"])
    ws.append(["Supridor", "Nota Fiscal", "Vol m³", "Compra R$ c/tributos", "Compra R$ s/tributos", "Custo", "ICMS"])
    ws.append(["TAG", "701", 0, 1000.0, _cgr(1000.0), None, 0.12])
    conta = wb.create_sheet("Conta Gráfica")
    conta.append(["DADOS", "UNIDADE", datetime(2026, 7, 1), datetime(2026, 8, 1), datetime(2026, 9, 1)])
    conta.append(["CGR", "R$", 10.0, 20.0, None])
    wb.save(tmp_path / "alex.xlsx")
    r = _conferir(client, (tmp_path / "alex.xlsx").read_bytes())
    assert (r["ok"], r["modelo"], r["modelo_rotulo"]) == (True, "por_nota", "Modelo Alexandre")
    assert r["meses"] == [
        {"periodo": "Jul/2026", "tem": True, "abas": ["Custo do Gás Realizado - NFs", "Conta Gráfica"], "qtd_notas": 1},
        {"periodo": "Ago/2026", "tem": True, "abas": ["Conta Gráfica"], "qtd_notas": None},
        {"periodo": "Set/2026", "tem": False, "abas": [], "qtd_notas": None},
    ]


def test_meses_invalidos_e_422(client, tmp_path):
    resp = client.post("/api/auditoria/planilha/conferir",
                       files={"planilha": ("p.xlsx", _planilha_apuracao(tmp_path / "p.xlsx").read_bytes(), XLSX)},
                       data={"meses": "Julho"})
    assert resp.status_code == 422


# ── notas_em_ambas na comparação ─────────────────────────────────────────────

def test_notas_em_ambas_lista_as_que_batem(tmp_path):
    caminho = str(_planilha_apuracao(tmp_path / "p.xlsx"))
    itens = [_item(numero="701", valor=1000.0),            # bate
             _item(numero="702", valor=2500.0),            # está nas duas, mas o valor difere
             _item(numero="799", valor=10.0)]              # só nas notas
    r = lote.comparar_com_planilha(itens, caminho, "Jul/2026")
    assert r.qtd_em_ambas == 2 and len(r.divergencias_valor) == 1
    assert r.notas_em_ambas == [{"empresa": "TAG", "tipo": "CT-e", "numero": "701", "linha_excel": 3,
                                 "cgr_liquido": _cgr(1000.0), "cgr_planilha": _cgr(1000.0)}]


def test_notas_em_ambas_no_comparador_generico(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Jul-26"
    ws.append(["Nota Fiscal", "Competência", "Valor"])
    ws.append([123456, datetime(2026, 7, 1), 1000.0])
    ws.append([654321, datetime(2026, 7, 1), 500.0])
    wb.save(tmp_path / "g.xlsx")
    r = lote.comparar_com_planilha([_item(numero="123456", tipo="NF-e")], str(tmp_path / "g.xlsx"), "Jul/2026")
    assert r.modelo == "generico"
    [n] = r.notas_em_ambas
    assert (n["numero"], n["linha_excel"], n["cgr_planilha"]) == ("123456", 2, None)


def test_processar_devolve_notas_em_ambas(client, tmp_path):
    from tests.test_servicos_auditoria import NFE_XML

    xml = NFE_XML.replace("<nNF>123456</nNF>", "<nNF>701</nNF>")
    planilha = _planilha_apuracao(tmp_path / "p.xlsx", valores=(10000.0, 2000.0)).read_bytes()
    resp = client.post("/api/auditoria/processar", data={"periodo": "Jul/2026"}, files=[
        ("arquivos", ("TAG/nf.xml", xml.encode(), "text/xml")),
        ("planilha", ("conta grafica.xlsx", planilha, XLSX)),
    ])
    assert resp.status_code == 200, resp.text
    comp = resp.json()["comparacao"]
    assert comp["qtd_em_ambas"] == 1
    assert comp["notas_em_ambas"] == [{"empresa": "TAG", "tipo": "NF-e", "numero": "701", "linha_excel": 3,
                                       "cgr_liquido": _cgr(10000.0), "cgr_planilha": _cgr(10000.0)}]
