from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from Src.Services.servicos_concilia import RegrasConcilia, PdfItem


class TestCleanOcrText:
    def test_remove_pipe(self):
        assert RegrasConcilia.clean_ocr_text("a|b") == "ab"

    def test_exclamacao_vira_1(self):
        assert RegrasConcilia.clean_ocr_text("R$ 1!0,00") == "R$ 110,00"

    def test_l_minusculo_vira_1(self):
        assert RegrasConcilia.clean_ocr_text("l00") == "100"

    def test_vazio(self):
        assert RegrasConcilia.clean_ocr_text("") == ""

    def test_none(self):
        assert RegrasConcilia.clean_ocr_text(None) == ""


# ════════════════════════════════════════════════════════════════════════════
# extrair_valor
# ════════════════════════════════════════════════════════════════════════════

class TestExtrairValor:
    def test_texto_vazio(self):
        valor, msg = RegrasConcilia.extrair_valor("")
        assert valor == 0.0
        assert "vazio" in msg.lower()

    def test_padrao_total_nota_debito(self):
        texto = "Total Nota de Débito Fatura = R$ 1.234,56"
        valor, _ = RegrasConcilia.extrair_valor(texto)
        assert valor == pytest.approx(1234.56)

    def test_padrao_valor_a_pagar(self):
        texto = "Valor a Pagar: R$ 999,99"
        valor, _ = RegrasConcilia.extrair_valor(texto)
        assert valor == pytest.approx(999.99)

    def test_padrao_valor_total(self):
        texto = "Valor Total: R$ 5.000,00"
        valor, _ = RegrasConcilia.extrair_valor(texto)
        assert valor == pytest.approx(5000.0)

    def test_fallback_maior_rs(self):
        texto = "R$ 10,00 R$ 200,00 R$ 50,00"
        valor, msg = RegrasConcilia.extrair_valor(texto)
        assert valor == 200.0
        assert "maior" in msg.lower()

    def test_sem_valor_identificavel(self):
        valor, msg = RegrasConcilia.extrair_valor("texto qualquer sem números")
        assert valor == 0.0
        assert "não identificado" in msg.lower()

    def test_valores_de_ano_nao_sao_filtrados_indevidamente(self):
        # O código foi corrigido para NÃO descartar 2024-2027 quando aparecem como R$
        texto = "R$ 2024,00"
        valor, _ = RegrasConcilia.extrair_valor(texto)
        assert valor == pytest.approx(2024.0)

    def test_total_prefere_sobre_outros_rs(self):
        # Quando tem padrão "Total ... = R$ X" + outros valores soltos, o maior dos
        # encontrados via "Total" é escolhido.
        texto = "Valor parcial R$ 50,00\nTotal = R$ 9.999,99"
        valor, _ = RegrasConcilia.extrair_valor(texto)
        assert valor == pytest.approx(9999.99)


# ════════════════════════════════════════════════════════════════════════════
# processar_arquivos
# ════════════════════════════════════════════════════════════════════════════

class TestProcessarArquivos:
    def test_arquivo_com_texto_e_valor(self, tmp_path):
        arq = tmp_path / "fatura.pdf"
        arq.write_bytes(b"%PDF-fake")

        logs = []
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("Valor Total: R$ 1.500,00", "PDFPLUMBER"),
        ):
            itens = RegrasConcilia.processar_arquivos([arq], "Receita", logs.append)

        assert len(itens) == 1
        item = itens[0]
        assert isinstance(item, PdfItem)
        assert item.file_name == "fatura.pdf"
        assert item.category == "Receita"
        assert item.amount == pytest.approx(1500.0)
        assert item.status == "OK"
        assert "PDFPLUMBER" in item.method
        assert logs  # callback foi chamado

    def test_sem_texto_extraido(self, tmp_path):
        arq = tmp_path / "vazio.pdf"
        arq.write_bytes(b"%PDF")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("", "OCR"),
        ):
            itens = RegrasConcilia.processar_arquivos([arq], "Despesa", lambda _m: None)
        assert itens[0].status == "ERRO"
        assert itens[0].amount == 0.0

    def test_excecao_na_leitura(self, tmp_path):
        arq = tmp_path / "x.pdf"
        arq.write_bytes(b"")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            side_effect=RuntimeError("io fail"),
        ):
            itens = RegrasConcilia.processar_arquivos([arq], "Receita", lambda _m: None)
        assert itens[0].status == "ERRO"
        assert "Exceção" in itens[0].method

    def test_valor_zero_marca_revisar(self, tmp_path):
        arq = tmp_path / "x.pdf"
        arq.write_bytes(b"")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("sem valor identificável aqui", "PDFPLUMBER"),
        ):
            itens = RegrasConcilia.processar_arquivos([arq], "Despesa", lambda _m: None)
        assert itens[0].status == "REVISAR"

    def test_log_inclui_progresso(self, tmp_path):
        arq1 = tmp_path / "a.pdf"
        arq2 = tmp_path / "b.pdf"
        for a in (arq1, arq2):
            a.write_bytes(b"")
        logs = []
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("Valor Total: R$ 10,00", "PDFPLUMBER"),
        ):
            RegrasConcilia.processar_arquivos([arq1, arq2], "Receita", logs.append)
        assert any("[1/2]" in l for l in logs)
        assert any("[2/2]" in l for l in logs)


class TestPdfItemDataclass:
    def test_imutavel(self):
        item = PdfItem(
            file_name="x.pdf", file_path="/x.pdf", category="Receita",
            amount=100.0, status="OK", method="m",
        )
        with pytest.raises(Exception):
            item.amount = 999  # frozen=True
