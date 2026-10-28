"""Conciliação RP (penalidades) — orquestração usada pela API web, com as
mesmas regras da tela desktop (tela_concilia.py) via RegrasConcilia.

RP (saldo de penalidade) = (Σ despesas − Σ receitas) × (1 − 9,25% PIS/COFINS) —
mesma fórmula da planilha oficial "Conta Gráfica" (linha "Saldo de penalidade")
e do que a tela desktop grava. Notas "cancelado" entram negativas
(RegrasConcilia). Os itens ficam com o valor bruto da nota.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Callable

from Src.Services.servicos_concilia import FATOR_PIS_COFINS, PdfItem, RegrasConcilia


def pdfs_da_pasta(pasta: Path | None) -> list[Path]:
    """Todos os PDFs da pasta (e subpastas), cada um uma vez só.

    No Windows `*.pdf` e `*.PDF` casam os mesmos arquivos; juntar as duas listas dobrava tudo, e as
    notas "cancelado" (que ficam fora da deduplicação por ND) entravam negativas duas vezes."""
    if not pasta or not pasta.exists():
        return []
    return sorted((p for p in pasta.rglob("*") if p.is_file() and p.suffix.lower() == ".pdf"), key=str)


STATUS_JA_NO_RET = "JA_NO_RET"


def marcar_ja_no_ret(itens: list[PdfItem], log: Callable[[str], None] | None = None) -> None:
    """Despesa que já foi contada no RET (mesmo PDF, mesmo valor) não entra de novo no RP.

    A ND do encargo de transporte às vezes é guardada também na pasta de penalidades (ex.: ND
    90014427 em jul/26); o Excel a conta só no RET. O item vira valor 0 com status JA_NO_RET —
    só acontece se o RET desse documento já estiver salvo."""
    from Src.Database.database import DatabasePMPV

    try:
        with DatabasePMPV() as db:
            no_ret = {
                (Path(str(r.get("arquivo") or "")).name.lower(), round(float(r.get("valor_total") or 0), 2))
                for p in db.listar_periodos_ret() for r in (db.listar_ret_itens(p) or [])
            }
    except Exception:  # noqa: BLE001 — sem banco/RET salvo, segue como antes
        return
    for pos, i in enumerate(itens):
        if i.category == "Despesa" and i.amount and (i.file_name.lower(), round(i.amount, 2)) in no_ret:
            if log:
                log(f"{i.file_name}: já está no RET ({i.amount:,.2f}) — fora do RP para não contar duas vezes.")
            itens[pos] = replace(i, amount=0.0, status=STATUS_JA_NO_RET, method=f"{i.method} · já no RET")


def processar(pasta_receitas: Path | None, pasta_despesas: Path | None,
              log: Callable[[str], None] | None = None) -> list[PdfItem]:
    log = log or (lambda _msg: None)
    itens: list[PdfItem] = []
    rec = pdfs_da_pasta(pasta_receitas)
    desp = pdfs_da_pasta(pasta_despesas)
    if rec:
        log("--- Receitas ---")
        itens += RegrasConcilia.processar_arquivos(rec, "Receita", log, raiz=pasta_receitas)
    if desp:
        log("--- Despesas ---")
        itens += RegrasConcilia.processar_arquivos(desp, "Despesa", log, raiz=pasta_despesas)
    marcar_ja_no_ret(itens, log)
    return itens


def totais(itens: list[PdfItem]) -> dict:
    receitas = sum(i.amount for i in itens if i.category == "Receita") * FATOR_PIS_COFINS
    despesas = sum(i.amount for i in itens if i.category == "Despesa") * FATOR_PIS_COFINS
    return {
        "total_receitas": receitas,
        "total_despesas": despesas,
        "rp": despesas - receitas,
        "qtd_revisar": sum(1 for i in itens if i.status not in ("OK", STATUS_JA_NO_RET)),
    }


def salvar(periodo: str, itens: list[PdfItem]) -> dict:
    """Grava o RP do período (consolidação) e substitui os itens do período."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.servicos_consolidacao import ServicosConsolidacao
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f'O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
    if not itens:
        raise ValueError("Não há notas conciliadas na lista para salvar. Processe as pastas de receitas e despesas primeiro.")
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
            receitas = sum(float(i["valor"] or 0) for i in itens if i["categoria"] == "Receita") * FATOR_PIS_COFINS
            despesas = sum(float(i["valor"] or 0) for i in itens if i["categoria"] == "Despesa") * FATOR_PIS_COFINS
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
