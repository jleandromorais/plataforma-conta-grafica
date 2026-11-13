"""Comparação da auditoria CGR com a planilha "Conta Gráfica e Apuração de Custos".

Layout (uma aba por mês, nomeada "Jul26", "Ago26"...):

- cabeçalho na linha com "Mês | Supridor | Nota Fiscal | Vol m³ | Compra R$ c/tributos |
  Compra R$ s/tributos | Custo | ICMS (alíquota) | ...", seguido de uma linha por nota;
- aba "Conta Gráfica": uma coluna por mês (datas na linha de cima) e a linha
  "Custo do Gás Realizado" com o CGR do mês.

As notas viram o mesmo modelo do Alexandre (nota a nota), então a comparação
— presença, CGR, valor, volume, alíquota e o porquê das diferenças — é a mesma
(`comparador_modelo_alexandre.comparar`). O mês escolhido pelo usuário define a aba.
"""
from __future__ import annotations

import re

from Src.Services.comparacao.comparador_conta_grafica import _normalizar_numero_nota
from Src.Services.comparacao.comparador_modelo_alexandre import (
    ModeloAlexandre, NotaPlanilha, _achar_aba, _num, _periodo_bloco, abas_por_periodo, comparar as _comparar_notas,
    conferir_mes as _conferir_mes,
)
from Src.Services.supridores import supridor_canonico, token as _token

ABA_CONTA = "contagrafica"
ROTULO_CGR = "custodogasrealizado"
_ABA_MES_RE = re.compile(r"^[a-z]{3}\d{2}$")   # token da aba: "jul26"


def _colunas(cabecalho: tuple) -> dict[str, int] | None:
    """Colunas pelo texto do cabeçalho; None se a linha não é o cabeçalho das notas."""
    cols: dict[str, int] = {}
    for i, v in enumerate(cabecalho):
        t = _token(v)
        if t == "supridor":
            cols["supridor"] = i
        elif t == "notafiscal":
            cols["nota"] = i
        elif t == "volm3":
            cols["volume"] = i
        elif t.startswith("comprarctributos"):
            cols["com"] = i
        elif t.startswith("comprarstributos"):
            cols["sem"] = i
        elif t == "icms" and "aliquota" not in cols:
            cols["aliquota"] = i   # a 1ª coluna ICMS é a alíquota; a 2ª é o valor em R$
    return cols if {"supridor", "nota", "sem"} <= cols.keys() else None


def _ler_aba_mes(ws) -> list[NotaPlanilha]:
    cols: dict[str, int] | None = None
    notas: list[NotaPlanilha] = []
    for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        if cols is None:
            if idx > 60:
                break   # cabeçalho não está no topo: não é uma aba de notas
            cols = _colunas(row)
            continue

        def cel(nome: str):
            i = cols.get(nome)
            return row[i] if i is not None and i < len(row) else None

        numero = cel("nota")
        sem = _num(cel("sem"))
        numero_norm = _normalizar_numero_nota(numero) if numero is not None else ""
        if not numero_norm or sem is None:
            continue   # linha de reserva (zeros) ou sem número
        supridor = str(cel("supridor") or "").strip()
        notas.append(NotaPlanilha(
            linha=idx, supridor=supridor, empresa=supridor_canonico(supridor),
            numero=str(numero).strip(), numero_normalizado=numero_norm,
            volume=_num(cel("volume")) or 0.0, valor_com_tributos=_num(cel("com")) or 0.0,
            valor_sem_tributos=sem, aliquota_icms=_num(cel("aliquota")),
        ))
    return notas


def _periodo_da_aba(nome: str) -> str:
    """'Jul26' → 'Jul/2026'; outra coisa → ''."""
    t = _token(nome)
    return _periodo_bloco(f"{t[:3]}-{t[3:]}") if _ABA_MES_RE.match(t) else ""


def _ler_cgr_mensal(ws) -> dict[str, float]:
    """Linha 'Custo do Gás Realizado' da aba Conta Gráfica; meses vêm da linha de datas."""
    from datetime import date, datetime

    datas: tuple | None = None
    for row in ws.iter_rows(max_row=60, values_only=True):
        if datas is None:
            if sum(isinstance(v, (datetime, date)) for v in row) >= 12:
                datas = row
            continue
        if any(_token(v).startswith(ROTULO_CGR) for v in row[:4] if isinstance(v, str)):
            out: dict[str, float] = {}
            for dt, v in zip(datas, row):
                valor = _num(v)
                if isinstance(dt, (datetime, date)) and valor:
                    out[_periodo_bloco(dt)] = valor
            return out
    return {}


def ler_modelo(caminho: str) -> ModeloAlexandre | None:
    """Lê a planilha. Devolve None se não tiver abas mensais com notas (aí tenta o próximo modelo)."""
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        notas = {}
        aba_das_notas: dict[str, str] = {}
        for nome in wb.sheetnames:
            periodo = _periodo_da_aba(nome)
            if periodo:
                lidas = _ler_aba_mes(wb[nome])
                if lidas:
                    notas[periodo] = lidas
                    aba_das_notas[periodo] = nome
        if not notas:
            return None
        ws_conta = _achar_aba(wb, ABA_CONTA)
        cgr = _ler_cgr_mensal(ws_conta) if ws_conta is not None else {}
        abas = abas_por_periodo(aba_das_notas, cgr, ws_conta.title if ws_conta is not None else "")
        return ModeloAlexandre(notas=notas, cgr_conta_grafica=cgr, aba_notas="abas mensais", aba_cgr="Conta Gráfica",
                               abas_periodo=abas)
    finally:
        wb.close()


comparar = _comparar_notas
conferir_mes = _conferir_mes
