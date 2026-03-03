from __future__ import annotations


def format_brl(value: float) -> str:
    """Formata número em moeda brasileira: R$ 1.234,56."""
    return f"R$ {(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl_plain(value: float) -> str:
    """Formata número em BRL sem prefixo: 1.234,56."""
    return f"{(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_brl(text: str) -> float:
    """Converte texto 'R$ 1.234,56' ou '1234,56' ou '1234.56' para float."""
    if not text:
        return 0.0
    txt = text.strip().replace("R$", "").replace(" ", "")
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return 0.0

