from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Src.infrastructure.ocr import ocr_pdf


class TestReadPdfTextTextoDigital:
    def test_pdf_com_texto_extenso(self, tmp_path):
        # Mocka pdfplumber.open() pra retornar páginas com texto > 50 chars
        fake_pdf = MagicMock()
        page1 = MagicMock()
        page1.extract_text.return_value = "A" * 60  # >50 chars → texto digital
        fake_pdf.pages = [page1]

        ctx = MagicMock()
        ctx.__enter__.return_value = fake_pdf
        ctx.__exit__.return_value = False

        with patch.object(ocr_pdf, "pdfplumber") as mock_plum:
            mock_plum.open.return_value = ctx
            texto, metodo = ocr_pdf.read_pdf_text(tmp_path / "x.pdf")

        assert metodo == "TEXTO_DIGITAL"
        assert texto.strip().startswith("A")

    def test_junta_paginas(self, tmp_path):
        fake_pdf = MagicMock()
        # Cada página precisa ter texto bem maior que 50 chars pra evitar fallback OCR
        p1 = MagicMock(); p1.extract_text.return_value = "Pagina 1 com texto bem extenso para garantir que ultrapasse o limite de 50 caracteres exigido pelo modulo"
        p2 = MagicMock(); p2.extract_text.return_value = "Pagina 2 igualmente extensa para o caso de cair em alguma checagem por pagina e nao por junta"
        fake_pdf.pages = [p1, p2]

        ctx = MagicMock()
        ctx.__enter__.return_value = fake_pdf

        with patch.object(ocr_pdf, "pdfplumber") as mock_plum:
            mock_plum.open.return_value = ctx
            texto, metodo = ocr_pdf.read_pdf_text(tmp_path / "x.pdf")

        assert "Pagina 1" in texto
        assert "Pagina 2" in texto
        assert metodo == "TEXTO_DIGITAL"

    def test_pagina_sem_texto_usa_string_vazia(self, tmp_path):
        fake_pdf = MagicMock()
        p1 = MagicMock(); p1.extract_text.return_value = None  # pdfplumber às vezes retorna None
        p2 = MagicMock(); p2.extract_text.return_value = "B" * 80  # >50 chars → TEXTO_DIGITAL
        fake_pdf.pages = [p1, p2]

        ctx = MagicMock()
        ctx.__enter__.return_value = fake_pdf

        with patch.object(ocr_pdf, "pdfplumber") as mock_plum:
            mock_plum.open.return_value = ctx
            texto, metodo = ocr_pdf.read_pdf_text(tmp_path / "x.pdf")

        # Não pode levantar AttributeError no None — o `or ""` da implementação trata
        assert metodo == "TEXTO_DIGITAL"
        assert "BBB" in texto


class TestReadPdfTextOCR:
    def test_fallback_ocr_quando_texto_curto(self, tmp_path):
        # Texto curto (≤50 chars) e OCR habilitado → vai pro OCR
        fake_pdf = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = "curto"
        page.to_image.return_value = MagicMock(original="IMAGEM_FAKE")
        fake_pdf.pages = [page]

        ctx = MagicMock()
        ctx.__enter__.return_value = fake_pdf

        with patch.object(ocr_pdf, "pdfplumber") as mock_plum, \
             patch.object(ocr_pdf, "OCR_ENABLED", True), \
             patch.object(ocr_pdf, "pytesseract") as mock_tess:
            mock_plum.open.return_value = ctx
            mock_tess.image_to_string.return_value = "Texto via OCR"
            texto, metodo = ocr_pdf.read_pdf_text(tmp_path / "x.pdf")

        assert metodo == "OCR"
        assert texto == "Texto via OCR"
        mock_tess.image_to_string.assert_called_once_with("IMAGEM_FAKE", lang="por")

    def test_lang_customizada_passada_pro_tesseract(self, tmp_path):
        fake_pdf = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = ""
        page.to_image.return_value = MagicMock(original="IMG")
        fake_pdf.pages = [page]

        ctx = MagicMock()
        ctx.__enter__.return_value = fake_pdf

        with patch.object(ocr_pdf, "pdfplumber") as mock_plum, \
             patch.object(ocr_pdf, "OCR_ENABLED", True), \
             patch.object(ocr_pdf, "pytesseract") as mock_tess:
            mock_plum.open.return_value = ctx
            mock_tess.image_to_string.return_value = "ok"
            ocr_pdf.read_pdf_text(tmp_path / "x.pdf", lang="eng")

        mock_tess.image_to_string.assert_called_once_with("IMG", lang="eng")

    def test_sem_tesseract_e_texto_curto_retorna_falha(self, tmp_path):
        fake_pdf = MagicMock()
        page = MagicMock()
        page.extract_text.return_value = "curto"
        fake_pdf.pages = [page]

        ctx = MagicMock()
        ctx.__enter__.return_value = fake_pdf

        with patch.object(ocr_pdf, "pdfplumber") as mock_plum, \
             patch.object(ocr_pdf, "OCR_ENABLED", False):
            mock_plum.open.return_value = ctx
            texto, metodo = ocr_pdf.read_pdf_text(tmp_path / "x.pdf")

        assert texto == ""
        assert "FALHA" in metodo
        assert "Tesseract" in metodo


class TestConfiguracaoTesseract:
    def test_ocr_enabled_e_bool(self):
        assert isinstance(ocr_pdf.OCR_ENABLED, bool)

    def test_candidates_list_inclui_paths_padrao(self):
        # Garante que o módulo não removeu os fallbacks de path do Tesseract
        assert any("Tesseract-OCR" in p for p in ocr_pdf._TESSERACT_CANDIDATES if p)
