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

from Src.common.duplicatas import possiveis_duplicatas_por_valor
from Src.Services.rp.servicos_concilia import FATOR_PIS_COFINS, PdfItem, RegrasConcilia, eh_top


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
    from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
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


TOL_PROVA_REAL_RS = 1.0   # R$: abaixo disso é arredondamento


def _tipo_e_numero(nome: str) -> tuple[str, str, str | None]:
    """(tipo, número, chave) da ND pelo nome do arquivo, com a MESMA extração do dedupe do
    processar_arquivos (`_numero_nd`). Sem ND → ("OUTRA", "", None). Nota "cancelado" não
    tem chave: ela fica fora da dedupe (entra negativa) e não conta como repetida."""
    from Src.Services.rp.servicos_concilia import _numero_nd, _sem_acento

    nd = _numero_nd(nome)
    if not nd:
        return "OUTRA", "", None
    tipo = "PFP" if nd.startswith("PFP") else "TOP"
    numero = nd[3:] if tipo == "PFP" else nd[7:]
    cancelada = "cancelado" in _sem_acento(nome).lower()
    return tipo, numero, None if cancelada else nd


def _eh_top_pelo_nome(arquivo: str) -> bool:
    """TOP pelo nome do arquivo: `eh_top` ("ND - TOP NREC 03863") + a ND "NDTOPNREC03899", que
    `eh_top` só reconhece pela pasta (a pasta não fica gravada)."""
    nome = Path(arquivo).name
    return eh_top(nome) or _tipo_e_numero(nome)[0] == "TOP"


def _pdf_itens_gravados(gravados: list[dict]) -> list[PdfItem]:
    """Itens gravados (`concilia_itens`) como PdfItem. TOP não recuperável é receita mesmo se foi
    gravado na categoria Despesa (pasta de despesas): a mesma regra do processar_arquivos (`eh_top`),
    aplicada aqui pelo nome do arquivo."""
    return [
        PdfItem(file_name=str(g.get("arquivo") or ""), file_path="",
                category="Receita" if _eh_top_pelo_nome(str(g.get("arquivo") or "")) else str(g.get("categoria") or ""),
                amount=float(g.get("valor") or 0.0), status=str(g.get("status") or ""), method="")
        for g in gravados
    ]


def remover_nota(periodo: str, item_id: int) -> dict:
    """Tira UMA nota gravada do mês (a cópia repetida, por exemplo) e regrava o RP sem ela.
    O RP novo sai da MESMA conta da prova real. O chamador atualiza o SCG/PR (atualizar_dos_meses)."""
    from Src.Database.database import DatabasePMPV
    from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, "
                         "por exemplo Jan/2026.")
    with DatabasePMPV() as db:
        atuais = db.listar_concilia_itens(periodo) or []
        if not any(g.get("id") == item_id for g in atuais):
            raise ValueError("Essa nota não está mais gravada neste mês. Atualize a página e confira a lista.")
        if len(atuais) == 1:
            raise ValueError("Essa é a única nota gravada do mês, então não dá para tirá-la. "
                             "Para refazer o mês, processe e grave de novo.")
        db.remover_item_do_periodo("concilia_itens", periodo, item_id)
        restantes = [g for g in atuais if g.get("id") != item_id]
    rp = totais(_pdf_itens_gravados(restantes))["rp"]
    with ServicosConsolidacao() as consolidacao:
        consolidacao.salvar_rp(periodo, rp)
    return {"periodo": periodo, "valor_gravado": rp, "qtd_itens": len(restantes)}


def prova_real(periodo: str) -> dict:
    """A conta do RP gravado do mês, aberta, item a item. Lê os itens gravados (`concilia_itens`),
    refaz o RP com a MESMA `totais` do salvar e compara com consolidacao.rp. NÃO grava nada.
    Avisa notas repetidas (mesmo tipo + número da ND), que o dedupe do processar já trataria."""
    from collections import defaultdict

    from Src.Database.database import DatabasePMPV
    from Src.common.periodos import is_periodo_valido

    if not is_periodo_valido(periodo):
        raise ValueError(f"O período “{periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, "
                         "por exemplo Jan/2026.")
    with DatabasePMPV() as db:
        gravados = db.listar_concilia_itens(periodo) or []
        cons = db.buscar_consolidacao(periodo) or {}

    pdf_itens = _pdf_itens_gravados(gravados)
    # Quantas vezes cada chave (tipo + nº da ND) aparece.
    por_chave: dict[str, list[PdfItem]] = defaultdict(list)
    for p in pdf_itens:
        chave = _tipo_e_numero(Path(p.file_name).name)[2]
        if chave:
            por_chave[chave].append(p)

    itens, agg = [], {"receita": [0, 0.0], "despesa": [0, 0.0], "ja_no_ret": [0, 0.0]}
    for p, g in zip(pdf_itens, gravados):
        nome = Path(p.file_name).name
        tipo, numero, chave = _tipo_e_numero(nome)
        lado = "ja_no_ret" if p.status == STATUS_JA_NO_RET else ("receita" if p.category == "Receita" else "despesa")
        agg[lado][0] += 1
        agg[lado][1] += p.amount
        itens.append({
            "id": g.get("id"),
            "arquivo": p.file_name, "nome": nome, "lado": lado, "tipo": tipo, "numero": numero,
            "valor": round(p.amount, 2), "liquido": round(p.amount * FATOR_PIS_COFINS, 2),
            "status": p.status, "repetida": bool(chave and len(por_chave[chave]) > 1),
        })
    itens.sort(key=lambda x: x["valor"], reverse=True)

    duplicadas = []
    for chave, grupo in por_chave.items():
        if len(grupo) > 1:
            tipo, numero, _ = _tipo_e_numero(Path(grupo[0].file_name).name)
            total = sum(g.amount for g in grupo)
            duplicadas.append({
                "tipo": tipo, "numero": numero, "qtd": len(grupo), "valor_total": round(total, 2),
                "liquido_total": round(total * FATOR_PIS_COFINS, 2),
                "arquivos": [Path(g.file_name).name for g in grupo],
            })
    duplicadas.sort(key=lambda d: d["valor_total"], reverse=True)

    # Mesmo valor no mesmo lado: pega a cópia que o número da ND não reconheceu como repetida.
    por_valor = possiveis_duplicatas_por_valor(
        (i for i in itens if i["lado"] != "ja_no_ret"),
        grupo=lambda i: "Receita" if i["lado"] == "receita" else "Despesa",
        valor=lambda i: i["valor"], nome=lambda i: i["nome"], ja_avisada=lambda i: i["repetida"],
    )
    # A tabela de notas destaca essas notas (e o filtro "Só repetidas" as mostra).
    ids_em_duplicata = {i for g in por_valor for i in g["ids"]}
    for i in itens:
        i["possivel_duplicata"] = i["id"] in ids_em_duplicata

    tem_itens = bool(pdf_itens)
    rp_calculado = round(totais(pdf_itens)["rp"], 2) if tem_itens else None
    rp_gravado = float(cons["rp"]) if cons.get("rp") is not None else None
    diferenca = round(rp_calculado - rp_gravado, 2) if rp_calculado is not None and rp_gravado is not None else None
    return {
        "periodo": periodo,
        "tem_itens": tem_itens,
        "qtd_itens": len(pdf_itens),
        "taxa": 0.0925,
        "receitas": {"qtd": agg["receita"][0], "bruto": round(agg["receita"][1], 2),
                     "liquido": round(agg["receita"][1] * FATOR_PIS_COFINS, 2)},
        "despesas": {"qtd": agg["despesa"][0], "bruto": round(agg["despesa"][1], 2),
                     "liquido": round(agg["despesa"][1] * FATOR_PIS_COFINS, 2)},
        "ja_no_ret": {"qtd": agg["ja_no_ret"][0], "bruto": round(agg["ja_no_ret"][1], 2)},
        "rp_calculado": rp_calculado,
        "rp_gravado": rp_gravado,
        "diferenca": diferenca,
        "confere": tem_itens and diferenca is not None and abs(diferenca) <= TOL_PROVA_REAL_RS,
        "itens": itens,
        "possiveis_duplicadas": duplicadas,
        "possiveis_duplicatas_valor": por_valor,
        "data_atualizacao": (cons.get("data_atualizacao") or "")[:16],
    }


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
