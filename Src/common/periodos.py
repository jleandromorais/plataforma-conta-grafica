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


# Lista ordenada das 12 abreviações (usada em combos, validações, etc.)
MESES_ABREVS: list[str] = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
]

# Mapeamento EN abrev → PT abrev (para Excel com cabeçalhos em inglês)
_EN_TO_PT: dict[str, str] = {
    "Jan": "Jan", "Feb": "Fev", "Mar": "Mar", "Apr": "Abr",
    "May": "Mai", "Jun": "Jun", "Jul": "Jul", "Aug": "Ago",
    "Sep": "Set", "Oct": "Out", "Nov": "Nov", "Dec": "Dez",
}


def numero_para_abrev(numero: int) -> str:
    """Converte número de mês (1–12) para abreviação PT. Lança ValueError se inválido."""
    abrev = _MES_NUMERO.get(numero)
    if abrev is None:
        raise ValueError(f"Número de mês inválido: {numero!r}")
    return abrev


def abrev_para_numero(abrev: str) -> int:
    """Converte abreviação PT (ex: 'Jan') para número de mês (1–12). Lança ValueError se inválido."""
    try:
        return MESES_ABREVS.index(abrev.capitalize()[:3]) + 1
    except ValueError:
        raise ValueError(f"Abreviação de mês inválida: {abrev!r}")


def en_para_pt(abrev_en: str) -> str:
    """Converte abreviação inglesa (ex: 'Feb') para PT (ex: 'Fev'). Retorna original se não encontrado."""
    return _EN_TO_PT.get(abrev_en.capitalize()[:3], abrev_en)


def _limpar_texto(valor: str | None) -> str:
    texto = "" if valor is None else str(valor).strip()
    texto = re.sub(r"\s+", " ", texto)
    return re.sub(r"\s*/\s*", "/", texto)


def _normalizar_token(texto: str) -> str:
    token = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", token.lower())


_ANO_MIN = 2000
_ANO_MAX = 2099


def _normalizar_ano(ano: str) -> str:
    ano_limpo = str(ano).strip()
    if len(ano_limpo) == 2 and ano_limpo.isdigit():
        ano_limpo = f"20{ano_limpo}"
    if ano_limpo.isdigit() and not (_ANO_MIN <= int(ano_limpo) <= _ANO_MAX):
        raise ValueError(f"Ano fora do intervalo permitido ({_ANO_MIN}–{_ANO_MAX}): {ano!r}")
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


_MES_ORDEM = {v.lower(): k for k, v in _MES_NUMERO.items()}


def periodo_sort_key(periodo: str) -> tuple[int, int]:
    """Retorna (ano, mes) para ordenação cronológica. Períodos inválidos vão para o final."""
    canonico = normalizar_periodo(periodo)
    m = re.fullmatch(r"([A-Za-z]+)/(\d{4})", canonico)
    if m:
        mes_str, ano_str = m.groups()
        mes_num = _MES_ORDEM.get(mes_str.lower(), 0)
        return (int(ano_str), mes_num)
    return (0, 0)


def is_periodo_valido(periodo: str) -> bool:
    """Retorna True se o período é um Mês/Ano válido (ex: Jan/2026)."""
    canonico = normalizar_periodo(periodo)
    return bool(re.fullmatch(r"[A-Za-z]{3}/\d{4}", canonico))


# ── Trimestres fiscais (PR / PV / PMPV) ──────────────────────────────────────
# Fonte única de verdade. Índices 0-based onde 0=Jan … 11=Dez.
# Nov (10) e Dez (11) pertencem ao ano anterior do trimestre fiscal.
TRIMESTRES_FISCAIS: dict[str, tuple[int, int, int]] = {
    "Nov - Jan": (10, 11, 0),
    "Fev - Abr": (1,  2,  3),
    "Mai - Jul": (4,  5,  6),
    "Ago - Out": (7,  8,  9),
}

# Lista ordenada de abreviaturas por trimestre fiscal (para Excel e agrupamentos)
TRIMESTRES_FISCAIS_ABREVS: list[tuple[str, list[str]]] = [
    ("Nov - Jan", ["Nov", "Dez", "Jan"]),
    ("Fev - Abr", ["Fev", "Mar", "Abr"]),
    ("Mai - Jul", ["Mai", "Jun", "Jul"]),
    ("Ago - Out", ["Ago", "Set", "Out"]),
]

# Trimestres civis (SCG / CGR / CGF / RET / RP / SR)
TRIMESTRES_CIVIS: dict[str, list[str]] = {
    "Jan - Mar": ["Jan", "Fev", "Mar"],
    "Abr - Jun": ["Abr", "Mai", "Jun"],
    "Jul - Set": ["Jul", "Ago", "Set"],
    "Out - Dez": ["Out", "Nov", "Dez"],
}
