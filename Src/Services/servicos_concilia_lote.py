"""Conciliação RP (penalidades) — orquestração usada pela API web, com as
mesmas regras da tela desktop (tela_concilia.py) via RegrasConcilia.

RP (saldo de penalidade) = Σ despesas − Σ receitas — mesma fórmula da planilha
oficial "Conta Gráfica" (linha "Saldo de penalidade") e do que a tela desktop
grava. Notas "cancelado" entram negativas (RegrasConcilia).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from Src.Services.servicos_concilia import PdfItem, RegrasConcilia


def pdfs_da_pasta(pasta: Path | None) -> list[Path]:
    return sorted(pasta.rglob("*.pdf"), key=str) + sorted(pasta.rglob("*.PDF"), key=str) if pasta and pasta.exists() else []


def processar(pasta_receitas: Path | None, pasta_despesas: Path | None,
              log: Callable[[str], None] | None = None) -> list[PdfItem]:
    log = log or (lambda _msg: None)
    itens: list[PdfItem] = []
    rec = pdfs_da_pasta(pasta_receitas)
    desp = pdfs_da_pasta(pasta_despesas)
    if rec:
        log("--- Receitas ---")
        itens += RegrasConcilia.processar_arquivos(rec, "Receita", log)
    if desp:
        log("--- Despesas ---")
        itens += RegrasConcilia.processar_arquivos(desp, "Despesa", log)
    return itens


def totais(itens: list[PdfItem]) -> dict:
    receitas = sum(i.amount for i in itens if i.category == "Receita")
    despesas = sum(i.amount for i in itens if i.category == "Despesa")
    return {
        "total_receitas": receitas,
        "total_despesas": despesas,
        "rp": despesas - receitas,
        "qtd_revisar": sum(1 for i in itens if i.status != "OK"),
    }


def salvar(periodo: str, itens: list[PdfItem]) -> dict:
    """Grava o RP do período (consolidação) e substitui os itens do período."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"Período inválido: {periodo!r}. Use o formato Jan/2026.")
    if not itens:
        raise ValueError("Nenhum PDF conciliado para salvar.")
    rp = totais(itens)["rp"]
    with ServicosConsolidacao() as consolidacao:
        consolidacao.salvar_rp(periodo, rp)
    with DatabasePMPV() as db:
        db.salvar_concilia_itens(periodo, [
            {"arquivo": i.file_name, "categoria": i.category, "valor": i.amount, "status": i.status, "metodo": i.method}
            for i in itens
        ])
    return {"rp": rp, "qtd_itens": len(itens)}


def historico() -> list[dict]:
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        periodos = sorted({i["periodo"] for i in (db.listar_concilia_itens() or [])})
        linhas = []
        for periodo in periodos:
            itens = db.listar_concilia_itens(periodo) or []
            cons = db.buscar_consolidacao(periodo) or {}
            receitas = sum(float(i["valor"] or 0) for i in itens if i["categoria"] == "Receita")
            despesas = sum(float(i["valor"] or 0) for i in itens if i["categoria"] == "Despesa")
            linhas.append({
                "periodo": periodo,
                "qtd_itens": len(itens),
                "total_receitas": receitas,
                "total_despesas": despesas,
                "rp_dos_itens": despesas - receitas,
                "rp_gravado": float(cons.get("rp") or 0.0),
                "data_atualizacao": (cons.get("data_atualizacao") or "")[:16],
            })
    from Src.common.periodos import ordenar_historico
    return ordenar_historico(linhas)
