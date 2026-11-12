"""Agregações extras do Dashboard: CGR por empresa, encargos RET por tipo e
volumes do CGF. Só leitura, direto das tabelas gravadas pelos módulos."""
from __future__ import annotations

import re
from collections import defaultdict

from Src.Database.database import DatabasePMPV

_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
_PERIODO = re.compile(r"^(" + "|".join(_MESES) + r")/(\d{4})$")
_MAX_TIPOS_RET = 3  # +"Outros": cores categóricas ficam distinguíveis


def _chave(periodo: str) -> tuple[int, int]:
    mes, ano = periodo.split("/")
    return int(ano), _MESES.index(mes)


def _no_filtro(periodo: str | None, ano: str | None) -> bool:
    if not periodo or not _PERIODO.match(periodo):
        return False
    return ano is None or periodo.endswith(f"/{ano}")


def _linhas(sql: str) -> list[dict]:
    with DatabasePMPV() as db:
        db.cursor.execute(sql)
        return [dict(r) for r in db.cursor.fetchall()]


def _nova_empresa() -> dict:
    return dict(notas=0, nfe=0, cte=0, valor_total=0.0, icms=0.0, pis_cofins=0.0, cgr_liquido=0.0)


def _ordenar_empresas(por_empresa: dict[str, dict]) -> list[dict]:
    return sorted(({"empresa": k, **v} for k, v in por_empresa.items()), key=lambda x: x["cgr_liquido"], reverse=True)


def empresas(ano: str | None) -> dict:
    """Totais por empresa do filtro e, em `meses`, as mesmas contas mês a mês
    (a tela agrupa em trimestre ou ano e escolhe o período)."""
    por_empresa: dict[str, dict] = defaultdict(_nova_empresa)
    por_mes: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(_nova_empresa))
    for r in _linhas("SELECT periodo, empresa, tipo, valor_total, icms, pis, cofins, cgr_liquido FROM auditoria_itens"):
        if not _no_filtro(r["periodo"], ano):
            continue
        nome = (r["empresa"] or "Sem empresa").strip() or "Sem empresa"
        cte = (r["tipo"] or "").upper().replace("-", "") == "CTE"
        for e in (por_empresa[nome], por_mes[r["periodo"]][nome]):
            e["notas"] += 1
            e["cte" if cte else "nfe"] += 1
            e["valor_total"] += r["valor_total"] or 0
            e["icms"] += r["icms"] or 0
            e["pis_cofins"] += (r["pis"] or 0) + (r["cofins"] or 0)
            e["cgr_liquido"] += r["cgr_liquido"] or 0
    lista = _ordenar_empresas(por_empresa)
    meses = [{"periodo": p, "empresas": _ordenar_empresas(por_mes[p])} for p in sorted(por_mes, key=_chave)]
    return {"ano_filtro": ano, "empresas": lista, "total_cgr_liquido": sum(x["cgr_liquido"] for x in lista),
            "meses": meses}


def ret(ano: str | None) -> dict:
    tipos_total: dict[str, float] = defaultdict(float)
    por_mes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in _linhas("SELECT periodo, tipo_encargo, valor_total FROM ret_itens"):
        if not _no_filtro(r["periodo"], ano):
            continue
        tipo = (r["tipo_encargo"] or "Sem tipo").strip() or "Sem tipo"
        v = r["valor_total"] or 0
        tipos_total[tipo] += v
        por_mes[r["periodo"]][tipo] += v
    ordenados = sorted(tipos_total, key=lambda t: tipos_total[t], reverse=True)
    principais = ordenados[:_MAX_TIPOS_RET]
    tem_outros = len(ordenados) > _MAX_TIPOS_RET
    tipos = principais + (["Outros"] if tem_outros else [])
    meses = []
    for p in sorted(por_mes, key=_chave):
        pt = {t: 0.0 for t in tipos}
        for tipo, v in por_mes[p].items():
            pt[tipo if tipo in principais else "Outros"] += v
        meses.append({"periodo": p, "total": sum(pt.values()), "por_tipo": pt})
    return {"ano_filtro": ano, "tipos": tipos, "meses": meses, "total": sum(m["total"] for m in meses)}


def volumes(ano: str | None) -> dict:
    campos = ("volume_faturado", "volume_devolucoes", "volume_canceladas", "volume_consumo_proprio", "volume_final")
    rows = [r for r in _linhas(
        "SELECT periodo, volume_faturado, volume_canceladas, volume_devolucoes, volume_consumo_proprio, volume_final FROM cgf_resumo"
    ) if _no_filtro(r["periodo"], ano)]
    rows.sort(key=lambda r: _chave(r["periodo"]))
    meses = [{"periodo": r["periodo"], **{c: float(r[c] or 0) for c in campos}} for r in rows]
    totais = {"periodo": "Total", **{c: sum(m[c] for m in meses) for c in campos}}
    return {"ano_filtro": ano, "meses": meses, "totais": totais}
