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

from Src.common.periodos import is_periodo_valido, normalizar_periodo, periodos_do_trimestre
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


def _trimestre_do_ciclo(periodo: str) -> tuple[str, int]:
    """Mês → (rótulo do trimestre do ciclo, ano do 1º mês), a chave do PV.
    Jan/2027 → ("Nov - Jan", 2026); Dez/2026 → ("Nov - Jan", 2026); Abr/2026 → ("Fev - Abr", 2026)."""
    mes, ano = periodo.strip().split("/")
    indice = _MESES.index(mes.capitalize())
    # Recua até o 1º mês do trimestre do ciclo (Nov, Fev, Mai ou Ago).
    inicio = int(ano) * 12 + indice - (indice - 1) % 3
    return _FISCAIS[_MESES[inicio % 12]], inicio // 12


def _gravar_pv(repo, label: str, ano_pv: int, pr: float | None = None) -> dict:
    """Regrava o PV (PMPV + PR) de um trimestre do ciclo. `pr` None = usa o PR SALVO.
    Devolve {trimestre, atualizado, pv_antes, pv, pendencias}; com pendência nada é gravado."""
    servico_pv = ServicosPV(repo)
    trimestre = servico_pv.buscar_trimestre(label, ano_pv)
    periodos = trimestre["periodos"]
    resultado = {"trimestre": trimestre["chave"], "atualizado": False,
                 "pv_antes": trimestre["salvo"]["pv"] if trimestre["salvo"] else None,
                 "pv": None, "pendencias": []}
    if pr is None:
        # Chave do PR: ano do ÚLTIMO mês ("Nov - Jan/2027"), como a tela PR.
        chave_pr = f"{label}/{periodos[-1].split('/')[1]}"
        linha = repo.buscar_pr(chave_pr)
        if not linha or linha.get("pr") is None:
            resultado["pendencias"].append(
                f"PV não atualizado: falta o PR salvo de {chave_pr} ({periodos[0]} a {periodos[-1]}).")
        else:
            pr = float(linha["pr"])
    if not trimestre["pmpv"]:
        resultado["pendencias"].append(f"PV não atualizado: falta o PMPV de {periodos[0]}.")
    if resultado["pendencias"]:
        return resultado
    resultado["pv"] = servico_pv.salvar_trimestre(label, ano_pv, trimestre["pmpv"], pr)["pv"]
    resultado["atualizado"] = True
    return resultado


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

        # PV do mesmo trimestre, com o PR que acabou de ser gravado.
        pv = _gravar_pv(repo, label, int(meses_pr[0].split("/")[1]), pr)
        resultado.update(pv_antes=pv["pv_antes"], pv=pv["pv"])
        resultado["pendencias"].extend(pv["pendencias"])
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


def atualizar_dos_meses(periodos: list[str]) -> list[dict]:
    """PR e PV depois de salvar Auditoria, CGF, RET ou RP de `periodos`.

    Esses módulos mudam o SCG da consolidação, e o PR sai dele: sem isto, o PR e o PV
    gravados ficam velhos até alguém salvar o SCG ou o SR de novo. Meses do mesmo
    trimestre civil valem uma atualização só; período inválido é ignorado (o próprio
    "salvar" já recusa). Nunca levanta erro: o que não deu vira pendência na resposta."""
    por_trimestre: dict[str, str] = {}
    for periodo in periodos:
        if not periodo or not is_periodo_valido(periodo):
            continue
        canonico = normalizar_periodo(periodo)
        por_trimestre.setdefault(meses_do_pr_do_civil(canonico)[0], canonico)
    return [atualizar_sem_falhar(p) for p in por_trimestre.values()]


def atualizar_pv(periodos: list[str], repo: SqlitePRRepository | None = None) -> list[dict]:
    """Regrava o PV de cada trimestre do ciclo que contém algum dos `periodos`,
    usando o PR salvo. Chamado ao salvar o PMPV (ou o PR)."""
    trimestres: list[tuple[str, int]] = []
    for periodo in periodos:
        t = _trimestre_do_ciclo(periodo)
        if t not in trimestres:  # 3 meses do mesmo trimestre → 1 gravação só
            trimestres.append(t)
    proprio = repo is None
    repo = repo or SqlitePRRepository()
    try:
        return [_gravar_pv(repo, label, ano) for label, ano in trimestres]
    finally:
        if proprio:
            repo.fechar()


def atualizar_pv_sem_falhar(periodos: list[str]) -> list[dict]:
    """Como `atualizar_pv`, mas um problema não desfaz o PMPV/PR já salvo: vira pendência."""
    try:
        return atualizar_pv(periodos)
    except Exception as exc:  # noqa: BLE001 — o salvamento principal já aconteceu
        logger.exception("PV automático falhou para %s", periodos)
        motivo = str(exc) if isinstance(exc, ValueError) else "erro inesperado (veja o log da API)"
        return [{"trimestre": "", "atualizado": False, "pv_antes": None, "pv": None,
                 "pendencias": [f"Não foi possível atualizar o PV de {', '.join(periodos)}: {motivo}. "
                                "Salve pela tela do PV."]}]


def atualizar_pv_do_pr(chave_pr: str) -> dict | None:
    """Chave do PR ("Nov - Jan/2027", ano do último mês) → regrava o PV desse trimestre.
    Chave que não é de trimestre do ciclo (ex.: "Jan/2026", formato antigo) → None."""
    label, _, ano = chave_pr.strip().rpartition("/")
    if label not in _FISCAIS.values() or not ano.isdigit():
        return None
    ano_pv = int(ano) - 1 if label == "Nov - Jan" else int(ano)  # o PV usa o ano do 1º mês
    return atualizar_pv_sem_falhar(periodos_do_trimestre(label, ano_pv))[0]
