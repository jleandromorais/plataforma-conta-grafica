"""RET de uma pasta inteira — orquestração que antes ficava na tela desktop
(tela_ret.py) e agora também é usada pela API web. As regras de extração e
cálculo continuam em RegrasRET (servicos_ret.py).

Diferença para a tela antiga: os documentos são agrupados pelo mês de
referência de cada PDF (`mes_ref`, vindo do nome das pastas). A tela somava
tudo e gravava num único mês — escolher a pasta do trimestre (ex.:
"RET-jan-mar-26") juntava os 3 meses num só.
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

from Src.Services.servicos_ret import RegrasRET

_PASTAS_FORA_DO_RET = ("NOTAS FISCAIS", "NOTA FISCAL")


def processar_pasta(pasta: str | Path, log: Callable[[str], None] | None = None) -> tuple[list[dict], int, int]:
    """Lê os PDFs de encargos da pasta (e subpastas).

    Fica de fora: o que está em pastas "Notas Fiscais" e os PDFs que são nota
    fiscal pelo nome (NF, DANFE, CT-e). Retorna (documentos, qtd_lidos, qtd_ignorados).
    """
    dados: list[dict] = []
    lidos = ignorados = 0
    for raiz, _, arquivos in os.walk(pasta):
        pdfs = [f for f in arquivos if f.lower().endswith(".pdf")]
        if any(n in p.upper() for p in Path(raiz).parts for n in _PASTAS_FORA_DO_RET):
            ignorados += len(pdfs)
            continue
        for nome in sorted(pdfs):
            caminho = os.path.join(raiz, nome)
            if RegrasRET.extrair_tipo_nota(caminho) == "NF":
                ignorados += 1
                if log:
                    log(f"   [NF] Ignorado (Nota Fiscal): {nome}")
                continue
            if log:
                log(f"[PDF] Processando: {nome}")
            dados.append(RegrasRET.extrair_dados_pdf(caminho, log_callback=log))
            lidos += 1
    return dados, lidos, ignorados


def periodo_mais_comum(dados: list[dict]) -> str:
    refs = [d.get("mes_ref", "") for d in dados if d.get("mes_ref")]
    return Counter(refs).most_common(1)[0][0] if refs else ""


def agrupar_por_mes(dados: list[dict], periodo_padrao: str = "") -> dict[str, list[dict]]:
    """Documentos por mês de referência; sem mês detectado → `periodo_padrao`."""
    grupos: dict[str, list[dict]] = defaultdict(list)
    for d in dados:
        grupos[d.get("mes_ref") or periodo_padrao or "Sem mês"].append(d)
    return dict(grupos)


def salvar_meses(grupos: dict[str, list[dict]]) -> list[dict]:
    """Grava o RET de cada mês na consolidação e substitui os itens do mês."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao
    from Src.common.periodos import is_periodo_valido

    invalidos = [p for p in grupos if not is_periodo_valido(p)]
    if invalidos:
        raise ValueError(f"Documentos sem mês válido ({', '.join(invalidos)}): escolha o mês antes de salvar.")
    salvos = []
    with ServicosConsolidacao() as consolidacao, DatabasePMPV() as db:
        for periodo, docs in grupos.items():
            ret = RegrasRET.calcular_ret(docs)["ret"]
            consolidacao.salvar_ret(periodo, ret)
            db.salvar_ret_itens(periodo, docs)
            salvos.append({"periodo": periodo, "ret": ret, "qtd_documentos": len(docs)})
    return salvos


TOL_PROVA_REAL_RS = 1.0   # R$: abaixo disso é arredondamento


def prova_real(periodo: str) -> dict:
    """A conta do RET gravado do mês, aberta: refaz RET = EAT × (1 − PIS/COFINS) + EC com os
    itens gravados (a MESMA `RegrasRET.calcular_ret` do salvar) e compara com consolidacao.ret.
    NÃO grava nada. Itens fora de EAT/EC (Penalidades, TOP, Outros) não entram na conta."""
    from Src.Database.database import DatabasePMPV
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, "
                         "por exemplo Jan/2026.")
    with DatabasePMPV() as db:
        itens = db.listar_ret_itens(periodo) or []
        cons = db.buscar_consolidacao(periodo) or {}

    # valor_total pode vir vazio do banco: vira 0 para a conta não quebrar.
    docs = [{**i, "tipo_encargo": i.get("tipo_encargo") or "", "valor_total": float(i.get("valor_total") or 0.0)}
            for i in itens]
    calc = RegrasRET.calcular_ret(docs)
    tem_itens = bool(docs)
    ret_gravado = float(cons["ret"]) if cons.get("ret") is not None else None
    ret_calculado = float(calc["ret"]) if tem_itens else None
    diferenca = ret_calculado - ret_gravado if ret_calculado is not None and ret_gravado is not None else None

    por_empresa: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0, 0.0])
    for d in calc["eat_docs"] + calc["ec_docs"]:
        acc = por_empresa[(d.get("empresa") or "", d["tipo_encargo"])]
        acc[0] += 1
        acc[1] += d["valor_total"]
    linhas = [{"empresa": e, "tipo_encargo": t, "qtd": q, "valor": v} for (e, t), (q, v) in por_empresa.items()]
    linhas.sort(key=lambda x: x["valor"], reverse=True)

    return {
        "periodo": periodo,
        "tem_itens": tem_itens,
        "qtd_documentos": len(docs),
        "qtd_eat": len(calc["eat_docs"]),
        "qtd_ec": len(calc["ec_docs"]),
        "qtd_outros": len(calc["outros_docs"]),
        "eat_bruto": float(calc["eat_bruto"]),
        "pis_cofins_rate": float(calc["pis_cofins_rate"]),
        "eat_liquido": float(calc["eat_bruto"]) * (1.0 - calc["pis_cofins_rate"]),
        "ec": float(calc["ec_docs_total"]),
        "ret_calculado": ret_calculado,
        "ret_gravado": ret_gravado,
        "diferenca": diferenca,
        "confere": tem_itens and diferenca is not None and abs(diferenca) <= TOL_PROVA_REAL_RS,
        "por_empresa": linhas,
        "data_atualizacao": (cons.get("data_atualizacao") or "")[:16],
    }


def historico() -> list[dict]:
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        linhas = []
        for periodo in db.listar_periodos_ret():
            itens = db.listar_ret_itens(periodo) or []
            cons = db.buscar_consolidacao(periodo) or {}
            linhas.append({
                "periodo": periodo,
                "qtd_documentos": len(itens),
                "ret_gravado": float(cons.get("ret") or 0.0),
                "data_atualizacao": (cons.get("data_atualizacao") or "")[:16],
            })
    from Src.common.periodos import ordenar_historico
    return ordenar_historico(linhas)
