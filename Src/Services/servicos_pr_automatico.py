"""PR e PV atualizados junto com o SCG e o SR.

O PR de um trimestre do ciclo (Quadro 7) sai do SCG e do SR do trimestre civil
que termina 2 meses antes, e o PV (Quadro 8) sai desse PR. Quando o analista
salva o SCG de um mês ou o SR de um trimestre, a API chama `atualizar_do_mes`:
o PR e o PV do trimestre afetado são recalculados e gravados na mesma hora, e a
resposta traz o antes e o depois para a tela mostrar.

Se faltar algo (SCG de algum mês, SR, VP ou PMPV), nada é gravado e o motivo
volta em `pendencias`, igual ao que a tela do PR mostra.
"""
from __future__ import annotations

import logging

from Src.infrastructure.repositories.sqlite_repositories import SqlitePRRepository
from Src.Services.servicos_pr import ServicosPR
from Src.Services.servicos_pv import ServicosPV

logger = logging.getLogger(__name__)

_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
# 1º mês do trimestre do ciclo → nome usado nas chaves do PR e do PV.
_FISCAIS = {"Nov": "Nov - Jan", "Fev": "Fev - Abr", "Mai": "Mai - Jul", "Ago": "Ago - Out"}


def meses_do_pr_do_civil(periodo: str) -> list[str]:
    """Os 3 meses do PR que usam o trimestre civil de `periodo`: o PR começa 2 meses
    depois do fim do trimestre civil. Jul/2026 (Jul–Set) → Nov/2026, Dez/2026, Jan/2027.
    Inverso de `servicos_pr.meses_apurados_do_pr`."""
    mes, ano = periodo.strip().split("/")
    indice = _MESES.index(mes.capitalize())
    fim_do_civil = int(ano) * 12 + indice - indice % 3 + 2
    return [f"{_MESES[(fim_do_civil + k) % 12]}/{(fim_do_civil + k) // 12}" for k in (2, 3, 4)]


def atualizar_do_mes(periodo: str, repo: SqlitePRRepository | None = None) -> dict:
    """Recalcula e grava o PR e o PV que dependem do trimestre civil de `periodo`.

    Devolve {meses_pr, atualizado, pr_antes, pr, pv_antes, pv, pendencias}.
    `atualizado` False = nada gravado (ver `pendencias`)."""
    meses_pr = meses_do_pr_do_civil(periodo)
    label = _FISCAIS[meses_pr[0].split("/")[0]]
    proprio = repo is None
    repo = repo or SqlitePRRepository()
    try:
        servico_pr = ServicosPR(repo)
        apuracao = servico_pr.apurar_trimestre(meses_pr)
        resultado = {"meses_pr": meses_pr, "atualizado": False, "pr_antes": None, "pr": None,
                     "pv_antes": None, "pv": None, "pendencias": list(apuracao["pendencias"])}
        if resultado["pendencias"]:
            return resultado

        # Mesmas chaves das telas: o PR usa o ano do último mês ("Nov - Jan/2027"),
        # o PV o do 1º mês ("Nov - Jan/2026"), como o PMPV.
        chave_pr = f"{label}/{meses_pr[-1].split('/')[1]}"
        antes = repo.buscar_pr(chave_pr)
        resultado["pr_antes"] = float(antes["pr"]) if antes and antes.get("pr") is not None else None
        pr = servico_pr.salvar_valores(chave_pr, apuracao["scg_selic"], apuracao["sr"], apuracao["vp"])
        resultado.update(atualizado=True, pr=pr)

        servico_pv = ServicosPV(repo)
        ano_pv = int(meses_pr[0].split("/")[1])
        trimestre = servico_pv.buscar_trimestre(label, ano_pv)
        resultado["pv_antes"] = trimestre["salvo"]["pv"] if trimestre["salvo"] else None
        if not trimestre["pmpv"]:
            resultado["pendencias"].append(f"PV não atualizado: falta o PMPV de {meses_pr[0]}.")
            return resultado
        resultado["pv"] = servico_pv.salvar_trimestre(label, ano_pv, trimestre["pmpv"], pr)["pv"]
        return resultado
    finally:
        if proprio:
            repo.fechar()


def atualizar_sem_falhar(periodo: str) -> dict:
    """Como `atualizar_do_mes`, mas um problema no PR não desfaz o SCG/SR já salvo:
    vira pendência para a tela mostrar."""
    try:
        return atualizar_do_mes(periodo)
    except Exception as exc:  # noqa: BLE001 — o salvamento principal já aconteceu
        logger.exception("PR automático falhou para %s", periodo)
        motivo = str(exc) if isinstance(exc, ValueError) else "erro inesperado (veja o log da API)"
        return {"meses_pr": [], "atualizado": False, "pr_antes": None, "pr": None, "pv_antes": None, "pv": None,
                "pendencias": [f"Não foi possível atualizar o PR e o PV: {motivo}. Salve pela tela do PR."]}
