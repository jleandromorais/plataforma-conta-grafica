"""Tarifa média de um trimestre do ciclo (Quadro 9 da NT), SÓ LEITURA.

Não existe conta nova aqui: o PV vem do que está gravado (`ServicosPV.buscar_trimestre`), a MB de
`servicos_margem.buscar_margem` e a soma de `servicos_margem.tarifa_media`. Quando o trimestre toca dois
anos (Nov–Jan), devolve uma tarifa para a MB de cada ano e NÃO escolhe qual vale: o analista decide.
"""
from __future__ import annotations

from Src.common.periodos import is_periodo_valido, normalizar_periodo, periodos_do_trimestre
from Src.Services.tarifa import servicos_margem
from Src.Services.tarifa.servicos_pr_automatico import _trimestre_do_ciclo
from Src.Services.tarifa.servicos_pv import ServicosPV, _num

_MOTIVO_SEM_PV = "grave o PV primeiro"


def trimestre_do_ciclo(trimestre: str) -> tuple[str, int, list[str]]:
    """Aceita "Nov/2025_Jan/2026" (rótulo) ou um mês qualquer do trimestre ("Dez/2025").
    Devolve (rótulo fiscal, ano do 1º mês, os 3 meses). Trimestre que não existe → ValueError (422)."""
    texto = (trimestre or "").strip()
    partes = [normalizar_periodo(p) for p in texto.split("_")]
    if not texto or len(partes) > 2 or not all(is_periodo_valido(p) for p in partes):
        raise ValueError(f"O trimestre “{trimestre}” não é válido. Use o rótulo, por exemplo Nov/2025_Jan/2026, "
                         "ou um mês do trimestre, por exemplo Dez/2025.")
    label, ano = _trimestre_do_ciclo(partes[0])
    meses = periodos_do_trimestre(label, ano)
    if len(partes) == 2 and partes != [meses[0], meses[-1]]:
        raise ValueError(f"“{trimestre}” não é um trimestre do ciclo (Nov–Jan, Fev–Abr, Mai–Jul ou Ago–Out). "
                         f"O que contém {partes[0]} é {meses[0]}_{meses[-1]}.")
    return label, ano, meses


def tarifa_media_do_trimestre(trimestre: str, servico_pv: ServicosPV) -> dict:
    label, ano, meses = trimestre_do_ciclo(trimestre)
    dados_pv = servico_pv.buscar_trimestre(label, ano)
    salvo = dados_pv["salvo"]
    pv = float(salvo["pv"]) if salvo else None

    anos = sorted({int(m.split("/")[1]) for m in meses})
    margens = [{"ano": a, "mb": m["margem"], "origem": m["origem"]}
               for a in anos for m in [servicos_margem.buscar_margem(a)]]
    tarifas = [{"ano": m["ano"], "mb": m["mb"],
                "tarifa_media": None if pv is None else servicos_margem.tarifa_media(pv, m["mb"])}
               for m in margens]

    motivo = aviso = None
    sem_mb = [str(m["ano"]) for m in margens if m["mb"] is None]
    if pv is None:
        motivo = _MOTIVO_SEM_PV
    elif sem_mb:
        motivo = f"informe a MB de {', '.join(sem_mb)} (margem de distribuição) no PMPV"
    if sem_mb:
        aviso = (f"Falta a MB de {', '.join(sem_mb)}: sem ela não há tarifa média desse ano. "
                 "Informe a MB do ano na tela PMPV.")
    mbs = {m["mb"] for m in margens if m["mb"] is not None}
    if len(anos) > 1 and len(mbs) > 1 and not sem_mb:
        aviso = ("O trimestre cruza o ano e as MBs são diferentes: o sistema mostra uma tarifa para cada MB "
                 "e não escolhe qual vale. O analista precisa confirmar.")
    elif len(anos) > 1 and len(mbs) > 1 and sem_mb:
        aviso += " Além disso, as MBs informadas são diferentes entre os anos."
    if salvo and abs(salvo["pv"] - dados_pv["pv"]) > 1e-6:
        extra = (f"O PV gravado ({_num(salvo['pv'])}) difere do que os módulos calculam hoje "
                 f"({_num(dados_pv['pv'])}); a tarifa usa o gravado.")
        aviso = f"{aviso} {extra}" if aviso else extra

    return {"trimestre": f"{meses[0]}_{meses[-1]}", "chave_pv": dados_pv["chave"], "pv_gravado": pv,
            "margens": margens, "tarifas": tarifas, "cruza_ano": len(anos) > 1,
            "aviso": aviso, "motivo": motivo}
