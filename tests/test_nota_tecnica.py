"""Minuta da Nota Técnica: com os números da NT 15/2026 (ciclo Abr–Jun/26,
PR Ago–Out/26) o documento traz os mesmos valores e textos da NT."""
from io import BytesIO

import docx
import pytest
from fastapi.testclient import TestClient

from Src.infrastructure.exporters import nota_tecnica as nt

MA = ["Abr/2026", "Mai/2026", "Jun/2026"]
SCG = {
    "Abr/2026": {"rpv": 4687274.80, "ret": 1192962.49, "rp": -484524.48, "scg": 5395712.81},
    "Mai/2026": {"rpv": -2645270.40, "ret": 448473.40, "rp": -632153.25, "scg": -2828950.25},
    "Jun/2026": {"rpv": -272855.03, "ret": 338345.75, "rp": -900148.73, "scg": -834658.02},
}
SELIC = {"Abr/2026": 3.319049, "Mai/2026": 2.204956, "Jun/2026": 1.119504}
SR_SELIC = {"Abr/2026": -30243.19, "Mai/2026": -10.09, "Jun/2026": -46.47}


def _dados():
    meses = [{"periodo": m, "scg": SCG[m]["scg"], "selic": SELIC[m], "sr": SR_SELIC[m],
              "scg_selic": SCG[m]["scg"] * (1 + SELIC[m] / 100)} for m in MA]
    return {
        "meses_apurados": MA, "meses_pr": nt.meses_do_pr(MA), "meses_pr_anterior": ["Mai/2026", "Jun/2026", "Jul/2026"],
        "scg": {m: {**SCG[m], "cgr": 0.0, "cgf": 0.0, "vf": 0.0, "pmpv": 0.0} for m in MA},
        "sr": [{"mes": m, "vp": 0, "vf": 0, "diferenca": 0, "pr": -0.0001, "sr_parcela": 0,
                "selic_mensal": SELIC[m], "sr_selic": SR_SELIC[m]} for m in MA],
        "pr": {"meses": meses, "scg_selic": 1839469.78, "sr": -30299.75, "saldo_total": 1809170.03,
               "vp": 133917011.0, "pr": 0.0135, "pendencias": []},
        "pv": {"pmpv": 2.3597, "pr": 0.0135, "pv": 2.3732, "avisos": []},
        "pv_anterior": {"pmpv": 2.2829},
    }


def _texto(conteudo: bytes) -> str:
    d = docx.Document(BytesIO(conteudo))
    partes = [p.text for p in d.paragraphs]
    partes += [c.text for t in d.tables for r in t.rows for c in r.cells]
    return "\n".join(partes)


def test_periodos_do_ciclo():
    assert nt.meses_do_pr(MA) == ["Ago/2026", "Set/2026", "Out/2026"]
    assert nt.por_extenso(["Ago/2026", "Set/2026", "Out/2026"]) == "1º de agosto de 2026 a 31 de outubro de 2026"
    assert nt.trimestre_pr_do_mes("Abr/2026") == ["Fev/2026", "Mar/2026", "Abr/2026"]
    assert nt.trimestre_pr_do_mes("Jan/2026") == ["Nov/2025", "Dez/2025", "Jan/2026"]
    assert nt.com_sinal(-30299.75) == "[-] R$ 30.299,75"


def test_minuta_traz_os_valores_da_nt_15_2026():
    texto = _texto(nt.montar(_dados()))
    assert "AGOSTO/2026 – OUTUBRO/2026" in texto
    assert "resultou no valor positivo de R$ 1.839.469,78 a ser acrescido à tarifa" in texto
    assert "[-] R$ 30.299,75" in texto
    assert "valor positivo de [+] R$ 0,0135/m³" in texto
    assert "5.395.712,81" in texto and "1.809.170,03" in texto and "133.917.011 m³" in texto
    assert "2,3732" in texto
    assert "um aumento de 3,36%" in texto  # 2,3597 / 2,2829 − 1
    assert "saldo remanescente de abril/2026 referente a PRfev/26-abr/26" in texto


def test_api_devolve_docx(monkeypatch):
    from Src.api.main import app
    monkeypatch.setattr(nt, "dados_do_ciclo", lambda meses: _dados())
    with TestClient(app) as c:
        r = c.post("/api/nota-tecnica/gerar", params={"periodo": "Jun/2026"})
    assert r.status_code == 200, r.text
    assert "Minuta_NT_Repasse_Ago-2026_a_Out-2026.docx" in r.headers["content-disposition"]
    assert "0,0135" in _texto(r.content)


@pytest.mark.parametrize("periodo", ["junho", "13/2026"])
def test_api_periodo_invalido(periodo):
    from Src.api.main import app
    with TestClient(app) as c:
        assert c.post("/api/nota-tecnica/gerar", params={"periodo": periodo}).status_code == 422
