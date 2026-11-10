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

    def test_nd_eneva_total_no_fim_da_linha(self):
        # ND Petrolina jan-26: sem "Total" nem "R$"; só a 1ª parcela fica sozinha
        # na linha, o total vem depois da data de vencimento.
        texto = (
            "ORIGEM/ESPECIFICAÇÃO DO DÉBITO\n"
            "3.985,55\n"
            "Erro de Programação Petrolina QDP < 85% DEZ - 25\n"
            "Erro de Programação Petrolina QDP >115% DEZ-25 11.779,43\n"
            "Vencimento\n"
            "30/01/2026 15.764,98\n"
            "VALOR POR EXTENSO\n"
        )
        valor, _ = RegrasConcilia.extrair_valor(texto)
        assert valor == pytest.approx(15764.98)

    # ── Caracterização (fixa o comportamento atual; valores fictícios) ──────

    def test_mensagem_quando_acha_valor(self):
        assert RegrasConcilia.extrair_valor("Valor Total: R$ 12,34") == (pytest.approx(12.34), "Maior Valor Válido Detectado")

    def test_estrategia_4_numero_br_no_meio_da_linha(self):
        # Sem "Total", sem "R$" e sem número no fim da linha: varre o texto todo.
        assert RegrasConcilia.extrair_valor("cobranca 1.234,56 referente ao mes")[0] == pytest.approx(1234.56)

    def test_estrategia_4_ignora_acima_de_999_mil(self):
        assert RegrasConcilia.extrair_valor("cobranca 1.234.567,89 referente") == (0.0, "Valor não identificado")

    def test_estrategia_4_ignora_abaixo_de_1_real(self):
        assert RegrasConcilia.extrair_valor("taxa 0,99 aplicada") == (0.0, "Valor não identificado")

    def test_faixa_exclui_um_centavo(self):
        # 0,01 não passa no filtro "maior que 0,01" das estratégias 1–3 nem no ">= 1,00" da 4.
        assert RegrasConcilia.extrair_valor("R$ 0,01") == (0.0, "Valor não identificado")

    def test_estrategia_1_tem_prioridade_e_pega_o_maior(self):
        # "TOTAL ... = R$" casa na estratégia 1; o R$ 9.000,00 solto é ignorado.
        texto = "VALOR TOTAL = R$ 100,00\nTOTAL = R$ 250,00\nR$ 9.000,00"
        assert RegrasConcilia.extrair_valor(texto)[0] == pytest.approx(250.0)

    def test_l_minusculo_vira_1_e_padroes_com_l_nao_casam(self):
        # Comportamento atual (anotado como achado): clean_ocr_text troca "l" por
        # "1", então "Valor Total:" vira "Va1or Tota1:" e cai na estratégia 2
        # (maior R$ do texto).
        texto = "Valor Total: R$ 100,00\nValor a Pagar: R$ 250,00\nR$ 9.000,00"
        assert RegrasConcilia.extrair_valor(texto)[0] == pytest.approx(9000.0)

    def test_estrategia_3_ignora_numero_que_nao_esta_no_fim(self):
        texto = "linha 7,00 meio\nfinal 45,10"
        assert RegrasConcilia.extrair_valor(texto)[0] == pytest.approx(45.10)


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

    def test_top_entra_como_receita_mesmo_na_pasta_de_despesas(self, tmp_path):
        # fev-26: a subpasta "TOP Não Recup" foi guardada em Despesa, mas a
        # planilha oficial lança TOP não recuperável em Receitas.
        top = tmp_path / "Despesa" / "02 - fev26 TOP Não Recup" / "GERDAU - ND - TOP NREC 03864.pdf"
        desk = tmp_path / "Desktop" / "ND_Penalidade - PETROLINA.pdf"
        for a in (top, desk):
            a.parent.mkdir(parents=True, exist_ok=True)
            a.write_bytes(b"")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("Valor Total: R$ 10,00", "PDFPLUMBER"),
        ):
            itens = RegrasConcilia.processar_arquivos([top, desk], "Despesa", lambda _m: None, raiz=tmp_path)
        assert {i.file_name: i.category for i in itens} == {
            "GERDAU - ND - TOP NREC 03864.pdf": "Receita",
            "ND_Penalidade - PETROLINA.pdf": "Despesa",  # "Desktop" não é TOP
        }

    def test_substituidos_e_duplicadas_ficam_de_fora(self, tmp_path):
        atual = tmp_path / "2026.04.20 - KLABIN - NDTOPNREC03901 - Atualizada em 20.04.26.pdf"
        antiga = tmp_path / "Substituídos" / "KLABIN - NDTOPNREC03901.pdf"
        outra = tmp_path / "ALPEK - TOP.NREC - 4430_4313.pdf"
        for a in (atual, antiga, outra):
            a.parent.mkdir(parents=True, exist_ok=True)
            a.write_bytes(b"")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("Valor Total: R$ 10,00", "PDFPLUMBER"),
        ):
            itens = RegrasConcilia.processar_arquivos([antiga, atual, outra], "Receita", lambda _m: None, raiz=tmp_path)
        assert sorted(i.file_name for i in itens) == sorted([atual.name, outra.name])

    @pytest.mark.parametrize("ordem", ["original_primeiro", "atualizada_primeiro"])
    def test_mesma_nd_fica_a_atualizada_e_cancelada_entra_negativa_no_fim(self, tmp_path, ordem):
        # Caracterização: mesma ND na mesma pasta (sem "Substituídos"), uma
        # cancelada e uma sem número de ND. Valores fictícios.
        original = tmp_path / "EMPRESA X - NDPFP00001.pdf"
        atualizada = tmp_path / "EMPRESA X - NDPFP00001 atualizada.pdf"
        cancelada = tmp_path / "EMPRESA X - NDPFP00002 cancelado.pdf"
        sem_nd = tmp_path / "EMPRESA Y - nota avulsa.pdf"
        for a in (original, atualizada, cancelada, sem_nd):
            a.write_bytes(b"")
        par = [original, atualizada] if ordem == "original_primeiro" else [atualizada, original]
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("Valor Total: R$ 10,00", "PDFPLUMBER"),
        ):
            itens = RegrasConcilia.processar_arquivos([cancelada, *par, sem_nd], "Despesa", lambda _m: None)
        assert [(i.file_name, i.amount, i.status, i.category) for i in itens] == [
            (atualizada.name, 10.0, "OK", "Despesa"),
            (sem_nd.name, 10.0, "OK", "Despesa"),
            (cancelada.name, -10.0, "OK", "Despesa"),
        ]
        assert itens[0].method == "PDFPLUMBER -> Maior Valor Válido Detectado"

    def test_duas_sem_atualiz_fica_a_primeira(self, tmp_path):
        a = tmp_path / "EMPRESA X - NDPFP00003 v1.pdf"
        b = tmp_path / "EMPRESA X - NDPFP00003 v2.pdf"
        for f in (a, b):
            f.write_bytes(b"")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            return_value=("Valor Total: R$ 10,00", "PDFPLUMBER"),
        ):
            itens = RegrasConcilia.processar_arquivos([b, a], "Receita", lambda _m: None)
        assert [i.file_name for i in itens] == [b.name]

    def test_excecao_corta_mensagem_em_50_caracteres(self, tmp_path):
        arq = tmp_path / "x.pdf"
        arq.write_bytes(b"")
        with patch(
            "Src.Services.servicos_concilia.read_pdf_text",
            side_effect=RuntimeError("e" * 80),
        ):
            itens = RegrasConcilia.processar_arquivos([arq], "Receita", lambda _m: None)
        assert itens[0].method == "Exceção: " + "e" * 50
        assert itens[0].amount == 0.0


class TestPdfItemDataclass:
    def test_imutavel(self):
        item = PdfItem(
            file_name="x.pdf", file_path="/x.pdf", category="Receita",
            amount=100.0, status="OK", method="m",
        )
        with pytest.raises(Exception):
            item.amount = 999  # frozen=True
