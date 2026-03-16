from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import pdfplumber

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None  # type: ignore


_TESSERACT_CANDIDATES = [
    os.environ.get("TESSERACT_CMD", ""),
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
]

_tess_path = next((p for p in _TESSERACT_CANDIDATES if os.path.exists(p)), None) if pytesseract else None
if _tess_path and pytesseract:
    pytesseract.pytesseract.tesseract_cmd = _tess_path

OCR_ENABLED: bool = bool(_tess_path and pytesseract)


def read_pdf_text(pdf_path: Path, lang: str = "por") -> Tuple[str, str]:
    """
    Le texto de um PDF.

    Prioridade:
      1. Texto digital via pdfplumber.
      2. Fallback OCR na primeira pagina (se OCR_ENABLED).

    Retorna (texto, metodo_usado).
    """
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
            text = "\n".join(pages_text)

            if len(text.strip()) > 50:
                return text, "TEXTO_DIGITAL"

            if not OCR_ENABLED or not pytesseract:
                return "", "FALHA: Imagem (sem Tesseract)"

            image = pdf.pages[0].to_image(resolution=300).original
            ocr_text = pytesseract.image_to_string(image, lang=lang)
            return ocr_text, "OCR"
    except Exception as e:  # pragma: no cover
        return "", f"ERRO LEITURA: {e}"
