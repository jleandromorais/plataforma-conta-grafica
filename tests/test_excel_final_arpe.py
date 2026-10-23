"""Excel Final no visual ARPE: abas de resultado no formato dos Quadros da NT
(SCG, SR, PR, PV) e só as abas que o usuário usa (sem Dashboard/Resumo)."""
import openpyxl
import pytest

from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters.excel_sheets import arpe, sheet_resultados_nt as nt

MESES = ["Jan/2026", "Fev/2026", "Mar/2026"]
SR = [
    {"mes": "Jan/2026", "vp": 48143000, "vf": 41805735.80, "diferenca": 6337264.20, "pr": -0.021,
     "sr_parcela": -133082.55, "selic_mensal": 3.411174, "sr_selic": -137622.23},
    {"mes": "Fev/2026", "vp": 42224000, "vf": 39940612.96, "diferenca": 2283387.04, "pr": -0.0321,
     "sr_parcela": -73296.72, "selic_mensal": 2.221160, "sr_selic": -74924.76},
    {"mes": "Mar/2026", "vp": 46748000, "vf": 44979282.33, "diferenca": 1768717.67, "pr": -0.0321,
     "sr_parcela": -56775.84, "selic_mensal": 1.212054, "sr_selic": -57463.99},
]


def _valores(ws):
    return {str(r[0]).strip(): r[1:] for r in ws.iter_rows(values_only=True) if r and r[0]}


def test_sr_quadro6_total_igual_planilha():
    wb = openpyxl.Workbook()
    nt.sheet_sr(wb, MESES, SR)
    linhas = _valores(wb["SR"])
    assert linhas["Saldo Remanescente (SELIC)"][1:4] == (-137622.23, -74924.76, -57463.99)
    assert linhas["Total do trimestre"][1] == pytest.approx(-270010.98)


def test_scg_com_selic_usa_a_selic_do_sr():
    wb = openpyxl.Workbook()
    scg = [{"periodo": "Jan/2026", "scg": -458694.16}, {"periodo": "Fev/2026", "scg": 3318892.44},
           {"periodo": "Mar/2026", "scg": -2634822.30}]
    nt.sheet_scg(wb, MESES, scg, {r["mes"]: r["selic_mensal"] for r in SR})
    total = _valores(wb["SCG"])["SCG com SELIC"][-1]
    assert total == pytest.approx(251511.57, abs=0.05)


def test_pr_quadro7():
    wb = openpyxl.Workbook()
    nt.sheet_pr(wb, {"meses_pr": ["Mai/2026", "Jun/2026", "Jul/2026"], "meses_apurados": MESES,
                     "scg_selic": 251511.57, "meses": [{"periodo": m["mes"], "sr": m["sr_selic"]} for m in SR],
                     "saldo_total": -18499.41, "vp": 133749000.0, "pr": -0.0001, "pendencias": []})
    assert _valores(wb["PR"])["Parcela de Recuperação — PR"][1] == -0.0001


def test_tema_tira_emoji_e_fundo_escuro():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "📊 PMPV"
    c = ws.cell(1, 1, "🔍 Título")
    c.fill = openpyxl.styles.PatternFill("solid", fgColor="0F1A2E")
    arpe.aplicar_tema(ws)
    assert ws.title == "PMPV"
    assert c.value == "Título"
    assert c.fill.fgColor.rgb.endswith(arpe.AZUL)
    assert c.font.color.rgb.endswith("FFFFFF")


def test_excel_final_do_trimestre_so_tem_as_abas_usadas(tmp_path, monkeypatch):
    caminho = tmp_path / "t.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

    f = ExcelConsolidado.exportar(periodo="Mar/2026", nome_arquivo=str(tmp_path / "x.xlsx"),
                                  periodos_trimestre=MESES, abrir=False)
    nomes = openpyxl.load_workbook(f).sheetnames
    assert nomes[:4] == ["SCG", "SR", "PR", "PV"]
    assert not any("Dashboard" in n or "Resumo" in n for n in nomes)
    assert all(arpe.sem_emoji(n) == n for n in nomes)
