"""Auditoria CGR: serviço em lote (servicos_auditoria_lote) e API web.

O serviço contém a orquestração que antes ficava na tela desktop; a API só
o expõe. Banco temporário via PLATAFORMA_DB.
"""
from __future__ import annotations

import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_auditoria_lote as lote
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem
from tests.test_servicos_auditoria import CTE_XML_NORMAL, NFE_XML

RAIZ = Path(__file__).resolve().parents[1]
PASTA_REAL_JAN = RAIZ / "SCG-26 - Copia" / "RPV - Recuperação do Preço de Venda" / "CGR" / "01 jan-26 Notas Fiscais"


def _nfe(numero: str, valor: float = 10000.0) -> str:
    return NFE_XML.replace("<nNF>123456</nNF>", f"<nNF>{numero}</nNF>").replace("<vNF>10000.00</vNF>", f"<vNF>{valor:.2f}</vNF>")


def _item(empresa="PETROBRAS", tipo="NF-e", valor=1000.0, taxa=0.12, caminho="PETROBRAS/n.xml"):
    return XMLItem(empresa, tipo, "1", valor, valor * taxa, taxa, 0, 0, 0, "OK", 0, caminho)


# ── Regras por item ──────────────────────────────────────────────────────────

class TestRegrasItem:
    def test_devolucao_e_negativa(self):
        normal = _item(caminho="PETROBRAS/Vendas/nf.xml")
        devolvida = _item(caminho="PETROBRAS/NF Devolvidas/nf.xml")  # antes não era reconhecida
        devolucao = _item(caminho="PETROBRAS/Devolução/nf.xml")
        esperado = RegrasAuditoria.calcular_s_tributos(1000.0, 0.12)
        assert lote.cgr_liquido_item(normal) == pytest.approx(esperado)
        assert lote.cgr_liquido_item(devolvida) == pytest.approx(-esperado)
        assert lote.cgr_liquido_item(devolucao) == pytest.approx(-esperado)

    def test_cte_de_transportadora_comum_fica_fora_do_cgr(self):
        frete = _item(empresa="Transportadora X", tipo="CT-e")
        gasoduto = _item(empresa="TAG", tipo="CT-e")
        tot = lote.calcular_totais([frete, gasoduto, _item()])
        assert tot["cgr_liquido"] == pytest.approx(2 * RegrasAuditoria.calcular_s_tributos(1000.0, 0.12))
        x = next(e for e in tot["por_empresa"] if e["empresa"] == "Transportadora X")
        assert x["cgr_liquido"] == 0 and x["frete_fora_do_cgr"] == pytest.approx(1000.0)

    def test_soma_das_empresas_bate_com_o_total(self):
        itens = [_item(), _item(empresa="GALP", valor=500.0), _item(empresa="Y", tipo="CT-e"), _item(caminho="P/devolvidas/x.xml")]
        tot = lote.calcular_totais(itens)
        assert sum(e["cgr_liquido"] for e in tot["por_empresa"]) == pytest.approx(tot["cgr_liquido"])

    def test_itens_gravados_com_sinal_da_devolucao(self):
        itens = lote.itens_para_banco([_item(), _item(caminho="P/devolvidas/x.xml")])
        assert itens[0]["cgr_liquido"] > 0 > itens[1]["cgr_liquido"]
        # a soma gravada (lado "dos módulos" do SCG) = CGR total
        assert sum(i["cgr_liquido"] for i in itens) == pytest.approx(0.0)


# ── API ──────────────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "aud_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _envio_sintetico():
    return [
        ("arquivos", ("PETROBRAS/nf1.xml", _nfe("1").encode(), "text/xml")),
        ("arquivos", ("PETROBRAS/nf2.xml", _nfe("2", 5000.0).encode(), "text/xml")),
        ("arquivos", ("PETROBRAS/Devolvidas/nf3.xml", _nfe("3", 2000.0).encode(), "text/xml")),
        ("arquivos", ("Transportadora X/cte.xml", CTE_XML_NORMAL.encode(), "text/xml")),
        ("arquivos", ("../fora.xml", _nfe("9").encode(), "text/xml")),  # caminho perigoso: ignorado
    ]


def test_processar_pasta_enviada(client):
    resp = client.post("/api/auditoria/processar", files=_envio_sintetico(), data={"pasta_raiz": "01 jan-26 Notas Fiscais"})
    assert resp.status_code == 200, resp.text
    r = resp.json()
    assert r["periodo_detectado"] == "Jan/2026"
    assert len(r["itens"]) == 4
    assert r["totais"]["qtd_devolucoes"] == 1
    s = lambda v: RegrasAuditoria.calcular_s_tributos(v, 0.12)  # noqa: E731
    assert r["totais"]["cgr_liquido"] == pytest.approx(s(10000) + s(5000) - s(2000))  # CT-e de frete fora
    assert r["comparacao"] is None and r["aviso_comparacao"]


def _codigos(r: dict) -> list[str]:
    return [p["codigo"] for p in r["problemas"]]


def test_processar_sem_problemas_quando_tudo_certo(client):
    r = client.post("/api/auditoria/processar", files=_envio_sintetico()).json()
    assert r["problemas"] == []


def test_xml_malformado_vira_problema_com_empresa_e_arquivo(client):
    """AC6: a nota que não pôde ser lida aparece, e a conta lidos × auditadas × problemas fecha."""
    envio = _envio_sintetico() + [("arquivos", ("GALP/quebrado.xml", b"<nfeProc><NFe>sem fechar", "text/xml"))]
    r = client.post("/api/auditoria/processar", files=envio).json()
    [p] = [p for p in r["problemas"] if p["codigo"] == "xml_invalido"]
    assert p["gravidade"] == "aviso"
    assert p["empresa"] == "GALP" and p["arquivo"] == "quebrado.xml"
    assert r["qtd_xml_lidos"] == len(r["itens"]) + 1


def test_xml_que_nao_e_nota_vira_info(client):
    envio = _envio_sintetico() + [("arquivos", ("PETROBRAS/evento.xml", b"<outro>qualquer</outro>", "text/xml"))]
    r = client.post("/api/auditoria/processar", files=envio).json()
    [p] = [p for p in r["problemas"] if p["codigo"] == "xml_tipo_desconhecido"]
    assert p["gravidade"] == "info" and p["empresa"] == "PETROBRAS"


def test_empresa_escolhida_que_nao_esta_na_pasta(client):
    r = client.post(
        "/api/auditoria/processar", files=_envio_sintetico(), data={"empresas": json.dumps(["PETROBRAS", "ENEVA"])},
    ).json()
    [p] = [p for p in r["problemas"] if p["codigo"] == "empresa_nao_encontrada"]
    assert p["empresa"] == "ENEVA" and p["gravidade"] == "aviso"


def test_empresa_sem_notas(tmp_path):
    (tmp_path / "VAZIA").mkdir()
    (tmp_path / "PETROBRAS").mkdir()
    (tmp_path / "PETROBRAS" / "nf.xml").write_text(_nfe("1"), encoding="utf-8")
    problemas: list[dict] = []
    itens, _, _ = lote.auditar_pasta(tmp_path, ["PETROBRAS", "VAZIA"], usar_pdf=False, problemas=problemas)
    assert len(itens) == 1
    assert [(p["codigo"], p["empresa"]) for p in problemas] == [("empresa_sem_notas", "VAZIA")]


def test_planilha_de_comparacao_corrompida_nao_da_500(client):
    """AC7."""
    envio = _envio_sintetico() + [("planilha", ("conta grafica.xlsx", b"nao e excel", "application/octet-stream"))]
    resp = client.post("/api/auditoria/processar", files=envio, data={"periodo": "Jan/2026"})
    assert resp.status_code == 200, resp.text
    r = resp.json()
    assert len(r["itens"]) == 4
    [p] = [p for p in r["problemas"] if p["codigo"] == "planilha_comparacao_ilegivel"]
    assert p["arquivo"] == "conta grafica.xlsx" and p["gravidade"] == "erro"


def test_processar_zip_e_filtro_de_empresas(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("Notas Fev 2026/PETROBRAS/nf1.xml", _nfe("1"))
        z.writestr("Notas Fev 2026/GALP/nf2.xml", _nfe("2"))
    r = client.post(
        "/api/auditoria/processar",
        files=[("arquivos", ("notas.zip", buf.getvalue(), "application/zip"))],
        data={"empresas": json.dumps(["GALP"])},
    ).json()
    assert [i["empresa"] for i in r["itens"]] == ["GALP"]
    assert r["periodo_detectado"] == "Fev/2026"


def test_salvar_recalcula_cgr_e_grava_itens(client):
    r = client.post("/api/auditoria/processar", files=_envio_sintetico()).json()
    itens = r["itens"]
    itens[0]["cgr_liquido"] = 999999  # valor do cliente é ignorado: o servidor recalcula
    resp = client.post("/api/auditoria/salvar", json={"periodo": "Mar/2026", "itens": itens})
    assert resp.status_code == 200
    assert resp.json()["cgr_liquido"] == pytest.approx(r["totais"]["cgr_liquido"])
    assert client.get("/api/rpv", params={"periodo": "Mar/2026"}).json()["cgr"] == pytest.approx(r["totais"]["cgr_liquido"])
    # SCG "dos módulos" (soma dos itens gravados) agora bate com o CGR salvo
    comp = client.get("/api/scg/comparar", params={"periodo": "Mar/2026"}).json()
    assert comp["modulos"]["cgr"] == pytest.approx(comp["gravado"]["cgr"])
    hist = {h["periodo"]: h for h in client.get("/api/auditoria/historico").json()}
    assert hist["Mar/2026"]["qtd_notas"] == 4


def test_prova_real_refaz_o_cgr_gravado(client):
    r = client.post("/api/auditoria/processar", files=_envio_sintetico()).json()
    client.post("/api/auditoria/salvar", json={"periodo": "Mar/2026", "itens": r["itens"]})
    p = client.get("/api/auditoria/prova-real", params={"periodo": "Mar/2026"}).json()
    assert p["qtd_notas"] == len(r["itens"])
    assert p["cgr_das_notas"] == pytest.approx(r["totais"]["cgr_liquido"])
    assert p["cgr_gravado"] == pytest.approx(r["totais"]["cgr_liquido"])
    assert p["confere"] is True
    # A conta fecha por empresa e por parte: compras + devoluções = CGR.
    assert sum(e["cgr"] for e in p["por_empresa"]) == pytest.approx(p["cgr_das_notas"])
    assert p["compras"] + p["devolucoes"] == pytest.approx(p["cgr_das_notas"])
    # Frete comum fica fora, igual ao processar.
    frete = {e["empresa"]: e["frete_fora_do_cgr"] for e in r["totais"]["por_empresa"]}
    assert {e["empresa"]: e["frete_fora_do_cgr"] for e in p["por_empresa"]} == pytest.approx(frete)


def test_prova_real_de_mes_sem_notas_nao_confere(client):
    p = client.get("/api/auditoria/prova-real", params={"periodo": "Dez/2026"}).json()
    assert p["qtd_notas"] == 0 and p["confere"] is False and p["cgr_gravado"] is None


def test_prova_real_periodo_invalido(client):
    assert client.get("/api/auditoria/prova-real", params={"periodo": "Teste"}).status_code == 422


def test_relatorio_excel(client):
    itens = client.post("/api/auditoria/processar", files=_envio_sintetico()).json()["itens"]
    resp = client.post("/api/auditoria/relatorio", data={"itens": json.dumps(itens), "periodo": "Mar/2026"})
    assert resp.status_code == 200
    assert resp.content[:2] == b"PK"  # xlsx
    assert "Auditoria_Mar-2026.xlsx" in resp.headers["content-disposition"]


@pytest.mark.skipif(not PASTA_REAL_JAN.exists(), reason="pasta real de NFs ausente")
def test_xmls_reais_igual_ao_servico(client, tmp_path):
    """Só os XMLs de duas empresas (os PDFs deixariam o teste lento)."""
    copia = tmp_path / "01 jan-26 Notas Fiscais"
    for emp in ("TAG", "Brava"):
        for xml in (PASTA_REAL_JAN / emp).rglob("*"):
            if xml.suffix.lower() == ".xml":
                alvo = copia / emp / xml.relative_to(PASTA_REAL_JAN / emp)
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(xml, alvo)
    itens, _, _ = lote.auditar_pasta(copia, ["Brava", "TAG"], usar_pdf=False)
    esperado = lote.calcular_totais(itens)["cgr_liquido"]

    arquivos = [("arquivos", (p.relative_to(copia).as_posix(), p.read_bytes(), "text/xml")) for p in copia.rglob("*.xml")]
    r = client.post("/api/auditoria/processar", files=arquivos, data={"pasta_raiz": copia.name}).json()
    assert r["totais"]["cgr_liquido"] == pytest.approx(esperado)
    assert len(r["itens"]) == len(itens)
