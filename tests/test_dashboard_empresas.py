"""Dashboard › CGR por empresa: totais do filtro e as mesmas contas mês a mês."""
from Src.api import dashboard_extra as dx


def _nota(periodo, empresa, cgr, tipo="NF-e"):
    return {"periodo": periodo, "empresa": empresa, "tipo": tipo, "valor_total": cgr * 1.2,
            "icms": 1.0, "pis": 0.5, "cofins": 0.5, "cgr_liquido": cgr}


def test_empresas_traz_meses_em_ordem_e_totais_batem(monkeypatch):
    linhas = [_nota("Set/2026", "Petrobras", 100.0), _nota("Jul/2026", "Petrobras", 50.0),
              _nota("Jul/2026", "TAG", 30.0, tipo="CT-e"), _nota("Ago/2025", "Eneva", 10.0),
              _nota("lixo", "X", 999.0)]
    monkeypatch.setattr(dx, "_linhas", lambda _sql: linhas)

    r = dx.empresas(None)
    assert [m["periodo"] for m in r["meses"]] == ["Ago/2025", "Jul/2026", "Set/2026"]
    jul = r["meses"][1]["empresas"]
    assert [(e["empresa"], e["cgr_liquido"], e["cte"]) for e in jul] == [("Petrobras", 50.0, 0), ("TAG", 30.0, 1)]
    soma_meses = sum(e["cgr_liquido"] for m in r["meses"] for e in m["empresas"])
    assert soma_meses == r["total_cgr_liquido"] == 190.0

    r26 = dx.empresas("2026")
    assert [m["periodo"] for m in r26["meses"]] == ["Jul/2026", "Set/2026"]
    assert r26["total_cgr_liquido"] == 180.0
