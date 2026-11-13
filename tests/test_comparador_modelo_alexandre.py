from __future__ import annotations

from datetime import datetime

import openpyxl
import pandas as pd
import pytest

from Src.Services.comparacao import comparador_modelo_alexandre as alex
from Src.Services import servicos_auditoria_lote as lote
from Src.Services.comparacao.comparador_conta_grafica import ComparadorContaGrafica, _periodo_de_data
from Src.Services.servicos_auditoria import XMLItem


def _nf(empresa, numero, valor, aliq=0.12, volume=1000, caminho="nf.xml", tipo="NF-e"):
    return XMLItem(empresa, tipo, numero, valor, valor * aliq, aliq, 0.0, 0.0, volume, "OK", volume, caminho)


def _s_trib(valor, aliq=0.12):
    return valor * (1 - aliq) * (1 - 0.0925)


@pytest.fixture
def planilha(tmp_path):
    """Modelo Alexandre mínimo: bloco JUN-2026 na aba de NFs e CGR mensal
    (Jun e Jul) na aba Conta Gráfica."""
    wb = openpyxl.Workbook()
    wb.active.title = "legenda de dados"
    ws = wb.create_sheet("Custo do Gás Realizado - NFs")
    ws.append(["MÊS", "JUN-2026", 999, None, 123])
    ws.append(["Supridor", "Nota Fiscal", "Vol m³", "Compra R$ c/tributos", "Compra R$ s/tributos", "Custo", "ICMS"])
    ws.append(["Petrobras", "12722-6", 1000, 1000.0, _s_trib(1000.0), 2.0, 0.12])
    ws.append(["Petrobras", "6540-4", 2000, 2000.0, _s_trib(2000.0) + 50, 2.0, 0.12])   # valor diverge
    ws.append(["Petrobras", None, None, None, 0, 0, None])                             # linha vazia
    ws.append(["3R BRAVA", "706-2", 500, 500.0, _s_trib(500.0), 2.0, 0.12])
    ws.append(["Galp", "1612-2", 70, 300.0, _s_trib(300.0), 2.0, 0.12])                # só na planilha
    ws.append(["TAG", 15550, None, 400.0, _s_trib(400.0), None, 0.12])
    ws.append(["3R BRAVA", None, 5795000, None, 10650887.6, 1.83])                     # resumo por supridor
    ws.append(["TOTAL - GERAL", None, 1, None, 2])
    conta = wb.create_sheet("Conta Gráfica")
    conta.append(["CONTA GRÁFICA"])
    conta.append(["DADOS", "UNIDADE", datetime(2026, 5, 1), datetime(2026, 6, 1), datetime(2026, 7, 1)])
    conta.append(["PMPV", "R$/m³", 2.0, 2.0, 2.0])
    conta.append(["CGR", "R$", 10.0, 3000.0, 5000.0])
    caminho = tmp_path / "Novo modelo Alexandre.xlsx"
    wb.save(caminho)
    return str(caminho)


class TestLeitura:
    def test_le_blocos_e_ignora_resumo(self, planilha):
        modelo = alex.ler_modelo(planilha)
        notas = modelo.notas["Jun/2026"]
        assert [(n.empresa, n.numero_normalizado) for n in notas] == [
            ("Petrobras", "12722"), ("Petrobras", "6540"), ("Brava", "706"), ("Galp", "1612"), ("TAG", "15550"),
        ]

    def test_le_cgr_da_aba_conta_grafica(self, planilha):
        modelo = alex.ler_modelo(planilha)
        assert modelo.cgr_conta_grafica["Jul/2026"] == 5000.0

    def test_outra_planilha_nao_e_modelo_alexandre(self, tmp_path):
        caminho = tmp_path / "outra.xlsx"
        pd.DataFrame({"Nota": [1, 2]}).to_excel(caminho, index=False)
        assert alex.ler_modelo(str(caminho)) is None

    @pytest.mark.parametrize("nome,esperado", [
        ("3R BRAVA", "Brava"), ("Eneva (Petrolina)", "Eneva"), ("GNL Link", "GNLink"), ("GNlink", "GNLink"),
        ("Petrorecôncavo", "Petrorecôncavo"), ("Petroreconcavo", "Petrorecôncavo"), ("GNC Mastergás", "Mastergás"),
        ("Orizon Biomentano", "Orizon"), ("GALP", "Galp"),
    ])
    def test_supridor_canonico(self, nome, esperado):
        assert alex.supridor_canonico(nome) == esperado


class TestComparacao:
    def _itens(self):
        return [
            _nf("Petrobras", "12722", 1000.0),
            _nf("Petrobras", "6540", 2000.0, volume=2000),
            _nf("Brava", "706", 500.0, volume=500),
            _nf("TAG", "15550", 400.0, volume=0, tipo="CT-e"),
            _nf("Eneva", "77", 800.0),                                   # só na auditoria
            _nf("Transpetro", "999", 50.0, tipo="CT-e"),                 # frete fora do CGR: ignorado
        ]

    def test_aponta_cada_tipo_de_divergencia(self, planilha):
        r = lote.comparar_com_planilha(self._itens(), planilha, "Jun/2026")
        assert r.modelo == "alexandre"
        assert r.qtd_em_ambas == 4
        assert [d["numero"] for d in r.divergencias_valor] == ["6540"]
        assert r.divergencias_valor[0]["motivos"] == ["CGR (s/ tributos)"]
        assert r.divergencias_valor[0]["diferenca_cgr"] == pytest.approx(-50, abs=0.01)
        assert [n["numero"] for n in r.notas_apenas_nossa] == ["77"]
        assert [n["numero"] for n in r.notas_apenas_conta_grafica] == ["1612-2"]

    def test_resumo_por_supridor(self, planilha):
        r = lote.comparar_com_planilha(self._itens(), planilha, "Jun/2026")
        por = {e["empresa"]: e for e in r.por_empresa}
        assert por["Brava"]["confere"] and por["TAG"]["confere"]
        assert not por["Petrobras"]["confere"]
        assert por["Galp"]["qtd_auditoria"] == 0 and por["Galp"]["qtd_planilha"] == 1

    def test_devolucao_entra_negativa(self, planilha):
        itens = [_nf("Brava", "706", 500.0, volume=500, caminho="Brava/Devolução - 706.xml")]
        r = lote.comparar_com_planilha(itens, planilha, "Jun/2026")
        d = r.divergencias_valor[0]
        assert d["cgr_auditoria"] == pytest.approx(-_s_trib(500.0), abs=0.01)

    def test_mes_sem_notas_compara_so_o_total(self, planilha):
        r = lote.comparar_com_planilha([_nf("Petrobras", "1", 1000.0)], planilha, "Jul/2026")
        assert r.notas_mes_na_planilha is False
        assert r.notas_apenas_nossa == [] and r.divergencias_valor == []
        assert r.cgr_planilha_conta_grafica == 5000.0
        assert any(a.startswith("CGR DIVERGENTE") for a in r.avisos)

    def test_sugere_mes_quando_periodo_errado(self, planilha, tmp_path):
        wb = openpyxl.load_workbook(planilha)
        ws = wb["Custo do Gás Realizado - NFs"]
        ws.append(["MÊS", "MAI-2026"])
        ws.append(["Supridor", "Nota Fiscal"])
        ws.append(["Eneva (Petrolina)", "77-1", 1000, 800.0, _s_trib(800.0), 2.0, 0.12])
        wb.save(planilha)
        r = lote.comparar_com_planilha([_nf("Eneva", "77", 800.0)], planilha, "Jun/2026")
        assert any("Mês provavelmente errado" in a and "Mai/2026" in a for a in r.avisos)

    def test_total_que_bate(self, planilha):
        itens = [_nf("Petrobras", "1", 5000.0 / ((1 - 0.12) * (1 - 0.0925)))]
        r = lote.comparar_com_planilha(itens, planilha, "Jul/2026")
        assert any(a.startswith("CGR confere") for a in r.avisos)


class TestRegressaoAno1900:
    """Planilha com alíquotas (0,12) e volumes fazia o comparador genérico
    ler números como datas de 1900 e derrubar a auditoria com HTTP 422."""

    @pytest.mark.parametrize("valor", [0.12, 0.0165, 143365, 2.349])
    def test_numero_que_nao_e_data(self, valor):
        assert _periodo_de_data(valor) == ""

    def test_comparador_generico_nao_quebra(self):
        df = pd.DataFrame({
            "Supridor": ["Petrobras", "Petrobras"], "Nota": ["3564-28", "3565-28"],
            "ICMS": [0.12, 0.07], "Data": [0.0165, 0.076], "__sheet_name__": ["NFs", "NFs"],
        })
        r = ComparadorContaGrafica.comparar([_nf("Petrobras", "3564", 1.0)], df, "Jun/2026")
        assert r.periodo == "Jun/2026"
