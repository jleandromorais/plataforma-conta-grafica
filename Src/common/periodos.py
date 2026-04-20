from __future__ import annotations

import re
import unicodedata


_MESES = {
    "jan": "Jan",
    "janeiro": "Jan",
    "fev": "Fev",
    "fevereiro": "Fev",
    "mar": "Mar",
    "marco": "Mar",
    "abril": "Abr",
    "abr": "Abr",
    "mai": "Mai",
    "maio": "Mai",
    "jun": "Jun",
    "junho": "Jun",
    "jul": "Jul",
    "julho": "Jul",
    "ago": "Ago",
    "agosto": "Ago",
    "set": "Set",
    "setembro": "Set",
    "out": "Out",
    "outubro": "Out",
    "nov": "Nov",
    "novembro": "Nov",
    "dez": "Dez",
    "dezembro": "Dez",
}

_MES_NUMERO = {
    1: "Jan",
    2: "Fev",
    3: "Mar",
    4: "Abr",
    5: "Mai",
    6: "Jun",
    7: "Jul",
    8: "Ago",
    9: "Set",
    10: "Out",
    11: "Nov",
    12: "Dez",
}

# Mapeamento abreviação → nome completo normalizado (sem acentos)
_ABREV_TO_FULL = {
    "jan": "janeiro",
    "fev": "fevereiro",
    "mar": "marco",
    "abr": "abril",
    "mai": "maio",
    "jun": "junho",
    "jul": "julho",
    "ago": "agosto",
    "set": "setembro",
    "out": "outubro",
    "nov": "novembro",
    "dez": "dezembro",
}


def _limpar_texto(valor: str | None) -> str:
    texto = "" if valor is None else str(valor).strip()
    texto = re.sub(r"\s+", " ", texto)
    return re.sub(r"\s*/\s*", "/", texto)


def _normalizar_token(texto: str) -> str:
    token = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", token.lower())


def _normalizar_ano(ano: str) -> str:
    ano_limpo = str(ano).strip()
    if len(ano_limpo) == 2 and ano_limpo.isdigit():
        return f"20{ano_limpo}"
    return ano_limpo


def normalizar_periodo(periodo: str | None) -> str:
    texto = _limpar_texto(periodo)
    if not texto:
        return ""

    # Formato com separador: "jan/26", "jan/2026", "01/2026"
    match_mes = re.fullmatch(r"([A-Za-zÀ-ÿ]+|\d{1,2})/(\d{2}|\d{4})", texto)
    if match_mes:
        mes_bruto, ano_bruto = match_mes.groups()
        ano = _normalizar_ano(ano_bruto)
        if mes_bruto.isdigit():
            mes_nome = _MES_NUMERO.get(int(mes_bruto))
            if mes_nome:
                return f"{mes_nome}/{ano}"
        mes_nome = _MESES.get(_normalizar_token(mes_bruto))
        if mes_nome:
            return f"{mes_nome}/{ano}"

    match_trimestre = re.fullmatch(r"([Qq]\d)/(\d{2}|\d{4})", texto)
    if match_trimestre:
        trimestre, ano_bruto = match_trimestre.groups()
        return f"{trimestre.upper()}/{_normalizar_ano(ano_bruto)}"

    # Formato sem separador: "jan26", "jan2026", "janeiro26", "fev25"
    match_sem_sep = re.fullmatch(r"([A-Za-zÀ-ÿ]+)(\d{2}|\d{4})", texto)
    if match_sem_sep:
        mes_bruto, ano_bruto = match_sem_sep.groups()
        ano = _normalizar_ano(ano_bruto)
        mes_nome = _MESES.get(_normalizar_token(mes_bruto))
        if mes_nome:
            return f"{mes_nome}/{ano}"

    return texto


def variantes_periodo(periodo: str | None) -> tuple[str, ...]:
    texto = _limpar_texto(periodo)
    if not texto:
        return tuple()

    canonico = normalizar_periodo(texto)
    variantes: list[str] = []
    for candidato in (canonico, texto):
        if candidato and candidato not in variantes:
            variantes.append(candidato)

    match_mes = re.fullmatch(r"([A-Za-zÀ-ÿ]+)/(\d{4})", canonico)
    if match_mes:
        mes, ano = match_mes.groups()
        curto = f"{mes}/{ano[-2:]}"
        if curto not in variantes:
            variantes.append(curto)

    match_trimestre = re.fullmatch(r"([Qq]\d)/(\d{4})", canonico)
    if match_trimestre:
        trimestre, ano = match_trimestre.groups()
        curto = f"{trimestre.upper()}/{ano[-2:]}"
        if curto not in variantes:
            variantes.append(curto)

    return tuple(variantes)
