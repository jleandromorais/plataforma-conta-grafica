"""Relatório trimestral em Word: os achados vêm das provas reais e o .docx traz o texto."""
from io import BytesIO

import docx
from fastapi.testclient import TestClient

from Src.infrastructure.exporters import relatorio_trimestral as rt


def _prova(periodo, *, cgr=100.0, cgf=90.0, ret=5.0, rp=-3.0, gravado=True, origens=None, digitadas=(), dups=()):
    rpv = cgr - cgf
    ok = {"tem_itens": True, "confere": True, "valor_das_notas": cgr}
    return {
        "periodo": periodo, "gravado": gravado, "cgr": cgr, "cgf": cgf, "rpv": rpv, "ret": ret, "rp": rp,
        "scg_gravado": rpv + ret + rp, "scg_calculado": rpv + ret + rp,
        "diferenca": 0.0, "confere": True,
        "origens": origens or {"cgr": ok, "cgf": {"tem_resumo": True, "confere": True, "valor_calculado": cgf},
                               "ret": {"tem_itens": True, "confere": True, "valor_calculado": ret},
                               "rp": {"tem_itens": True, "confere": True, "valor_calculado": rp}},
        "notas_digitadas": list(digitadas), "possiveis_duplicatas_valor": list(dups),
    }


def _texto(conteudo: bytes) -> str:
    d = docx.Document(BytesIO(conteudo))
    return "\n".join([p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells])


MESES = ["Jul/2026", "Ago/2026", "Set/2026"]


def test_trimestre_limpo_sem_achados():
    d = {"meses": MESES, "provas": [_prova(m) for m in MESES]}
    assert rt.achados(d) == []
    assert "Nenhuma incongruência encontrada" in _texto(rt.montar(d))


def test_cgf_que_nao_confere_e_alta():
    o = {"cgr": {"tem_itens": True, "confere": True, "valor_das_notas": 100.0},
         "cgf": {"tem_resumo": True, "confere": False, "valor_calculado": 80.0},
         "ret": {"tem_itens": True, "confere": True, "valor_calculado": 5.0},
         "rp": {"tem_itens": True, "confere": True, "valor_calculado": -3.0}}
    d = {"meses": MESES, "provas": [_prova("Jul/2026", origens=o)]}
    a = rt.achados(d)
    assert [(x["modulo"], x["gravidade"]) for x in a] == [("CGF", "alta")]
    assert "-R$ 10,00" in a[0]["texto"]


def test_mes_sem_itens_e_atencao_e_nota_digitada_e_registro():
    sem = {k: {"tem_itens": False, "tem_resumo": False, "confere": False} for k in ("cgr", "cgf", "ret", "rp")}
    nota = {"tipo": "CT-e", "numero": "550499", "empresa": "TAG", "cgr_liquido": 481319.89, "motivo": "Copergás não enviou"}
    d = {"meses": MESES, "provas": [_prova("Jul/2026", digitadas=[nota]), _prova("Ago/2026", origens=sem)]}
    a = rt.achados(d)
    assert sum(1 for x in a if x["gravidade"] == "atencao") == 4
    reg = [x for x in a if x["gravidade"] == "info"][0]
    assert "550499" in reg["texto"] and "Copergás não enviou" in reg["texto"]
    txt = _texto(rt.montar(d))
    assert "550499" in txt and "sem notas" in txt


def test_mes_sem_fechamento():
    d = {"meses": MESES, "provas": [_prova("Jul/2026", gravado=False)]}
    assert rt.achados(d)[0]["gravidade"] == "alta"
    rt.montar(d)


def test_api_devolve_docx(monkeypatch):
    from Src.api.main import app
    monkeypatch.setattr(rt, "dados_do_trimestre", lambda meses: {"meses": meses, "provas": [_prova(m) for m in meses]})
    with TestClient(app) as c:
        r = c.post("/api/relatorio-trimestral/gerar", params={"periodo": "Ago/2026"})
    assert r.status_code == 200
    assert "Relatorio_Trimestral_" in r.headers["content-disposition"]
    assert "Relatório Trimestral" in _texto(r.content)
