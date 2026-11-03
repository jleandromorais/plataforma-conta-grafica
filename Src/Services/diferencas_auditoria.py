"""Onde o CGR processado difere do que está gravado no mês.

Compara as notas recém-auditadas com as notas gravadas (`auditoria_itens`),
por supridor e nota a nota, com o mesmo CGR por nota da gravação
(`cgr_liquido_item`, só o que integra o CGR). Serve para meses sem as notas na
planilha do Alexandre (ex.: Jul/26): o gravado é a referência que existe.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from Src.Services.comparador_conta_grafica import _normalizar_numero_nota
from Src.Services.explicador_diferencas import TOL_VALOR, brl
from Src.Services.servicos_auditoria import XMLItem, empresa_integra_cgr
from Src.Services.servicos_auditoria_lote import cgr_liquido_item, integra_cgr
from Src.Services.supridores import supridor_canonico

MAX_NOTAS = 15


def _chave(empresa: str, tipo: str, numero: Any, valor_total: float) -> tuple:
    num = _normalizar_numero_nota(numero).lstrip("0")
    # OCR sem número ("0", "N/A"): casa pelo valor da nota.
    return (supridor_canonico(empresa), tipo, num or f"valor {round(float(valor_total or 0), 2):.2f}")


def _numero(chave: tuple) -> str:
    """Número para a tela; nota casada pelo valor (OCR sem número) vira "s/nº"."""
    return "s/nº" if chave[2].startswith("valor ") else chave[2]


def _juntar(linhas: list[tuple[tuple, float, bool]]) -> dict[tuple, dict]:
    out: dict[tuple, dict] = defaultdict(lambda: {"cgr": 0.0, "ocr": False})
    for chave, cgr, ocr in linhas:
        out[chave]["cgr"] += cgr
        out[chave]["ocr"] |= ocr
    return out


def comparar_com_gravado(itens: list[XMLItem], gravados: list[dict], cgr_gravado: float | None = None) -> dict:
    """`cgr_gravado`: CGR do mês na consolidação. Se as notas gravadas não somam
    esse valor, foram gravadas com uma regra antiga e o resumo avisa."""
    if not gravados:
        return _sem_notas_gravadas(itens)
    novos = _juntar([
        (_chave(i.empresa, i.tipo, i.numero, i.valor_total), cgr_liquido_item(i), str(i.status).upper() == "OCR")
        for i in itens if integra_cgr(i)
    ])
    antigos = _juntar([
        (_chave(g.get("empresa", ""), g.get("tipo", ""), g.get("numero", ""), g.get("valor_total", 0.0)),
         float(g.get("cgr_liquido") or 0.0), False)
        for g in gravados if g.get("tipo") == "NF-e" or empresa_integra_cgr(g.get("empresa", ""))
    ])

    notas, por_empresa = [], defaultdict(lambda: [0.0, 0.0])
    for chave in set(novos) | set(antigos):
        novo, antigo = novos.get(chave), antigos.get(chave)
        v_novo, v_antigo = (novo or {}).get("cgr", 0.0), (antigo or {}).get("cgr", 0.0)
        por_empresa[chave[0]][0] += v_antigo
        por_empresa[chave[0]][1] += v_novo
        if abs(v_novo - v_antigo) <= TOL_VALOR:
            continue
        situacao = "so_no_gravado" if novo is None else "so_no_processado" if antigo is None else "valor_diferente"
        notas.append({
            "empresa": chave[0], "tipo": chave[1], "numero": _numero(chave), "situacao": situacao,
            "gravado": v_antigo, "processado": v_novo, "diferenca": v_novo - v_antigo,
            "ocr": bool((novo or {}).get("ocr")),
        })
    notas.sort(key=lambda n: -abs(n["diferenca"]))
    empresas = sorted(
        ({"empresa": e, "gravado": g, "processado": p, "diferenca": p - g}
         for e, (g, p) in por_empresa.items() if abs(p - g) > TOL_VALOR),
        key=lambda e: -abs(e["diferenca"]),
    )
    total_novo = sum(v["cgr"] for v in novos.values())
    total_antigo = sum(v["cgr"] for v in antigos.values())
    return {
        "tem_notas_gravadas": bool(gravados),
        "cgr_gravado_notas": total_antigo,
        "cgr_processado": total_novo,
        "diferenca": total_novo - total_antigo,
        "por_empresa": empresas,
        "notas": notas[:MAX_NOTAS],
        "qtd_notas_diferentes": len(notas),
        "resumo": _aviso_notas_antigas(total_antigo, cgr_gravado) + _resumo(empresas, notas),
    }


def _aviso_notas_antigas(soma_notas: float, cgr_gravado: float | None) -> list[str]:
    if cgr_gravado is None or abs(soma_notas - cgr_gravado) <= TOL_VALOR:
        return []
    return [f"Atenção: as notas gravadas somam {brl(soma_notas)}, mas o CGR gravado é {brl(cgr_gravado)}. "
            "Elas foram gravadas com uma regra antiga; a comparação nota a nota pode apontar diferenças que já não existem."]


def _sem_notas_gravadas(itens: list[XMLItem]) -> dict:
    """Mês gravado só com o total (ex.: copiado da planilha): não há nota para
    comparar. Mostra o CGR por empresa e as notas lidas por OCR, as primeiras a
    conferir contra a planilha."""
    do_cgr = [i for i in itens if integra_cgr(i)]
    por_emp: dict[str, float] = defaultdict(float)
    for i in do_cgr:
        por_emp[supridor_canonico(i.empresa)] += cgr_liquido_item(i)
    ocr = sorted((i for i in do_cgr if str(i.status).upper() == "OCR"), key=lambda i: -abs(cgr_liquido_item(i)))
    notas = [{
        "empresa": supridor_canonico(i.empresa), "tipo": i.tipo, "numero": _numero(_chave(i.empresa, i.tipo, i.numero, i.valor_total)),
        "situacao": "so_no_processado", "gravado": 0.0, "processado": cgr_liquido_item(i),
        "diferenca": cgr_liquido_item(i), "ocr": True,
    } for i in ocr]
    total = sum(por_emp.values())
    resumo = ["O mês está gravado só com o total, sem as notas: não dá para apontar a nota que difere."]
    if ocr:
        resumo.append(f"Confira primeiro as {len(ocr)} nota(s) lidas por OCR (somam {brl(sum(n['processado'] for n in notas))}): "
                      "é onde costuma estar o erro de leitura.")
    resumo.append("CGR por empresa agora: " + " · ".join(f"{e} {brl(v)}" for e, v in sorted(por_emp.items(), key=lambda x: -x[1])))
    return {
        "tem_notas_gravadas": False, "cgr_gravado_notas": 0.0, "cgr_processado": total, "diferenca": 0.0,
        "por_empresa": [{"empresa": e, "gravado": 0.0, "processado": v, "diferenca": 0.0} for e, v in sorted(por_emp.items())],
        "notas": notas[:MAX_NOTAS], "qtd_notas_diferentes": len(notas), "resumo": resumo,
    }


_SITUACAO = {
    "so_no_gravado": "está no gravado e não veio agora",
    "so_no_processado": "veio agora e não está no gravado",
    "valor_diferente": "valor diferente",
}


def _resumo(empresas: list[dict], notas: list[dict]) -> list[str]:
    if not notas:
        return ["As notas batem com as gravadas."]
    linhas = []
    for e in empresas[:3]:
        daqui = [n for n in notas if n["empresa"] == e["empresa"]][:2]
        detalhe = "; ".join(
            f"{'NF' if n['tipo'] == 'NF-e' else 'CT-e'} {n['numero']} {_SITUACAO[n['situacao']]} ({brl(n['diferenca'])}"
            f"{', lida por OCR' if n['ocr'] else ''})"
            for n in daqui
        )
        linhas.append(f"{e['empresa']}: {brl(e['diferenca'])}" + (f" — {detalhe}" if detalhe else ""))
    return linhas
