"""Despesa que já está no RET não conta de novo no RP (ex.: ND 90014427 em jul/26)."""
from __future__ import annotations

import pytest

from Src.Database.database import DatabasePMPV
from Src.Services import servicos_concilia_lote as lote
from Src.Services.servicos_concilia import PdfItem


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "ret.db"
    with DatabasePMPV(db_path=str(caminho)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(caminho))
    return caminho


def _item(nome, valor, categoria="Despesa"):
    return PdfItem(file_name=nome, file_path=f"x/{nome}", category=categoria, amount=valor, status="OK", method="TEXTO_DIGITAL")


def test_despesa_ja_salva_no_ret_vira_zero_e_nao_conta_no_rp(banco):
    with DatabasePMPV() as db:
        db.salvar_ret_itens("Jul/2026", [{"arquivo": "ND 90014427 - COPERGAS.pdf", "caminho": "EAT/ND 90014427 - COPERGAS.pdf",
                                          "tipo_encargo": "EAT", "empresa": "COPERGAS", "nota_tipo": "Débito", "numero_nd": "90014427",
                                          "data_vencimento": "", "valor_total": 133905.42, "moeda_detectada": "BRL", "contrib_ec": "EC"}])
    itens = [_item("ND 90014427 - COPERGAS.pdf", 133905.42), _item("ND Petrolina_Penalidade.pdf", 4506.24),
             _item("AMBEV - NDPFP04058.pdf", 133905.42, categoria="Receita")]   # receita com mesmo valor: não é tocada
    lote.marcar_ja_no_ret(itens)
    assert (itens[0].amount, itens[0].status) == (0.0, "JA_NO_RET")
    assert itens[1].amount == 4506.24 and itens[1].status == "OK"
    assert itens[2].amount == 133905.42
    t = lote.totais(itens)
    assert t["total_despesas"] == pytest.approx(4506.24 * 0.9075)
    assert t["qtd_revisar"] == 0   # "já no RET" não é pendência


def test_sem_ret_salvo_nada_muda(banco):
    itens = [_item("ND 90014427 - COPERGAS.pdf", 133905.42)]
    lote.marcar_ja_no_ret(itens)
    assert itens[0].amount == 133905.42 and itens[0].status == "OK"


def test_pdfs_da_pasta_lista_cada_arquivo_uma_vez(tmp_path):
    """Windows: *.pdf e *.PDF casam o mesmo arquivo; antes cada PDF vinha duas vezes."""
    (tmp_path / "sub").mkdir()
    for nome in ("a.pdf", "b.PDF", "sub/c.pdf", "sub/d.Pdf", "nao.txt"):
        (tmp_path / nome).write_bytes(b"%PDF")
    assert [p.name for p in lote.pdfs_da_pasta(tmp_path)] == ["a.pdf", "b.PDF", "c.pdf", "d.Pdf"][:0] or \
        sorted(p.name for p in lote.pdfs_da_pasta(tmp_path)) == ["a.pdf", "b.PDF", "c.pdf", "d.Pdf"]
    assert lote.pdfs_da_pasta(None) == [] and lote.pdfs_da_pasta(tmp_path / "nao_existe") == []
