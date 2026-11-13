"""Conciliação RP: serviço (servicos_concilia_lote) e API web. Banco
temporário via PLATAFORMA_DB. RP = despesas − receitas (planilha oficial)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.rp import servicos_concilia_lote as lote
from Src.Services.rp.servicos_concilia import PdfItem

RAIZ = Path(__file__).resolve().parents[1]
JAN = RAIZ / "SCG-26 - Copia" / "RP - Recuperação de Penalidades" / "Jan-26"
PASTA_DESP = JAN / "Penalidade-01 jan-26 Penalidade Falha de Programação (Despesa)"
PASTA_REC = JAN / "Receita-01 jan-26 Penalidade Falha de Programação (Receita)"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "rp_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _item(cat, valor, status="OK"):
    return PdfItem(file_name="a.pdf", file_path="a.pdf", category=cat, amount=valor, status=status, method="x")


def test_rp_e_despesas_menos_receitas_liquido_de_pis_cofins():
    t = lote.totais([_item("Despesa", 100.0), _item("Receita", 30.0), _item("Despesa", -10.0)])  # -10 = cancelada
    assert t["rp"] == pytest.approx(60.0 * 0.9075)
    assert t["total_receitas"] == pytest.approx(30.0 * 0.9075)


def test_salvar_grava_rp_e_scg_dos_modulos_bate(client):
    itens = [
        {"arquivo": "d.pdf", "caminho": "despesas/d.pdf", "categoria": "Despesa", "valor": 500.0, "status": "OK", "metodo": "x"},
        {"arquivo": "r.pdf", "caminho": "receitas/r.pdf", "categoria": "Receita", "valor": 200.0, "status": "OK", "metodo": "x"},
    ]
    resp = client.post("/api/conciliacao/salvar", json={"periodo": "Abr/2026", "itens": itens})
    assert resp.status_code == 200
    assert resp.json()["rp"] == pytest.approx(300.0 * 0.9075)
    comp = client.get("/api/scg/comparar", params={"periodo": "Abr/2026"}).json()
    assert comp["gravado"]["rp"] == pytest.approx(300.0 * 0.9075)
    assert comp["modulos"]["rp"] == pytest.approx(300.0 * 0.9075)  # mesma regra nos dois lados
    hist = {h["periodo"]: h for h in client.get("/api/conciliacao/historico").json()}
    assert hist["Abr/2026"]["rp_dos_itens"] == pytest.approx(hist["Abr/2026"]["rp_gravado"])


def test_salvar_recusa_periodo_invalido(client):
    resp = client.post("/api/conciliacao/salvar", json={"periodo": "jan", "itens": []})
    assert resp.status_code == 422


def test_relatorio(client):
    itens = [{"arquivo": "d.pdf", "caminho": "d.pdf", "categoria": "Despesa", "valor": 5.0, "status": "OK", "metodo": "x"}]
    resp = client.post("/api/conciliacao/relatorio", json={"periodo": "Abr/2026", "itens": itens})
    assert resp.status_code == 200 and resp.content[:2] == b"PK"


@pytest.mark.skipif(not (PASTA_DESP.exists() and PASTA_REC.exists()), reason="pastas reais de RP ausentes")
def test_pastas_reais_de_janeiro_igual_ao_desktop(client):
    """Mesmo resultado que a tela desktop lendo as pastas direto do disco, e
    igual à coluna jan-26 da planilha oficial "Conta Gráfica" (Penalidades).

    (Os itens gravados em Jan/2026 somam menos: na época, 3 PDFs de despesa
    não foram lidos — ficaram com valor 0 e status REVISAR.)"""
    esperado = lote.totais(lote.processar(PASTA_REC, PASTA_DESP))

    def campo(nome, pasta):
        return [(nome, (p.relative_to(pasta).as_posix(), p.read_bytes(), "application/pdf")) for p in sorted(pasta.rglob("*.pdf"))]

    resp = client.post("/api/conciliacao/processar", files=campo("receitas", PASTA_REC) + campo("despesas", PASTA_DESP))
    assert resp.status_code == 200, resp.text
    t = resp.json()["totais"]
    for k in ("total_despesas", "total_receitas", "rp"):
        assert t[k] == pytest.approx(esperado[k])
    # Planilha: PFP = 892.216,54; despesas = 86.214,11 + 14.306,72 + 89.541,95
    # (Petrolina = 15.764,98 bruto); Saldo de penalidade = −702.153,76.
    assert t["total_receitas"] == pytest.approx(892_216.54, abs=0.01)
    assert t["total_despesas"] == pytest.approx(190_062.78, abs=0.01)
    assert t["rp"] == pytest.approx(-702_153.76, abs=0.01)


RP_PASTAS = RAIZ / "SCG-26 - Copia" / "RP - Recuperação de Penalidades"
MAR_REC = RP_PASTAS / "mar-26" / "(Receita) 03 mar-26 Penalidade Falha de Programação"
MAR_DESP = RP_PASTAS / "mar-26" / "(Despesa)03 mar-26 Penalidade Falha de Programação"
FEV_REC = RP_PASTAS / "fev-26" / "Receita 02 fev-26 Penalidade Falha de Programação (Receita)"
FEV_DESP = RP_PASTAS / "fev-26" / "(penalidade) 02 fev-26 Penalidade Falha de Programação (Despesa)"


@pytest.mark.skipif(not (MAR_REC.exists() and MAR_DESP.exists()), reason="pastas reais de RP ausentes")
def test_marco_inclui_top_nao_recuperavel():
    """Planilha oficial, mar-26: PFP 429.307,28 + TOP não recuperável
    2.307.567,91 (receitas); Petrolina 19.160,79 (despesa);
    Saldo de penalidade = −2.717.714,40."""
    t = lote.totais(lote.processar(MAR_REC, MAR_DESP))
    assert t["total_receitas"] == pytest.approx(429_307.28 + 2_307_567.91, abs=0.02)
    assert t["total_despesas"] == pytest.approx(19_160.79, abs=0.01)
    assert t["rp"] == pytest.approx(-2_717_714.40, abs=0.02)


@pytest.mark.skipif(not (FEV_REC.exists() and FEV_DESP.exists()), reason="pastas reais de RP ausentes")
def test_fevereiro_top_da_pasta_de_despesas_vira_receita():
    """fev-26: o TOP está dentro da pasta de despesas, mas é receita.
    Brutos: PFP 573.278,96 (GERDAU atualizada), TOP 4.566.792,73 (sem a
    KLABIN de "Substituídos"), despesas TAG 504.297,99 + Petrolina 25.790,68.
    A planilha oficial difere só na Petrolina, lançada lá como
    "=25790.68*(0.0925)" em vez de "*(1-0.0925)"."""
    itens = lote.processar(FEV_REC, FEV_DESP)
    t = lote.totais(itens)
    assert len(itens) == 29
    assert t["total_receitas"] == pytest.approx((573_278.96 + 4_566_792.73) * 0.9075, abs=0.01)
    assert t["total_despesas"] == pytest.approx((461_151.40 + 43_146.59 + 25_790.68) * 0.9075, abs=0.01)


# ---------- Prova real do RP (valores fictícios) ----------

def _salvar(client, periodo, itens):
    corpo = [{"arquivo": a, "caminho": a, "categoria": c, "valor": v, "status": s, "metodo": "x"}
             for a, c, v, s in itens]
    r = client.post("/api/conciliacao/salvar", json={"periodo": periodo, "itens": corpo})
    assert r.status_code == 200, r.text
    return r.json()["rp"]


ITENS_BASE = [
    ("GERDAU - NDPFP03882.pdf", "Receita", 1000.0, "OK"),
    ("KLABIN - NDTOPNREC03901.pdf", "Receita", 25000.0, "OK"),   # TOP veio da pasta de despesas
    ("CPA - despesa.pdf", "Despesa", 400.0, "OK"),
]


def test_prova_real_confere_e_top_vai_para_receita(client):
    rp = _salvar(client, "Fev/2026", ITENS_BASE)
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert d["tem_itens"] and d["qtd_itens"] == 3 and d["taxa"] == 0.0925
    assert d["rp_calculado"] == pytest.approx(rp, abs=0.01) == pytest.approx((400 - 26000) * 0.9075, abs=0.01)
    assert d["confere"] is True and d["diferenca"] == pytest.approx(0, abs=0.01)
    assert d["receitas"]["qtd"] == 2 and d["despesas"]["qtd"] == 1
    top = next(i for i in d["itens"] if i["tipo"] == "TOP")
    assert top["lado"] == "receita" and top["numero"] == "03901"
    assert d["itens"][0]["valor"] == 25000.0           # maior valor primeiro
    assert d["possiveis_duplicadas"] == []


def test_prova_real_mes_sem_itens(client):
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Mar/2026"}).json()
    assert d["tem_itens"] is False and d["confere"] is False
    assert d["rp_calculado"] is None and d["itens"] == []


def test_prova_real_periodo_invalido_422(client):
    assert client.get("/api/conciliacao/prova-real", params={"periodo": "xx"}).status_code == 422


def test_prova_real_rp_alterado_por_fora(client):
    from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
    rp = _salvar(client, "Fev/2026", ITENS_BASE)
    with ServicosConsolidacao() as c:
        c.salvar_rp("Fev/2026", rp + 50.0)
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert d["confere"] is False and d["diferenca"] == pytest.approx(-50.0, abs=0.01)


def test_prova_real_nota_repetida_avisa_e_muda_rp(client):
    rp1 = _salvar(client, "Fev/2026", ITENS_BASE)
    repetidas = ITENS_BASE + [("2026.04.20 - KLABIN - NDTOPNREC03901 - Atualizada em 20.04.26.pdf", "Receita", 25243.08, "OK")]
    rp2 = _salvar(client, "Fev/2026", repetidas)
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert len(d["possiveis_duplicadas"]) == 1
    g = d["possiveis_duplicadas"][0]
    assert g["qtd"] == 2 and g["tipo"] == "TOP" and g["numero"] == "03901" and len(g["arquivos"]) == 2
    assert sum(i["repetida"] for i in d["itens"]) == 2
    # a nota repetida muda o RP em -(25.243,08 × 0,9075)
    assert rp2 - rp1 == pytest.approx(-25243.08 * 0.9075, abs=0.01)
    assert rp2 - rp1 == pytest.approx(-22908.10, abs=0.01)


def test_prova_real_ja_no_ret_fica_fora_do_rp(client):
    itens = ITENS_BASE + [("ND encargo.pdf", "Despesa", 0.0, "JA_NO_RET")]
    rp = _salvar(client, "Fev/2026", itens)
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert d["ja_no_ret"]["qtd"] == 1 and d["despesas"]["qtd"] == 1
    assert next(i for i in d["itens"] if i["nome"] == "ND encargo.pdf")["lado"] == "ja_no_ret"
    assert d["rp_calculado"] == pytest.approx(rp, abs=0.01) and d["confere"] is True


def test_prova_real_top_gravado_como_despesa_conta_como_receita(client):
    """Mês antigo: TOP foi gravado na categoria Despesa. A prova real o trata como receita
    e, como o RP gravado usou a regra velha, mostra a diferença (o problema aparece)."""
    _salvar(client, "Fev/2026", [("KLABIN - NDTOPNREC03901.pdf", "Despesa", 1000.0, "OK")])
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert d["itens"][0]["lado"] == "receita" and d["receitas"]["qtd"] == 1
    assert d["rp_calculado"] == pytest.approx(-907.5) and d["confere"] is False
