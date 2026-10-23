"""PR pela Nota Técnica (planilha "Q7, Q8 e Q9 PR-PV"):

    PR = ROUND((Σ SCG_m × (1 + SELIC acum_m) + Σ SR_m com SELIC) / VP; 4)

SCG e SR dos 3 meses do trimestre civil apurado (Jan–Mar/26 para o PR de
Mai–Jul/26); VP = soma do VP dos 3 meses do PR. Números da planilha.
"""
from unittest.mock import MagicMock, patch

import pytest

from Src.Services import servicos_pr
from Src.Services.servicos_pr import ServicosPR, meses_apurados_do_pr

# Q5 - SCG - Anexo A (BI16:BK16, BI19:BK19) e Q6 - SR (AV10:AX10)
JAN_MAR_26 = [
    {"periodo": "Jan/2026", "scg": -458695.85571998963, "selic": 3.411174217622337, "sr": -137622.23},
    {"periodo": "Fev/2026", "scg": 3318892.518926999, "selic": 2.221160445031889, "sr": -74924.76},
    {"periodo": "Mar/2026", "scg": -2634822.303553988, "selic": 1.212054, "sr": -57463.99},
]
VP_MAI_JUL_26 = [45663000.0, 44190000.0, 43896000.0]


def test_pr_mai_jul_26_igual_planilha():
    r = ServicosPR.apurar_pr_nt(JAN_MAR_26, VP_MAI_JUL_26, pmpv=2.283)

    assert r["scg_selic"] == pytest.approx(251509.90, abs=0.01)
    assert r["sr"] == pytest.approx(-270010.98, abs=0.01)
    assert r["saldo_total"] == pytest.approx(-18501.08, abs=0.01)
    assert r["vp"] == 133749000.0
    assert r["pr"] == -0.0001
    assert r["pv"] == pytest.approx(2.2829)


def test_sem_vp_nao_divide_por_zero():
    r = ServicosPR.apurar_pr_nt(JAN_MAR_26, [0.0, 0.0, 0.0], pmpv=2.283)
    assert r["pr"] == 0.0


@pytest.mark.parametrize("meses_pr, apurados", [
    (["Mai/2026", "Jun/2026", "Jul/2026"], ["Jan/2026", "Fev/2026", "Mar/2026"]),
    (["Fev/2026", "Mar/2026", "Abr/2026"], ["Out/2025", "Nov/2025", "Dez/2025"]),
    (["Ago/2026", "Set/2026", "Out/2026"], ["Abr/2026", "Mai/2026", "Jun/2026"]),
    (["Nov/2025", "Dez/2025", "Jan/2026"], ["Jul/2025", "Ago/2025", "Set/2025"]),
])
def test_trimestre_civil_apurado(meses_pr, apurados):
    assert meses_apurados_do_pr(meses_pr) == apurados


def test_apurar_trimestre_le_banco_e_aponta_pendencias():
    repo_pr = MagicMock()
    repo_pr.buscar_pmpv_mensal.return_value = 2.283
    repo_sr = MagicMock()
    repo_sr.buscar_sr_trimestre.side_effect = lambda label: [
        {"mes": m["periodo"], "selic_mensal": m["selic"], "sr_selic": m["sr"]} for m in JAN_MAR_26
    ] if label == "Jan/2026_Mar/2026" else []
    cons = MagicMock()
    cons.buscar_consolidacao.side_effect = lambda p: {"scg": next(m["scg"] for m in JAN_MAR_26 if m["periodo"] == p)}
    vps = dict(zip(["Mai/2026", "Jun/2026", "Jul/2026"], VP_MAI_JUL_26))

    with patch.object(servicos_pr, "SqliteSRRepository", return_value=repo_sr), \
         patch.object(servicos_pr, "ServicosConsolidacao", return_value=cons), \
         patch.object(servicos_pr, "vp_do_mes", side_effect=lambda _r, p: vps.get(p, 0.0)):
        r = ServicosPR(repo_pr).apurar_trimestre(["Mai/2026", "Jun/2026", "Jul/2026"])

    assert r["meses_apurados"] == ["Jan/2026", "Fev/2026", "Mar/2026"]
    assert r["pr"] == -0.0001
    assert r["pendencias"] == []
    assert [m["sr"] for m in r["meses"]] == [-137622.23, -74924.76, -57463.99]


def test_apurar_trimestre_sem_sr_salvo_avisa():
    repo_sr = MagicMock()
    repo_sr.buscar_sr_trimestre.return_value = []
    cons = MagicMock()
    cons.buscar_consolidacao.return_value = {"scg": 1.0}
    with patch.object(servicos_pr, "SqliteSRRepository", return_value=repo_sr), \
         patch.object(servicos_pr, "ServicosConsolidacao", return_value=cons), \
         patch.object(servicos_pr, "vp_do_mes", return_value=1.0):
        r = ServicosPR(MagicMock()).apurar_trimestre(["Mai/2026", "Jun/2026", "Jul/2026"])
    assert any("SR" in p and "Jan/2026" in p for p in r["pendencias"])


def test_api_apurar(monkeypatch):
    from fastapi.testclient import TestClient
    from Src.api.main import app
    monkeypatch.setattr(ServicosPR, "apurar_trimestre", lambda self, periodos: {"pr": -0.0001, "meses_pr": periodos})
    with TestClient(app) as c:
        r = c.post("/api/pr/apurar", json={"periodos": ["Mai/2026", "Jun/2026", "Jul/2026"]})
    assert r.status_code == 200, r.text
    assert r.json()["pr"] == -0.0001
