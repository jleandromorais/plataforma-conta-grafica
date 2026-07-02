from __future__ import annotations


def format_brl(value: float) -> str:
    """Formata em moeda brasileira com 2 casas: R$ 1.234,56."""
    return f"R$ {(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl4(value: float) -> str:
    """Formata em moeda brasileira com 4 casas: R$ 1,2345 (usado em PMPV/PR/PV)."""
    return f"R$ {(value or 0):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl_plain(value: float) -> str:
    """Formata BRL sem prefixo com 2 casas: 1.234,56."""
    return f"{(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_brl4_plain(value: float) -> str:
    """Formata BRL sem prefixo com 4 casas: 1,2345."""
    return f"{(value or 0):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_vol(value: float) -> str:
    """Formata volume em m³ com separador de milhar: 1.234.567."""
    return f"{(value or 0):,.0f}".replace(",", ".")


def format_vol_m3(value: float) -> str:
    """Formata volume com 2 casas decimais sem zeros à direita: '1.234,5' ou '1.234'."""
    texto = f"{(value or 0):,.2f}"
    inteiro, decimal = texto.split(".")
    inteiro = inteiro.replace(",", ".")
    decimal = decimal.rstrip("0")
    return f"{inteiro},{decimal}" if decimal else inteiro


def format_brl_compacto(value: float) -> str:
    """Formata BRL de forma compacta: R$ 1,23 Mi / R$ 1,2 mil / R$ 1,23."""
    sinal = "-" if value < 0 else ""
    av = abs(value)
    if av >= 1_000_000:
        return f"{sinal}R$ {av/1_000_000:,.2f} Mi".replace(",", "X").replace(".", ",").replace("X", ".")
    if av >= 1_000:
        return f"{sinal}R$ {av/1_000:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".")
    return format_brl(value)


def parse_brl(text: str) -> float:
    """Converte 'R$ 1.234,56', '1234,56', '1234.56' ou '1,2345' para float."""
    if not text:
        return 0.0
    txt = str(text).strip().replace("R$", "").replace(" ", "").replace("/m³", "").replace("m³", "")
    if "," in txt and "." in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return 0.0
