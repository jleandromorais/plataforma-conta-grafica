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
    assert "550499" in txt and "Sem notas" in txt


def test_mes_sem_fechamento():
    d = {"meses": MESES, "provas": [_prova("Jul/2026", gravado=False)]}
    assert rt.achados(d)[0]["gravidade"] == "alta"
    rt.montar(d)


def test_trimestre_limpo_diz_tudo_batendo():
    d = {"meses": MESES, "provas": [_prova(m) for m in MESES]}
    txt = _texto(rt.montar(d))
    assert "Tudo batendo" in txt
    assert "12 de 12" in txt  # partes que conferem


def test_scg_nao_gravado_usa_conta_refeita_e_avisa():
    """Bug antigo: o total somava a coluna `scg` crua; mês sem ela entrava como R$ 0,00."""
    p = _prova("Ago/2026")
    p["scg_gravado"], p["diferenca"], p["confere"] = None, None, False
    d = {"meses": MESES, "provas": [_prova("Jul/2026"), p, _prova("Set/2026")]}
    a = [x for x in rt.achados(d) if x["modulo"] == "SCG"]
    assert [x["gravidade"] for x in a] == ["atencao"]
    txt = _texto(rt.montar(d))
    assert "R$ 36,00" in txt  # 3 × (100 − 90 + 5 − 3)
    assert "SCG não gravado" in txt


def test_scg_gravado_diferente_nao_fecha_e_relatorio_usa_a_conta():
    p = _prova("Jul/2026")
    p["scg_gravado"], p["diferenca"], p["confere"] = 500.0, 12.0 - 500.0, False
    d = {"meses": MESES, "provas": [p, _prova("Ago/2026"), _prova("Set/2026")]}
    a = rt.achados(d)
    assert [(x["modulo"], x["gravidade"]) for x in a] == [("SCG", "alta")]
    txt = _texto(rt.montar(d))
    assert "Não está tudo batendo" in txt and "R$ 36,00" in txt


def test_auditoria_por_empresa_aparece():
    p = _prova("Jul/2026")
    p["auditoria"] = {
        "qtd_notas": 3, "compras": 110.0, "devolucoes": -10.0, "frete_fora_do_cgr": 7.0,
        "cgr_das_notas": 100.0, "cgr_gravado": 100.0, "diferenca": 0.0,
        "por_empresa": [{"empresa": "GNlink", "qtd_nfe": 2, "qtd_cte": 0, "compras": 110.0, "devolucoes": -10.0,
                         "frete_fora_do_cgr": 0.0, "cgr": 100.0},
                        {"empresa": "Transportes X", "qtd_nfe": 0, "qtd_cte": 1, "compras": 0.0, "devolucoes": 0.0,
                         "frete_fora_do_cgr": 7.0, "cgr": 0.0}],
    }
    p["possiveis_duplicatas_valor"] = [{"grupo": "NF-e · GNlink", "valor": 55.0, "qtd": 2,
                                        "notas": ["NF-e 265", "NF-e 255"], "ids": [1, 2]}]
    d = {"meses": MESES, "provas": [p, _prova("Ago/2026"), _prova("Set/2026")]}
    txt = _texto(rt.montar(d))
    assert "GNlink" in txt and "Transportes X" in txt
    assert "NF-e 265, NF-e 255" in txt
    assert "Tirar do cálculo" in txt


def _pl(**k):
    base = {"periodo": "Jul/2026", "erro": None, "tem_mes": True, "modelo_rotulo": "Conta Gráfica e Apuração de Custos",
            "cgr_notas": 99_913_890.30, "fontes_cgr": [], "qtd_em_ambas": 89, "so_na_planilha": [],
            "so_gravadas": [], "divergencias": [], "supridores": []}
    return {**base, **k}


def test_planilha_nota_que_falta_aparece_mesmo_com_o_sistema_fechando():
    """O caso de jul/26: sistema fecha consigo mesmo, mas a TAG 550499 está só na planilha."""
    p = _prova("Jul/2026")
    p["planilha"] = _pl(
        fontes_cgr=[{"rotulo": "Aba Conta Gráfica", "valor": 100_395_210.17}],
        so_na_planilha=[{"empresa": "TAG", "numero": "550499", "linha_excel": 97, "cgr_planilha": 481_319.89}],
        divergencias=[{"empresa": "GNLink", "numero": "000.271.226-1", "linha_excel": 42,
                       "motivos": ["Volume"], "diferenca_cgr": 0.0, "explicacao": "Só o volume difere."}],
    )
    d = {"meses": MESES, "provas": [p, _prova("Ago/2026"), _prova("Set/2026")], "com_planilha": True}
    a = rt.achados(d)
    altas = [x for x in a if x["gravidade"] == "alta"]
    assert len(altas) == 2 and all(x["modulo"] == "Planilha" for x in altas)
    assert any("550499" in x["texto"] and "linha 97" in x["texto"] for x in altas)
    assert "R$ 481.319,87 a menos" in altas[0]["texto"]
    assert [x["gravidade"] for x in a if "GNLink" in x["texto"]] == ["atencao"]
    txt = _texto(rt.montar(d))
    assert "Não está tudo batendo" in txt and "✗ Não bate" in txt and "550499" in txt


def test_planilha_tudo_batendo_e_sem_planilha_avisa():
    d = {"meses": MESES, "provas": [{**_prova(m), "planilha": _pl()} for m in MESES], "com_planilha": True}
    assert rt.achados(d) == []
    assert "Tudo batendo com a planilha oficial" in _texto(rt.montar(d))

    sem = {"meses": MESES, "provas": [_prova(m) for m in MESES]}
    txt = _texto(rt.montar(sem))
    assert "Tudo batendo no sistema" in txt and "sem a planilha oficial" in txt


def test_itens_gravados_como_xml_devolvem_o_mesmo_cgr():
    from Src.Services.auditoria.servicos_auditoria_lote import cgr_liquido_item, itens_gravados_como_xml

    gravados = [
        {"empresa": "Petrobras", "tipo": "NF-e", "numero": "1", "valor_total": 1000.0, "cgr_liquido": 798.6},
        {"empresa": "Petrobras", "tipo": "NF-e", "numero": "2", "valor_total": 500.0, "cgr_liquido": -399.3},
        {"empresa": "TAG", "tipo": "CT-e", "numero": "550499", "valor_total": 0.0, "cgr_liquido": 481319.89},
    ]
    itens = itens_gravados_como_xml(gravados)
    for g, i in zip(gravados, itens):
        assert abs(cgr_liquido_item(i) - g["cgr_liquido"]) < 0.005


def test_api_aceita_planilha(monkeypatch):
    from Src.api.main import app
    recebido = {}

    def falso(meses, planilha=None):
        recebido["planilha"] = planilha
        return {"meses": meses, "provas": [_prova(m) for m in meses]}

    monkeypatch.setattr(rt, "dados_do_trimestre", falso)
    with TestClient(app) as c:
        r = c.post("/api/relatorio-trimestral/gerar", params={"periodo": "Ago/2026"},
                   files={"planilha": ("cg.xlsx", b"x", "application/octet-stream")})
    assert r.status_code == 200
    assert recebido["planilha"] and recebido["planilha"].endswith(".xlsx")


def test_api_devolve_docx(monkeypatch):
    from Src.api.main import app
    monkeypatch.setattr(rt, "dados_do_trimestre",
                        lambda meses, planilha=None: {"meses": meses, "provas": [_prova(m) for m in meses]})
    with TestClient(app) as c:
        r = c.post("/api/relatorio-trimestral/gerar", params={"periodo": "Ago/2026"})
    assert r.status_code == 200
    assert "Relatorio_Trimestral_" in r.headers["content-disposition"]
    assert "Relatório Trimestral" in _texto(r.content)
