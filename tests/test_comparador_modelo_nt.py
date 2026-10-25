"""Comparação com a NT (aba "Q5 - SCG - Anexo A"): por supridor, com o porquê das diferenças."""
from __future__ import annotations

import openpyxl
import pytest

from Src.Services import comparador_modelo_nt as nt
from Src.Services.servicos_auditoria import XMLItem


def _item(empresa="Petrobras", tipo="NF-e", numero="1", valor=1000.0, taxa=0.12, vol=100.0,
          caminho="Petrobras/nf.xml", status="OK"):
    return XMLItem(empresa, tipo, numero, valor, valor * taxa, taxa, 0, 0, 0, status, vol, caminho)


def _cgr(valor, taxa=0.12):
    from Src.Services.servicos_auditoria import RegrasAuditoria
    return RegrasAuditoria.calcular_s_tributos(valor, taxa)


def _planilha(tmp_path, blocos: dict[str, list[tuple]]):
    """blocos: {'07/2026': [(fornecedor, volume, cgr), ...]} — com colunas vazias entre os campos, como na NT real."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Q5 - SCG - Anexo A"
    linha = 1
    for periodo, fornecedores in blocos.items():
        ws.cell(linha, 5, periodo)
        ws.cell(linha, 6, "VF Líquido")
        ws.cell(linha + 1, 5, "Fornecedor")
        ws.cell(linha + 1, 7, "Volume Adiquirido aos Fornecedores")
        ws.cell(linha + 1, 8, "Custo do Gás Realizado\n CGR")
        for k, (nome, vol, cgr) in enumerate(fornecedores, start=2):
            ws.cell(linha + k, 5, nome)
            ws.cell(linha + k, 7, vol)
            ws.cell(linha + k, 8, cgr)
        ws.cell(linha + len(fornecedores) + 2, 5, "TOTAL - GERAL")
        ws.cell(linha + len(fornecedores) + 2, 7, 999999999)
        linha += len(fornecedores) + 6
    destino = tmp_path / "NT_teste.xlsx"
    wb.save(destino)
    return str(destino)


def test_nao_e_nt_devolve_none(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.title = "Outra"
    wb.save(tmp_path / "x.xlsx")
    assert nt.ler_modelo(str(tmp_path / "x.xlsx")) is None


def test_le_blocos_e_ignora_linha_de_total(tmp_path):
    m = nt.ler_modelo(_planilha(tmp_path, {"07/2026": [("Petrobras", 100, 1000.0), ("Eneva (Garanhuns)", 10, 50.0), ("Eneva (Petrolina)", 20, 70.0)]}))
    assert m.periodos == ["Jul/2026"]
    assert m.blocos["Jul/2026"]["Eneva"].volume == 30 and m.blocos["Jul/2026"]["Eneva"].cgr == 120.0
    assert "TOTAL - GERAL" not in m.blocos["Jul/2026"]


def test_tudo_confere(tmp_path):
    itens = [_item(valor=1000.0, vol=100.0)]
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 100, round(_cgr(1000.0), 2))]})
    r = nt.comparar(itens, nt.ler_modelo(pl), "Jul/2026")
    assert r.modelo == "nt" and all(e["confere"] for e in r.por_empresa)
    assert any(a.startswith("CGR confere") for a in r.avisos)


def test_nota_extra_nas_notas_explica_a_diferenca(tmp_path):
    itens = [_item(numero="1", valor=1000.0), _item(numero="2", valor=5000.0)]
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 100, round(_cgr(1000.0), 2))]})
    [e] = nt.comparar(itens, nt.ler_modelo(pl), "Jul/2026").por_empresa
    assert not e["confere"]
    assert any("NF-e 2" in t and "sozinha explica" in t for t in e["explicacoes"])


def test_supridor_ausente_na_nt_e_nas_notas(tmp_path):
    itens = [_item(empresa="GALP", caminho="GALP/n.xml")]
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 100, 5000.0)]})
    por = {e["empresa"]: e for e in nt.comparar(itens, nt.ler_modelo(pl), "Jul/2026").por_empresa}
    assert "não tem Galp" in por["Galp"]["explicacoes"][0]
    assert "nenhuma nota dele entrou" in por["Petrobras"]["explicacoes"][0]


def test_so_o_volume_diverge_e_aponta_mes_da_nt(tmp_path):
    itens = [_item(valor=1000.0, vol=88000.0)]
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 64000, round(_cgr(1000.0), 2))],
                              "08/2026": [("Petrobras", 88000, 9999.0)]})
    [e] = nt.comparar(itens, nt.ler_modelo(pl), "Jul/2026").por_empresa
    assert not e["confere"] and abs(e["diferenca"]) <= 1 and e["diferenca_volume"] == 24000
    texto = " ".join(e["explicacoes"])
    assert "só o volume" in texto and "Ago/2026" in texto


def test_aliquota_unica_explica_a_nt(tmp_path):
    itens = [_item(numero="1", valor=1000.0, taxa=0.07), _item(numero="2", valor=2000.0, taxa=0.12)]
    alvo = round(_cgr(1000.0, 0.12) + _cgr(2000.0, 0.12), 2)
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 200, alvo)]})
    [e] = nt.comparar(itens, nt.ler_modelo(pl), "Jul/2026").por_empresa
    assert any("alíquota de 12%" in t for t in e["explicacoes"])


def test_nt_maior_sem_causa_isolada_diz_que_nao_achou(tmp_path):
    itens = [_item(valor=1000.0, vol=100.0)]
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 100, round(_cgr(1000.0), 2) + 777.77)]})
    [e] = nt.comparar(itens, nt.ler_modelo(pl), "Jul/2026").por_empresa
    assert any("nenhuma nota ou devolução isolada" in t for t in e["explicacoes"])


def test_mes_sem_bloco_na_nt(tmp_path):
    pl = _planilha(tmp_path, {"07/2026": [("Petrobras", 100, 1.0)]})
    r = nt.comparar([_item()], nt.ler_modelo(pl), "Out/2026")
    assert r.por_empresa == [] and "não tem o bloco de Out/2026" in r.avisos[0]
