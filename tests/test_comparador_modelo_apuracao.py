"""Planilha "Conta Gráfica e Apuração de Custos" (uma aba por mês) + registro de modelos."""
from __future__ import annotations

from datetime import datetime

import openpyxl
import pytest

from Src.Services import comparacao_registro as registro
from Src.Services import comparador_modelo_apuracao as ap
from Src.Services import servicos_auditoria_lote as lote
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem

CABECALHO = ["Mês", "Supridor", "Nota Fiscal", "Vol m³", "Compra R$ c/tributos", "Compra R$ s/tributos", "Custo", "ICMS", "PIS"]


def _cgr(valor, taxa=0.12):
    return round(RegrasAuditoria.calcular_s_tributos(valor, taxa), 2)


def _item(empresa="TAG", numero="1", valor=1000.0, taxa=0.12, vol=0.0, tipo="CT-e", status="OK", caminho="TAG/x.xml"):
    return XMLItem(empresa, tipo, numero, valor, valor * taxa, taxa, 0, 0, 0, status, vol, caminho)


def _nota_planilha(ws, supridor, numero, valor, vol=0, taxa=0.12, mes=datetime(2026, 7, 1)):
    ws.append([mes, supridor, numero, vol, valor, _cgr(valor, taxa), None, taxa, 0.02])


@pytest.fixture
def planilha(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Capa"
    ws = wb.create_sheet("Jul26")
    ws.append(["RELATÓRIO MENSAL"])
    ws.append([])
    ws.append(CABECALHO)
    _nota_planilha(ws, "TAG", "4491", 1000.0)
    _nota_planilha(ws, "TAG", "550499", 5000.0, taxa=0.0)       # só na planilha
    _nota_planilha(ws, "GNL Link", "000.271.226-1", 2000.0)     # na auditoria o OCR leu o número como "0"
    ws.append([datetime(2026, 7, 1), "TAG", None, None, None, 0])   # linha de reserva (zeros)
    ws2 = wb.create_sheet("Ago26")
    ws2.append(CABECALHO)
    _nota_planilha(ws2, "TAG", "9999", 100.0, mes=datetime(2026, 8, 1))
    destino = tmp_path / "apuracao.xlsx"
    wb.save(destino)
    return str(destino)


def test_le_uma_aba_por_mes_e_ignora_linha_de_reserva(planilha):
    m = ap.ler_modelo(planilha)
    assert set(m.notas) == {"Jul/2026", "Ago/2026"}
    assert [n.numero for n in m.notas["Jul/2026"]] == ["4491", "550499", "000.271.226-1"]
    assert m.notas["Jul/2026"][0].aliquota_icms == 0.12


def test_planilha_de_outro_layout_nao_e_reconhecida(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Jul26"
    wb.active.append(["a", "b"])
    wb.save(tmp_path / "x.xlsx")
    assert ap.ler_modelo(str(tmp_path / "x.xlsx")) is None


def test_aponta_a_nota_que_so_esta_na_planilha_e_explica_a_diferenca(planilha):
    itens = [_item(numero="4491", valor=1000.0), _item(empresa="GNLink", tipo="NF-e", numero="0", valor=2000.0,
                                                      status="OCR", caminho="GNLINK/x.pdf")]
    r = lote.comparar_com_planilha(itens, planilha, "Jul/2026")
    assert (r.modelo, r.tipo) == ("apuracao", "por_nota")
    assert [n["numero"] for n in r.notas_apenas_conta_grafica] == ["550499"]
    assert r.notas_apenas_nossa == []
    tag = next(e for e in r.por_empresa if e["empresa"] == "TAG")
    assert not tag["confere"]
    assert "550499" in tag["explicacoes"][0] and "NÃO vieram nos arquivos" in tag["explicacoes"][0]
    assert any("explicam toda a diferença" in t for t in tag["explicacoes"])


def test_numero_lido_como_zero_pelo_ocr_casa_pelo_valor(planilha):
    itens = [_item(numero="4491", valor=1000.0), _item(empresa="GNLink", tipo="NF-e", numero="0", valor=2000.0,
                                                      status="OCR", caminho="GNLINK/x.pdf")]
    r = lote.comparar_com_planilha(itens, planilha, "Jul/2026")
    assert r.qtd_em_ambas == 2   # a nota "0" casou com a 000.271.226-1
    assert any("casada pelo valor com a nota 000.271.226-1" in a for a in r.avisos)


def test_o_mes_escolhido_define_a_aba(planilha):
    itens = [_item(numero="9999", valor=100.0)]
    jul = lote.comparar_com_planilha(itens, planilha, "Jul/2026")
    ago = lote.comparar_com_planilha(itens, planilha, "Ago/2026")
    assert ago.qtd_em_ambas == 1 and ago.notas_apenas_conta_grafica == []
    assert jul.qtd_em_ambas == 0 and len(jul.notas_apenas_conta_grafica) == 3
    assert any("Mês provavelmente errado" in a and "Ago/2026" in a for a in jul.avisos)


def test_valor_diferente_vem_com_explicacao_por_nota(planilha):
    itens = [_item(numero="4491", valor=1500.0)]
    r = lote.comparar_com_planilha(itens, planilha, "Jul/2026")
    [d] = r.divergencias_valor
    assert "CGR" in d["explicacao"] and "valor c/ tributos" in d["explicacao"]


def test_registro_ordem_e_tipos():
    assert [m.nome for m in registro.MODELOS] == ["alexandre", "apuracao", "nt"]
    assert all(m.tipo in registro.TIPOS for m in registro.MODELOS)
