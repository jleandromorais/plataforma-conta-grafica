"""Aviso "Possível duplicata" (mesmo valor) das provas reais de RP, RET e Auditoria."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Src.common.duplicatas import possiveis_duplicatas_por_valor
from Src.Database.database import DatabasePMPV
from Src.Services import servicos_auditoria_lote as auditoria_lote


def _achar(itens, **kw):
    return possiveis_duplicatas_por_valor(
        itens, grupo=lambda i: i["g"], valor=lambda i: i["v"], nome=lambda i: i["n"], **kw)


class TestHelper:
    def test_mesmo_valor_no_mesmo_grupo_avisa(self):
        r = _achar([{"g": "Receita", "v": 25243.08, "n": "a.pdf", "id": 7}, {"g": "Receita", "v": 25243.08, "n": "b.pdf", "id": 9}])
        assert r == [{"grupo": "Receita", "valor": 25243.08, "qtd": 2, "notas": ["a.pdf", "b.pdf"], "ids": [7, 9]}]

    def test_grupos_diferentes_nao_avisam(self):
        assert _achar([{"g": "Receita", "v": 10.0, "n": "a"}, {"g": "Despesa", "v": 10.0, "n": "b"}]) == []

    def test_valores_diferentes_nao_avisam(self):
        assert _achar([{"g": "R", "v": 10.0, "n": "a"}, {"g": "R", "v": 10.01, "n": "b"}]) == []

    def test_valor_zero_e_vazio_ficam_fora(self):
        itens = [{"g": "R", "v": 0.0, "n": "a"}, {"g": "R", "v": 0.0, "n": "b"}, {"g": "R", "v": None, "n": "c"},
                 {"g": "R", "v": None, "n": "d"}]
        assert _achar(itens) == []

    def test_arredonda_em_duas_casas(self):
        assert len(_achar([{"g": "R", "v": 5.001, "n": "a"}, {"g": "R", "v": 4.999, "n": "b"}])) == 1

    def test_grupo_ja_avisado_pelo_numero_nao_repete(self):
        itens = [{"g": "R", "v": 7.0, "n": "a", "rep": True}, {"g": "R", "v": 7.0, "n": "b", "rep": True}]
        assert _achar(itens, ja_avisada=lambda i: i["rep"]) == []
        # basta uma nota sem o aviso do número para o aviso por valor valer
        itens[1]["rep"] = False
        assert len(_achar(itens, ja_avisada=lambda i: i["rep"])) == 1

    def test_ordem_do_maior_valor_em_modulo(self):
        itens = [{"g": "R", "v": v, "n": str(k)} for k, v in enumerate([5.0, 5.0, -90.0, -90.0, 20.0, 20.0])]
        assert [d["valor"] for d in _achar(itens)] == [-90.0, 20.0, 5.0]


# ---------- RP ----------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "dup_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def test_rp_cópia_renomeada_da_klabin_avisa_por_valor(client):
    # As duas cópias do fev/26: o número da ND sai diferente (03901 × 039017), então o aviso por número
    # não pega; o por valor pega.
    itens = [
        ("2026.04.20 - KLABIN - NDTOPNREC03901 - Atualizada em 20.04.26.pdf", "Receita", 25243.08),
        ("2026.04.20 - KLABIN - NDTOPNREC03901 -~7bf95f atualizada.pdf", "Receita", 25243.08),
        ("GERDAU - NDPFP03882.pdf", "Receita", 1000.0),
        ("CPA - despesa.pdf", "Despesa", 400.0),
    ]
    corpo = [{"arquivo": a, "caminho": a, "categoria": c, "valor": v, "status": "OK", "metodo": "x"} for a, c, v in itens]
    assert client.post("/api/conciliacao/salvar", json={"periodo": "Fev/2026", "itens": corpo}).status_code == 200
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    [g] = d["possiveis_duplicatas_valor"]
    assert (g["grupo"], g["valor"], g["qtd"]) == ("Receita", 25243.08, 2)
    assert len(g["notas"]) == 2


def test_rp_sem_valores_repetidos_nao_avisa(client):
    corpo = [{"arquivo": "a.pdf", "caminho": "a.pdf", "categoria": "Receita", "valor": 10.0, "status": "OK", "metodo": "x"},
             {"arquivo": "b.pdf", "caminho": "b.pdf", "categoria": "Despesa", "valor": 10.0, "status": "OK", "metodo": "x"}]
    client.post("/api/conciliacao/salvar", json={"periodo": "Fev/2026", "itens": corpo})
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert d["possiveis_duplicatas_valor"] == []  # receita e despesa de mesmo valor não são cópia


def test_rp_ja_no_ret_com_valor_zero_nao_conta(client):
    corpo = [{"arquivo": f"nd{k}.pdf", "caminho": f"nd{k}.pdf", "categoria": "Despesa", "valor": 0.0,
              "status": "JA_NO_RET", "metodo": "x"} for k in range(2)]
    corpo.append({"arquivo": "c.pdf", "caminho": "c.pdf", "categoria": "Despesa", "valor": 5.0, "status": "OK", "metodo": "x"})
    client.post("/api/conciliacao/salvar", json={"periodo": "Fev/2026", "itens": corpo})
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert d["possiveis_duplicatas_valor"] == []


# ---------- RET ----------

def _doc(tipo, valor, empresa, arquivo, mes="Jan/2026"):
    return {"arquivo": arquivo, "caminho": f"{tipo}/{mes}/{arquivo}", "tipo_encargo": tipo, "empresa": empresa,
            "nota_tipo": "Débito", "numero_nd": "1", "data_vencimento": "", "valor_total": valor, "mes_ref": mes}


def test_ret_mesmo_valor_mesma_empresa_e_tipo_avisa(client):
    docs = [_doc("EAT", 1000.0, "Empresa A", "eat1.pdf"), _doc("EAT", 1000.0, "Empresa A", "eat1 copia.pdf"),
            _doc("EAT", 1000.0, "Empresa B", "eat2.pdf"),      # outra empresa: não é cópia
            _doc("EC", 1000.0, "Empresa A", "ec1.pdf")]         # outro tipo: não é cópia
    assert client.post("/api/ret/salvar", json={"documentos": docs}).status_code == 200
    p = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    [g] = p["possiveis_duplicatas_valor"]
    assert (g["grupo"], g["valor"], g["qtd"]) == ("EAT · Empresa A", 1000.0, 2)
    assert sorted(g["notas"]) == ["eat1 copia.pdf", "eat1.pdf"]


def test_ret_sem_repeticao_nao_avisa(client):
    client.post("/api/ret/salvar", json={"documentos": [_doc("EAT", 1.0, "A", "a.pdf"), _doc("EAT", 2.0, "A", "b.pdf")]})
    p = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    assert p["possiveis_duplicatas_valor"] == []


# ---------- Tirar a nota do cálculo ----------

def _salvar_rp(client, periodo, itens):
    corpo = [{"arquivo": a, "caminho": a, "categoria": c, "valor": v, "status": "OK", "metodo": "x"} for a, c, v in itens]
    r = client.post("/api/conciliacao/salvar", json={"periodo": periodo, "itens": corpo})
    assert r.status_code == 200, r.text
    return r.json()["rp"]


KLABIN_COPIAS = [
    ("2026.04.20 - KLABIN - NDTOPNREC03901 - Atualizada em 20.04.26.pdf", "Receita", 25243.08),
    ("2026.04.20 - KLABIN - NDTOPNREC03901 -~7bf95f atualizada.pdf", "Receita", 25243.08),
    ("GERDAU - NDPFP03882.pdf", "Receita", 1000.0),
    ("CPA - despesa.pdf", "Despesa", 400.0),
]


def test_rp_tirar_a_copia_regrava_o_rp_sem_ela(client):
    rp_com_copia = _salvar_rp(client, "Fev/2026", KLABIN_COPIAS)
    d = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    [g] = d["possiveis_duplicatas_valor"]
    assert len(g["ids"]) == 2
    r = client.post("/api/conciliacao/remover-nota", json={"periodo": "Fev/2026", "id": g["ids"][1]})
    assert r.status_code == 200, r.text
    rp_sem_copia = (400 - 25243.08 - 1000.0) * 0.9075
    assert r.json()["valor_gravado"] == pytest.approx(rp_sem_copia, abs=0.01)
    assert r.json()["qtd_itens"] == 3
    assert r.json()["valor_gravado"] - rp_com_copia == pytest.approx(25243.08 * 0.9075, abs=0.01)
    depois = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()
    assert depois["possiveis_duplicatas_valor"] == []
    assert depois["confere"] is True and depois["rp_gravado"] == pytest.approx(rp_sem_copia, abs=0.01)
    assert depois["qtd_itens"] == 3


def test_rp_tirar_nota_que_nao_existe_ou_de_outro_mes_recusa(client):
    _salvar_rp(client, "Fev/2026", KLABIN_COPIAS)
    _salvar_rp(client, "Mar/2026", [("a.pdf", "Receita", 1.0), ("b.pdf", "Despesa", 2.0)])
    ids_mar = [i["id"] for i in client.get("/api/conciliacao/prova-real", params={"periodo": "Mar/2026"}).json()["itens"]]
    r = client.post("/api/conciliacao/remover-nota", json={"periodo": "Fev/2026", "id": ids_mar[0]})
    assert r.status_code == 422                      # id de outro mês não vale
    assert client.post("/api/conciliacao/remover-nota", json={"periodo": "Fev/2026", "id": 99999}).status_code == 422
    assert len(client.get("/api/conciliacao/prova-real", params={"periodo": "Mar/2026"}).json()["itens"]) == 2


def test_rp_nao_deixa_tirar_a_unica_nota(client):
    _salvar_rp(client, "Fev/2026", [("a.pdf", "Receita", 10.0)])
    i = client.get("/api/conciliacao/prova-real", params={"periodo": "Fev/2026"}).json()["itens"][0]
    assert client.post("/api/conciliacao/remover-nota", json={"periodo": "Fev/2026", "id": i["id"]}).status_code == 422


def test_ret_tirar_a_copia_regrava_o_ret(client):
    docs = [_doc("EAT", 1000.0, "Empresa A", "eat1.pdf"), _doc("EAT", 1000.0, "Empresa A", "eat1 copia.pdf"),
            _doc("EC", 500.0, "Empresa A", "ec1.pdf")]
    client.post("/api/ret/salvar", json={"documentos": docs})
    p = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    [g] = p["possiveis_duplicatas_valor"]
    assert p["ret_gravado"] == pytest.approx(2000 * 0.9075 + 500)
    r = client.post("/api/ret/remover-documento", json={"periodo": "Jan/2026", "id": g["ids"][0]})
    assert r.status_code == 200, r.text
    assert r.json()["valor_gravado"] == pytest.approx(1000 * 0.9075 + 500)
    depois = client.get("/api/ret/prova-real", params={"periodo": "Jan/2026"}).json()
    assert depois["possiveis_duplicatas_valor"] == [] and depois["confere"] is True
    assert depois["ret_gravado"] == pytest.approx(1000 * 0.9075 + 500)


def test_ret_tirar_documento_inexistente_recusa(client):
    client.post("/api/ret/salvar", json={"documentos": [_doc("EAT", 1.0, "A", "a.pdf"), _doc("EAT", 2.0, "A", "b.pdf")]})
    assert client.post("/api/ret/remover-documento", json={"periodo": "Jan/2026", "id": 99999}).status_code == 422


def test_auditoria_tirar_a_copia_regrava_o_cgr(client):
    itens = [
        {"empresa": "PETROBRAS", "tipo": "NF-e", "numero": "10", "valor_total": 50000.0, "cgr_liquido": 40000.0},
        {"empresa": "PETROBRAS", "tipo": "NF-e", "numero": "11", "valor_total": 50000.0, "cgr_liquido": 40000.0},
        {"empresa": "GALP", "tipo": "NF-e", "numero": "12", "valor_total": 30000.0, "cgr_liquido": 20000.0},
    ]
    with DatabasePMPV() as db:
        db.salvar_auditoria_itens("Mar/2026", itens)
    from Src.Services.servicos_consolidacao import ServicosConsolidacao
    with ServicosConsolidacao() as c:
        c.salvar_cgr("Mar/2026", 100000.0)
    p = auditoria_lote.prova_real("Mar/2026")
    [g] = p["possiveis_duplicatas_valor"]
    r = client.post("/api/auditoria/remover-nota", json={"periodo": "Mar/2026", "id": g["ids"][1]})
    assert r.status_code == 200, r.text
    assert r.json()["valor_gravado"] == pytest.approx(60000.0) and r.json()["qtd_itens"] == 2
    depois = auditoria_lote.prova_real("Mar/2026")
    assert depois["possiveis_duplicatas_valor"] == [] and depois["confere"] is True
    assert depois["cgr_gravado"] == pytest.approx(60000.0)


def test_auditoria_tirar_nota_inexistente_recusa(client):
    with DatabasePMPV() as db:
        db.salvar_auditoria_itens("Mar/2026", [{"empresa": "A", "tipo": "NF-e", "numero": "1", "valor_total": 1.0, "cgr_liquido": 1.0},
                                              {"empresa": "A", "tipo": "NF-e", "numero": "2", "valor_total": 2.0, "cgr_liquido": 2.0}])
    assert client.post("/api/auditoria/remover-nota", json={"periodo": "Mar/2026", "id": 99999}).status_code == 422


# ---------- Auditoria ----------

def test_auditoria_mesmo_valor_mesma_empresa_e_tipo_avisa(client):
    itens = [
        {"empresa": "PETROBRAS", "tipo": "NF-e", "numero": "10", "valor_total": 50000.0, "cgr_liquido": 40000.0},
        {"empresa": "PETROBRAS", "tipo": "NF-e", "numero": "11", "valor_total": 50000.0, "cgr_liquido": 40000.0},
        {"empresa": "GALP", "tipo": "NF-e", "numero": "12", "valor_total": 50000.0, "cgr_liquido": 40000.0},
        {"empresa": "PETROBRAS", "tipo": "CT-e", "numero": "13", "valor_total": 50000.0, "cgr_liquido": 0.0},
    ]
    with DatabasePMPV() as db:
        db.salvar_auditoria_itens("Mar/2026", itens)
    p = auditoria_lote.prova_real("Mar/2026")
    [g] = p["possiveis_duplicatas_valor"]
    assert (g["grupo"], g["valor"], g["qtd"]) == ("NF-e · PETROBRAS", 50000.0, 2)
    assert sorted(g["notas"]) == ["NF-e 10", "NF-e 11"]


def test_auditoria_sem_notas_nao_avisa(client):
    assert auditoria_lote.prova_real("Dez/2026")["possiveis_duplicatas_valor"] == []
