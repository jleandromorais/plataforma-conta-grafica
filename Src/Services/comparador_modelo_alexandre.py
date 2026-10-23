"""Comparação da auditoria CGR com o modelo de Conta Gráfica do Alexandre
("Novo modelo Alexandre Conta gráfica - Calculador - revN.xlsx").

O modelo tem um layout fixo, então é lido de forma determinística (sem
adivinhar colunas como o comparador genérico):

- aba "Custo do Gás Realizado - NFs": blocos mensais. Cada bloco começa numa
  linha "MÊS | JUN-2026", seguida do cabeçalho e de uma linha por nota:
  A=Supridor, B=Nota Fiscal, C=Vol m³, D=Compra c/tributos,
  E=Compra s/tributos, G=alíquota ICMS. Linhas sem número de nota (resumo por
  supridor, linhas vazias com fórmula) são ignoradas.
- aba "Conta Gráfica": linha "CGR" da apuração mensal, uma coluna por mês.
  Cobre meses que ainda não têm as notas detalhadas na aba de NFs.

A comparação casa as notas por (supridor, número) e aponta, nota a nota, o que
diverge: presença, CGR (s/tributos), valor c/tributos, volume e alíquota.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from Src.common.periodos import normalizar_periodo
from Src.Services.comparador_conta_grafica import ResultadoComparacaoNotas, _normalizar_numero_nota
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem, empresa_integra_cgr

ABA_NOTAS = "custodogasrealizadonfs"
ABA_CONTA = "contagrafica"

# Tolerâncias: abaixo disso é arredondamento, não divergência.
TOL_VALOR = 1.00      # R$
TOL_VOLUME = 1.0      # m³
TOL_ALIQUOTA = 0.0005

# Nome canônico do supridor. A primeira palavra-chave encontrada no nome
# (pasta da auditoria ou coluna "Supridor" da planilha) define o grupo.
_SUPRIDORES = (
    ("brava", "Brava"), ("3r", "Brava"),
    ("eneva", "Eneva"),
    ("galp", "Galp"),
    ("gnllink", "GNLink"), ("gnlink", "GNLink"), ("gnl", "GNLink"),
    ("orizon", "Orizon"),
    ("petroreconcavo", "Petrorecôncavo"),
    ("petrobras", "Petrobras"),
    ("mastergas", "Mastergás"),
    ("shell", "Shell"),
    ("tag", "TAG"),
    ("cegas", "Cegás"),
    ("sergas", "Sergás"),
    ("vector", "GNC Vector"),
)


def _token(texto: Any) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", limpo.lower())


def supridor_canonico(nome: Any) -> str:
    tok = _token(nome)
    for chave, canon in _SUPRIDORES:
        if chave in tok:
            return canon
    return str(nome or "").strip() or "?"


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _periodo_bloco(valor: Any) -> str:
    """'JUN-2026', 'jun/26', datetime(2026,6,1) → 'Jun/2026'."""
    if isinstance(valor, (datetime, date)):
        return normalizar_periodo(f"{valor.month:02d}/{valor.year}")
    m = re.fullmatch(r"\s*([A-Za-zÀ-ÿ]{3})[A-Za-zÀ-ÿ]*\s*[-/ .]\s*(\d{2}|\d{4})\s*", str(valor or ""))
    if not m:
        return ""
    ano = m.group(2) if len(m.group(2)) == 4 else f"20{m.group(2)}"
    try:
        return normalizar_periodo(f"{m.group(1).capitalize()}/{ano}")
    except ValueError:
        return ""


@dataclass
class NotaPlanilha:
    linha: int
    supridor: str          # como está na planilha
    empresa: str           # canônico
    numero: str            # como está na planilha
    numero_normalizado: str
    volume: float
    valor_com_tributos: float
    valor_sem_tributos: float
    aliquota_icms: float | None


@dataclass
class ModeloAlexandre:
    notas: dict[str, list[NotaPlanilha]] = field(default_factory=dict)   # período → notas
    cgr_conta_grafica: dict[str, float] = field(default_factory=dict)   # período → CGR da aba Conta Gráfica

    @property
    def periodos_com_notas(self) -> list[str]:
        return list(self.notas)


def _achar_aba(wb, alvo: str):
    for nome in wb.sheetnames:
        if _token(nome).startswith(alvo):
            return wb[nome]
    return None


def _ler_notas(ws) -> dict[str, list[NotaPlanilha]]:
    notas: dict[str, list[NotaPlanilha]] = {}
    periodo = ""
    for idx, row in enumerate(ws.iter_rows(max_col=7, values_only=True), start=1):
        row = tuple(row) + (None,) * (7 - len(row))
        a, b, c, d, e, _f, g = row[:7]
        if _token(a) == "mes":
            periodo = _periodo_bloco(b)
            if periodo:
                notas.setdefault(periodo, [])
            continue
        if not periodo or a is None or b is None:
            continue
        if _token(a) == "supridor" or _token(b).startswith("nota"):
            continue  # cabeçalho
        numero_norm = _normalizar_numero_nota(b)
        sem = _num(e)
        if not numero_norm or sem is None:
            continue
        notas[periodo].append(NotaPlanilha(
            linha=idx,
            supridor=str(a).strip(),
            empresa=supridor_canonico(a),
            numero=str(b).strip(),
            numero_normalizado=numero_norm,
            volume=_num(c) or 0.0,
            valor_com_tributos=_num(d) or 0.0,
            valor_sem_tributos=sem,
            aliquota_icms=_num(g),
        ))
    return notas


def _ler_cgr_conta_grafica(ws) -> dict[str, float]:
    """Linha 'CGR' da apuração mensal; períodos vêm da linha 'DADOS' acima dela."""
    datas: tuple | None = None
    for row in ws.iter_rows(max_row=60, values_only=True):
        rotulo = _token(row[0] if row else None)
        if rotulo == "dados" and datas is None:
            if sum(isinstance(v, (datetime, date)) for v in row) >= 3:
                datas = row
            continue
        if rotulo == "cgr" and datas is not None:
            out: dict[str, float] = {}
            for dt, v in zip(datas, row):
                valor = _num(v)
                if isinstance(dt, (datetime, date)) and valor:
                    out[normalizar_periodo(f"{dt.month:02d}/{dt.year}")] = valor
            return out
    return {}


def ler_modelo(caminho: str) -> ModeloAlexandre | None:
    """Lê o modelo do Alexandre. Devolve None se o arquivo não segue esse layout
    (aí o chamador usa o comparador genérico)."""
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        ws_notas = _achar_aba(wb, ABA_NOTAS)
        if ws_notas is None:
            return None
        notas = _ler_notas(ws_notas)
        if not notas:
            return None
        ws_conta = _achar_aba(wb, ABA_CONTA)
        cgr = _ler_cgr_conta_grafica(ws_conta) if ws_conta is not None else {}
        return ModeloAlexandre(notas=notas, cgr_conta_grafica=cgr)
    finally:
        wb.close()


# ── Comparação ───────────────────────────────────────────────────────────────

def _chave(empresa: str, numero_norm: str) -> tuple[str, str]:
    return (supridor_canonico(empresa), numero_norm)


def _agrupar_auditoria(itens: list[XMLItem]) -> dict[tuple[str, str], dict]:
    """Soma por (supridor, nota) os documentos que entram no CGR. Devolução
    entra negativa, como no CGR líquido."""
    out: dict[tuple[str, str], dict] = {}
    for it in itens:
        if not (it.tipo == "NF-e" or empresa_integra_cgr(it.empresa)):
            continue  # frete de outras transportadoras: fora do CGR e fora da planilha
        numero_norm = _normalizar_numero_nota(it.numero)
        if not numero_norm:
            continue
        devolucao = "devol" in _token(it.caminho)
        sinal = -1.0 if devolucao else 1.0
        g = out.setdefault(_chave(it.empresa, numero_norm), {
            "empresa": supridor_canonico(it.empresa), "empresa_pasta": it.empresa, "tipo": it.tipo,
            "numero": str(it.numero), "numero_normalizado": numero_norm,
            "cgr": 0.0, "valor_com_tributos": 0.0, "volume": 0.0, "aliquotas": set(), "qtd": 0,
        })
        g["cgr"] += sinal * RegrasAuditoria.calcular_s_tributos(it.valor_total, it.icms_taxa)
        g["valor_com_tributos"] += sinal * float(it.valor_total)
        g["volume"] += sinal * float(it.volume_total or it.volume or 0)
        if it.icms_taxa:
            g["aliquotas"].add(round(float(it.icms_taxa), 4))
        g["qtd"] += 1
    return out


def _agrupar_planilha(notas: list[NotaPlanilha]) -> dict[tuple[str, str], dict]:
    out: dict[tuple[str, str], dict] = {}
    for n in notas:
        g = out.setdefault((n.empresa, n.numero_normalizado), {
            "empresa": n.empresa, "supridor": n.supridor, "numero": n.numero,
            "numero_normalizado": n.numero_normalizado, "linhas": [],
            "cgr": 0.0, "valor_com_tributos": 0.0, "volume": 0.0, "aliquotas": set(),
        })
        g["linhas"].append(n.linha)
        g["cgr"] += n.valor_sem_tributos
        g["valor_com_tributos"] += n.valor_com_tributos
        g["volume"] += n.volume
        if n.aliquota_icms:
            g["aliquotas"].add(round(n.aliquota_icms, 4))
    return out


def _divergencias_da_nota(aud: dict, pla: dict) -> list[str]:
    motivos: list[str] = []
    if abs(aud["cgr"] - pla["cgr"]) > TOL_VALOR:
        motivos.append("CGR (s/ tributos)")
    if pla["valor_com_tributos"] and abs(aud["valor_com_tributos"] - pla["valor_com_tributos"]) > TOL_VALOR:
        motivos.append("valor c/ tributos")
    # Volume: CT-e de transporte não tem volume na planilha.
    if pla["volume"] and abs(aud["volume"] - pla["volume"]) > TOL_VOLUME:
        motivos.append("volume")
    if aud["aliquotas"] and pla["aliquotas"] and not any(
        abs(a - p) <= TOL_ALIQUOTA for a in aud["aliquotas"] for p in pla["aliquotas"]
    ):
        motivos.append("alíquota ICMS")
    if len(pla["linhas"]) > 1:
        motivos.append(f"nota repetida na planilha ({len(pla['linhas'])}x)")
    if aud["qtd"] > 1:
        motivos.append(f"nota repetida na auditoria ({aud['qtd']}x)")
    return motivos


def _fmt_aliq(aliqs: set[float]) -> str:
    return ", ".join(f"{a * 100:g}%" for a in sorted(aliqs))


def comparar(itens: list[XMLItem], modelo: ModeloAlexandre, periodo: str) -> ResultadoComparacaoNotas:
    periodo_norm = normalizar_periodo(periodo)
    if not periodo_norm:
        raise ValueError("Período inválido. Escreva o mês e o ano, por exemplo Jan/2026 ou 01/2026.")

    aud = _agrupar_auditoria(itens)
    cgr_auditoria = sum(g["cgr"] for g in aud.values())
    cgr_conta = modelo.cgr_conta_grafica.get(periodo_norm)
    avisos: list[str] = []

    notas_mes = modelo.notas.get(periodo_norm)
    if notas_mes is None:
        meses = modelo.periodos_com_notas
        ultimo = meses[-1] if meses else "—"
        avisos.append(
            f"A aba 'Custo do Gás Realizado - NFs' não tem as notas de {periodo_norm} "
            f"(as notas detalhadas vão até {ultimo}). Comparei só o CGR total com a aba 'Conta Gráfica'."
        )
        if cgr_conta is None:
            avisos.append(f"A aba 'Conta Gráfica' também não tem CGR para {periodo_norm}.")
        _aviso_total(avisos, "aba 'Conta Gráfica'", cgr_auditoria, cgr_conta)
        return ResultadoComparacaoNotas(
            periodo=periodo_norm, coluna_nota_excel="B (Nota Fiscal)", coluna_periodo_excel=None,
            total_nossa_base=len(aud), total_conta_grafica=0, qtd_em_ambas=0,
            notas_apenas_nossa=[], notas_apenas_conta_grafica=[], linhas_sem_numero_excel=[],
            avisos=avisos, sheets_excel=["Custo do Gás Realizado - NFs", "Conta Gráfica"],
            sheets_periodo_match=["Conta Gráfica"] if cgr_conta is not None else [],
            total_linhas_periodo=0,
            modelo="alexandre", cgr_auditoria=cgr_auditoria, cgr_planilha_notas=None,
            cgr_planilha_conta_grafica=cgr_conta, notas_mes_na_planilha=False,
        )

    pla = _agrupar_planilha(notas_mes)
    cgr_planilha = sum(g["cgr"] for g in pla.values())

    apenas_aud = [k for k in aud if k not in pla]
    apenas_pla = [k for k in pla if k not in aud]
    ambas = [k for k in aud if k in pla]

    divergencias: list[dict[str, Any]] = []
    for k in ambas:
        a, p = aud[k], pla[k]
        motivos = _divergencias_da_nota(a, p)
        if motivos:
            divergencias.append({
                "empresa": a["empresa"], "tipo": a["tipo"], "numero": a["numero"],
                "numero_planilha": p["numero"], "linha_excel": p["linhas"][0],
                "motivos": motivos,
                "cgr_auditoria": round(a["cgr"], 2), "cgr_planilha": round(p["cgr"], 2),
                "diferenca_cgr": round(a["cgr"] - p["cgr"], 2),
                "valor_auditoria": round(a["valor_com_tributos"], 2),
                "valor_planilha": round(p["valor_com_tributos"], 2),
                "volume_auditoria": round(a["volume"], 2), "volume_planilha": round(p["volume"], 2),
                "aliquota_auditoria": _fmt_aliq(a["aliquotas"]), "aliquota_planilha": _fmt_aliq(p["aliquotas"]),
            })
    divergencias.sort(key=lambda d: -abs(d["diferenca_cgr"]))

    notas_apenas_nossa = sorted((
        {"empresa": aud[k]["empresa"], "tipo": aud[k]["tipo"], "numero": aud[k]["numero"],
         "numero_normalizado": k[1], "valor_total": round(aud[k]["valor_com_tributos"], 2),
         "cgr_liquido": round(aud[k]["cgr"], 2), "icms": 0.0}
        for k in apenas_aud), key=lambda d: -abs(d["cgr_liquido"]))
    notas_apenas_planilha = sorted((
        {"empresa": pla[k]["empresa"], "supridor": pla[k]["supridor"], "numero": pla[k]["numero"],
         "numero_normalizado": k[1], "linha_excel": pla[k]["linhas"][0],
         "periodo_linha": periodo_norm, "cgr_planilha": round(pla[k]["cgr"], 2),
         "valor_planilha": round(pla[k]["valor_com_tributos"], 2),
         "dados_linha": {"Supridor": pla[k]["supridor"], "Nota Fiscal": pla[k]["numero"],
                         "Vol m³": pla[k]["volume"], "Compra c/tributos": pla[k]["valor_com_tributos"],
                         "Compra s/tributos": pla[k]["cgr"]}}
        for k in apenas_pla), key=lambda d: -abs(d["cgr_planilha"]))

    por_empresa = _resumo_por_empresa(aud, pla)

    if aud and len(ambas) < len(aud) / 2:
        sugerido = _mes_mais_provavel(aud, modelo)
        if sugerido and sugerido[0] != periodo_norm:
            avisos.append(
                f"Mês provavelmente errado: só {len(ambas)} de {len(aud)} notas auditadas estão em "
                f"{periodo_norm} na planilha, mas {sugerido[1]} estão em {sugerido[0]}. Confira o mês selecionado."
            )

    _aviso_total(avisos, "notas da planilha", cgr_auditoria, cgr_planilha)
    if cgr_conta is not None and abs(cgr_conta - cgr_planilha) > TOL_VALOR:
        avisos.append(
            f"Na própria planilha, o CGR da aba 'Conta Gráfica' ({_brl(cgr_conta)}) difere da soma das "
            f"notas de {periodo_norm} ({_brl(cgr_planilha)}) em {_brl(cgr_conta - cgr_planilha)}."
        )

    return ResultadoComparacaoNotas(
        periodo=periodo_norm, coluna_nota_excel="B (Nota Fiscal)", coluna_periodo_excel=None,
        total_nossa_base=len(aud), total_conta_grafica=len(pla), qtd_em_ambas=len(ambas),
        notas_apenas_nossa=notas_apenas_nossa, notas_apenas_conta_grafica=notas_apenas_planilha,
        linhas_sem_numero_excel=[], avisos=avisos,
        sheets_excel=["Custo do Gás Realizado - NFs", "Conta Gráfica"],
        sheets_periodo_match=[f"Custo do Gás Realizado - NFs ({periodo_norm})"],
        total_linhas_periodo=len(notas_mes),
        modelo="alexandre", divergencias_valor=divergencias, por_empresa=por_empresa,
        cgr_auditoria=cgr_auditoria, cgr_planilha_notas=cgr_planilha,
        cgr_planilha_conta_grafica=cgr_conta, notas_mes_na_planilha=True,
    )


def _mes_mais_provavel(aud: dict, modelo: ModeloAlexandre) -> tuple[str, int] | None:
    """Mês da planilha com mais notas em comum com a auditoria."""
    chaves = set(aud)
    melhor = max(
        ((per, len(chaves & {(n.empresa, n.numero_normalizado) for n in notas})) for per, notas in modelo.notas.items()),
        key=lambda x: x[1], default=None,
    )
    return melhor if melhor and melhor[1] > 0 else None


def _resumo_por_empresa(aud: dict, pla: dict) -> list[dict[str, Any]]:
    acc: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "qtd_auditoria": 0, "qtd_planilha": 0, "cgr_auditoria": 0.0, "cgr_planilha": 0.0,
    })
    for g in aud.values():
        acc[g["empresa"]]["qtd_auditoria"] += 1
        acc[g["empresa"]]["cgr_auditoria"] += g["cgr"]
    for g in pla.values():
        acc[g["empresa"]]["qtd_planilha"] += 1
        acc[g["empresa"]]["cgr_planilha"] += g["cgr"]
    linhas = []
    for empresa, v in acc.items():
        dif = v["cgr_auditoria"] - v["cgr_planilha"]
        linhas.append({"empresa": empresa, **{k: (round(x, 2) if isinstance(x, float) else x) for k, x in v.items()},
                       "diferenca": round(dif, 2), "confere": abs(dif) <= TOL_VALOR and v["qtd_auditoria"] == v["qtd_planilha"]})
    linhas.sort(key=lambda r: (r["confere"], -abs(r["diferenca"])))
    return linhas


def _brl(v: float) -> str:
    txt = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}R$ {txt}"


def _aviso_total(avisos: list[str], fonte: str, auditoria: float, planilha: float | None) -> None:
    if planilha is None:
        return
    dif = auditoria - planilha
    if abs(dif) <= TOL_VALOR:
        avisos.append(f"CGR confere com a planilha ({fonte}): {_brl(auditoria)}.")
        return
    pct = f" ({dif / planilha * 100:+.2f}%)" if planilha else ""
    avisos.append(
        f"CGR DIVERGENTE: auditoria {_brl(auditoria)} × planilha ({fonte}) {_brl(planilha)} "
        f"→ diferença de {_brl(dif)}{pct}."
    )
