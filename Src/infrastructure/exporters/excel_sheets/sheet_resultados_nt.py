"""Abas de resultado no formato dos Quadros da Nota Técnica (SCG, SR, PR, PV).

Recebem os dados prontos (dos serviços) e só desenham; nenhum cálculo de
regra de negócio aqui além de somas de exibição.
"""
from __future__ import annotations

from . import arpe


def _curto(periodo: str) -> str:
    mes, ano = periodo.split("/")
    return f"{mes.lower()}/{ano[-2:]}"


def _aba(wb, nome: str, larguras: list[float], titulo: str, subtitulo: str):
    ws = wb[nome] if nome in wb.sheetnames else wb.create_sheet(nome)
    if ws.max_row == 1 and ws["A1"].value is None:
        arpe.preparar(ws, len(larguras), larguras)
        return ws, arpe.titulo(ws, titulo, subtitulo, len(larguras))
    return ws, ws.max_row + 3


def _bloco(ws, r: int, texto: str, ncols: int) -> int:
    """Faixa do trimestre quando a aba tem mais de um bloco."""
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
    c = ws.cell(r, 1, texto)
    c.font = arpe._font(True, arpe.AZUL, 12)
    return r + 1


def sheet_scg(wb, meses: list[str], scg: list[dict], selic: dict[str, float]) -> None:
    """SCG mensal do trimestre: CGR, CGF, RPV, RET, RP, SCG e SCG com SELIC.
    `selic`: % acumulada por mês (a mesma do SR do trimestre)."""
    n = len(meses) + 3
    ws, r = _aba(wb, "SCG", [34, 9] + [18] * len(meses) + [19],
                 "Apuração mensal do Saldo da Conta Gráfica (SCG)",
                 "SCG = RPV + RET + RP, com RPV = CGR − CGF. SCG com SELIC = SCG × (1 + variação da SELIC "
                 "acumulada do mês até o fim do trimestre).")
    r = _bloco(ws, r, f"{meses[0]} a {meses[-1]}", n)
    arpe.cabecalho(ws, r, ["DESCRIÇÃO", "UNIDADE"] + [_curto(m) for m in meses] + ["TRIMESTRE"])
    por_mes = {d["periodo"]: d for d in scg}
    val = lambda m, k: float((por_mes.get(m) or {}).get(k) or 0.0)  # noqa: E731

    linhas = [
        ("CGR — Custo do Gás Realizado", "cgr", "normal"),
        ("CGF — Custo do Gás Faturado (VF × PMPV)", "cgf", "normal"),
        ("RPV = CGR − CGF", "rpv", "normal"),
        ("RET — Encargos de Transporte (EAT + EC)", "ret", "normal"),
        ("RP — Penalidades", "rp", "normal"),
        ("SCG = RPV + RET + RP", "scg", "destaque"),
    ]
    for i, (rot, k, estilo) in enumerate(linhas, start=1):
        vs = [val(m, k) for m in meses]
        arpe.linha(ws, r + i, [rot, "R$"] + vs + [sum(vs)], [None, None] + [arpe.BRL] * (len(meses) + 1),
                   estilo, alternada=i % 2 == 0)
    r += len(linhas) + 1
    arpe.linha(ws, r, ["Variação da SELIC acumulada", "%"] + [selic.get(m, "—") for m in meses] + [""],
               [None, None] + [arpe.PCT] * len(meses) + [None])
    com = [val(m, "scg") * (1 + selic.get(m, 0.0) / 100) for m in meses]
    arpe.linha(ws, r + 1, ["SCG com SELIC", "R$"] + com + [sum(com)],
               [None, None] + [arpe.BRL] * (len(meses) + 1), "total")
    if not selic:
        arpe.nota(ws, r + 2, "SELIC não encontrada: salve o SR do trimestre na plataforma para trazer a variação.", n)


def sheet_sr(wb, meses: list[str], sr: list[dict]) -> None:
    """Quadro 6 — Saldo Remanescente com correção da SELIC."""
    n = len(meses) + 2
    ws, r = _aba(wb, "SR", [38, 9] + [18] * len(meses),
                 "Quadro 6 — Apuração do Saldo Remanescente com correção da SELIC",
                 "SR = (VP − VF) × PR do mês, atualizado pela variação da SELIC (Art. 11, §§ 4º e 5º).")
    r = _bloco(ws, r, f"{meses[0]} a {meses[-1]}", n)
    arpe.cabecalho(ws, r, ["DESCRIÇÃO", "UNIDADE"] + [_curto(m) for m in meses])
    if not sr:
        arpe.nota(ws, r + 1, "SR deste trimestre não foi salvo na plataforma.", n)
        return
    por_mes = {d["mes"]: d for d in sr}
    val = lambda m, k: float((por_mes.get(m) or {}).get(k) or 0.0)  # noqa: E731
    linhas = [
        ("Volume Prospectivo — VP", "m³", "vp", arpe.VOLUME, "normal"),
        ("Volume Faturado — VF", "m³", "vf", arpe.VOLUME, "normal"),
        ("Diferença de Volumes — (VP − VF)", "m³", "diferenca", arpe.VOLUME, "normal"),
        ("Parcela de Recuperação do Período — PR", "R$/m³", "pr", arpe.TARIFA, "normal"),
        ("Saldo Remanescente", "R$", "sr_parcela", arpe.BRL, "destaque"),
        ("Variação da SELIC acumulada", "%", "selic_mensal", arpe.PCT, "normal"),
        ("Saldo Remanescente (SELIC)", "R$", "sr_selic", arpe.BRL, "destaque"),
    ]
    for i, (rot, un, k, fmt, estilo) in enumerate(linhas, start=1):
        arpe.linha(ws, r + i, [rot, un] + [val(m, k) for m in meses], [None, None] + [fmt] * len(meses),
                   estilo, alternada=i % 2 == 0)
    total = sum(val(m, "sr_selic") for m in meses)
    r += len(linhas) + 1
    arpe.linha(ws, r, ["Total do trimestre", "R$", total] + [""] * (len(meses) - 1),
               [None, None, arpe.BRL] + [None] * (len(meses) - 1), "total")
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=n)


def sheet_pr(wb, pr: dict | None) -> None:
    """Quadro 7 — Parcela de Recuperação (PR) do trimestre seguinte."""
    ws, r = _aba(wb, "PR", [52, 10, 20], "Quadro 7 — Parcela de Recuperação (PR)",
                 "PR = (SCG com SELIC + SR com SELIC do trimestre apurado) ÷ VP do trimestre do PR, "
                 "arredondado a 4 casas.")
    if not pr:
        arpe.nota(ws, r, "PR não calculado.", 3)
        return
    mp, ma = pr["meses_pr"], pr["meses_apurados"]
    r = _bloco(ws, r, f"PR de {mp[0]} a {mp[-1]} (apurado com {ma[0]} a {ma[-1]})", 3)
    arpe.cabecalho(ws, r, ["DESCRIÇÃO", "UNIDADE", "VALOR"])
    itens = [(f"Saldo da Conta Gráfica — SCG com SELIC ({ma[0]} a {ma[-1]})", "R$", pr["scg_selic"], arpe.BRL, "normal")]
    itens += [(f"Saldo Remanescente com SELIC — {m['periodo']}", "R$", m["sr"], arpe.BRL, "normal") for m in pr["meses"]]
    itens += [
        ("Saldo Total a Recuperar", "R$", pr["saldo_total"], arpe.BRL, "total"),
        (f"VP — Volume Prospectivo Contratado ({mp[0]} a {mp[-1]})", "m³", pr["vp"], arpe.VOLUME, "normal"),
        ("Parcela de Recuperação — PR", "R$/m³", pr["pr"], arpe.TARIFA, "destaque"),
    ]
    for i, (rot, un, v, fmt, estilo) in enumerate(itens, start=1):
        arpe.linha(ws, r + i, [rot, un, v], [None, None, fmt], estilo, alternada=i % 2 == 0)
    if pr.get("pendencias"):
        arpe.nota(ws, r + len(itens) + 2, "Pendências: " + " ".join(pr["pendencias"]), 3)


def sheet_pv(wb, pv: dict | None, meses_pr: list[str]) -> None:
    """Quadro 8 — Preço de Venda (PV = PMPV + PR)."""
    ws, r = _aba(wb, "PV", [40, 10, 20], "Quadro 8 — Cálculo do Preço de Venda (PV)",
                 "PV = PMPV + PR do mesmo trimestre.")
    r = _bloco(ws, r, f"PV de {meses_pr[0]} a {meses_pr[-1]}", 3)
    arpe.cabecalho(ws, r, ["DESCRIÇÃO", "UNIDADE", "VALOR"])
    if not pv:
        arpe.nota(ws, r + 1, "PV não calculado.", 3)
        return
    arpe.linha(ws, r + 1, ["PMPV — Preço Médio Ponderado de Venda", "R$/m³", pv["pmpv"]], [None, None, arpe.TARIFA])
    arpe.linha(ws, r + 2, ["PR — Parcela de Recuperação", "R$/m³", pv["pr"]], [None, None, arpe.TARIFA], alternada=True)
    arpe.linha(ws, r + 3, ["PV = PMPV + PR", "R$/m³", pv["pv"]], [None, None, arpe.TARIFA], "total")
    if pv.get("avisos"):
        arpe.nota(ws, r + 5, "Avisos: " + " ".join(pv["avisos"]), 3)
