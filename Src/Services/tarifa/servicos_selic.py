"""SELIC acumulada de cada mês do trimestre civil, buscada no Banco Central.

Regra das planilhas ARPE (aba "SELIC - Bacen" da Conta Gráfica; SR e Anexo A
da NT 05/2026), usada no SR (Quadro 6) e no SCG do PR (Quadros 5 e 7):

    fator do dia     = 1 + taxa do dia (série SGS 11) / 100
    SELIC do mês     = Π fatores dos dias úteis do mês
    acumulada do mês = Π (1 + SELIC do mês) do mês até o fim do trimestre civil − 1

A série 4390 (SELIC mensal) não serve: tem 2 casas e diverge das planilhas
(Jul/25: 1,28% contra 1,275733%).
"""
from __future__ import annotations

import calendar
import json
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from typing import Callable

from Src.common.periodos import abrev_para_numero

URL_SGS11 = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados?formato=json&dataInicial={ini}&dataFinal={fim}"
TIMEOUT_SEGUNDOS = 10
TENTATIVAS = 2
CASAS = 6

Buscador = Callable[[date, date], list[dict]]


class SelicIndisponivel(Exception):
    """O Banco Central não respondeu ou respondeu algo que não dá para usar."""


def buscar_bcb(inicio: date, fim: date) -> list[dict]:
    """Taxas diárias da série 11 entre `inicio` e `fim`: [{"data": "dd/mm/aaaa", "valor": "0.055131"}]."""
    url = URL_SGS11.format(ini=inicio.strftime("%d/%m/%Y"), fim=fim.strftime("%d/%m/%Y"))
    erro: Exception | None = None
    # A API do BC às vezes trava uma conexão e responde na seguinte: tenta duas vezes.
    for _ in range(TENTATIVAS):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_SEGUNDOS) as resp:
                return json.loads(resp.read())
        except Exception as exc:  # rede, timeout, HTTP ou JSON inválido: para o usuário é tudo "o BC não respondeu"
            erro = exc
    raise SelicIndisponivel(
        "Não foi possível buscar a SELIC no Banco Central: o site do BC não respondeu. "
        "Tente de novo em alguns minutos ou digite a SELIC à mão."
    ) from erro


def fatores_mensais(diarios: list[dict]) -> dict[tuple[int, int], float]:
    """{(ano, mês): fator do mês} a partir das taxas diárias da série 11."""
    fatores: dict[tuple[int, int], float] = defaultdict(lambda: 1.0)
    for d in diarios:
        dia = datetime.strptime(d["data"], "%d/%m/%Y")
        fatores[(dia.year, dia.month)] *= 1 + float(d["valor"]) / 100
    return dict(fatores)


def _ano_mes(periodo: str) -> tuple[int, int]:
    abrev, ano = periodo.split("/")
    return int(ano), abrev_para_numero(abrev)


def _validar_trimestre(meses: list[str]) -> list[tuple[int, int]]:
    try:
        am = [_ano_mes(p) for p in meses]
    except ValueError:
        raise ValueError(f"Período inválido: “{', '.join(meses)}”. Use os 3 meses do trimestre, por exemplo Jan/2026, Fev/2026 e Mar/2026.")
    ano, primeiro = am[0]
    if len(am) != 3 or primeiro % 3 != 1 or am != [(ano, primeiro + i) for i in range(3)]:
        raise ValueError(f"“{', '.join(meses)}” não é um trimestre civil. Use Jan–Mar, Abr–Jun, Jul–Set ou Out–Dez do mesmo ano.")
    return am


def fim_do_trimestre(meses: list[str]) -> date:
    ano, mes = _validar_trimestre(meses)[-1]
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def selic_acumulada(fatores: dict[tuple[int, int], float], meses: list[str]) -> dict[str, float]:
    """{período: % acumulada do mês até o fim do trimestre}, com 6 casas."""
    am = _validar_trimestre(meses)
    faltando = [p for p, chave in zip(meses, am) if chave not in fatores]
    if faltando:
        raise SelicIndisponivel(f"O Banco Central ainda não publicou a SELIC de {', '.join(faltando)}. Digite a SELIC à mão ou tente mais tarde.")
    resultado = {}
    for i, periodo in enumerate(meses):
        fator = 1.0
        for chave in am[i:]:
            fator *= fatores[chave]
        resultado[periodo] = round((fator - 1) * 100, CASAS)
    return resultado


def selic_do_trimestre(meses: list[str], hoje: date | None = None, buscar: Buscador = buscar_bcb) -> dict:
    """SELIC acumulada dos 3 meses do trimestre civil.

    Trimestre ainda não encerrado → `disponivel=False` e `fecha_em` (não usa SELIC parcial)."""
    hoje = hoje or date.today()
    fim = fim_do_trimestre(meses)
    if hoje <= fim:
        return {"disponivel": False, "valores": {}, "fecha_em": fim.isoformat(), "fonte": "Banco Central (série 11)"}
    ano, mes = _ano_mes(meses[0])
    valores = selic_acumulada(fatores_mensais(buscar(date(ano, mes, 1), fim)), meses)
    return {"disponivel": True, "valores": valores, "fecha_em": fim.isoformat(), "fonte": "Banco Central (série 11)"}
