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
