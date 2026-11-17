"""Cascata SR → PR → PV com prévia e aprovação.

Antes, salvar a Auditoria, o CGF, o RET, o RP, o SCG ou o SR regravava o SR, o PR e o PV em silêncio
(`servicos_pr_automatico`). Agora o "salvar" só grava o que é dele e devolve a PRÉVIA: o valor de hoje
ao lado do novo. O analista aprova, e só então `aplicar` grava.

A conta continua num lugar só: `previa` e `aplicar` chamam as mesmas funções de `servicos_pr_automatico`
(com `gravar=False` na prévia). `aplicar` recalcula tudo de novo no servidor e NUNCA grava números
que vieram da tela. Com qualquer pendência (falta SCG, SR, VP, PMPV, SELIC...) nada é gravado.
"""
from __future__ import annotations

import logging
from typing import Any

from Src.Database.database import origem_da_alteracao
from Src.common.periodos import is_periodo_valido, normalizar_periodo, periodo_sort_key, periodos_do_trimestre
from Src.infrastructure.repositories.sqlite_repositories import SqlitePRRepository
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
from Src.Services.tarifa import servicos_pr_automatico as auto

logger = logging.getLogger(__name__)

TOL_SR = 0.01       # R$: diferença de centavo não conta
TOL_TARIFA = 5e-5   # PR e PV têm 4 casas: abaixo de meio décimo-milésimo é a mesma conta


def _mudou(antes: float | None, novo: float | None, tol: float) -> bool:
    """O valor novo existe e é diferente do gravado (ou nada estava gravado)."""
    return novo is not None and (antes is None or abs(novo - antes) > tol)


def _motivo(exc: Exception) -> str:
    return str(exc) if isinstance(exc, ValueError) else "erro inesperado (veja o log da API)"


def _chaves(meses_pr: list[str]) -> tuple[str, str]:
    """(chave do PR, chave do PV) do trimestre: o PR usa o ano do ÚLTIMO mês, o PV o do 1º."""
    label = auto._FISCAIS[meses_pr[0].split("/")[0]]
    return f"{label}/{meses_pr[-1].split('/')[1]}", f"{label}/{meses_pr[0].split('/')[1]}"


def _atualizacao_pendente(item: dict) -> bool:
    return (_mudou(item["sr_antes"], item["sr_novo"], TOL_SR)
            or _mudou(item["pr_antes"], item["pr_novo"], TOL_TARIFA)
            or _mudou(item["pv_antes"], item["pv_novo"], TOL_TARIFA))


_ETAPAS = ("sr", "pr", "pv")


class CascataMudou(Exception):
    """O cálculo de agora difere do que o analista viu na prévia: a rota devolve 409 e nada é gravado."""


def _etapas(a_partir_de: str, ate: str | None) -> tuple[str, ...]:
    """As etapas que o pedido cobre: de `a_partir_de` até `ate` (padrão: até o PV)."""
    if a_partir_de not in _ETAPAS:
        raise ValueError("`a_partir_de` deve ser sr, pr ou pv.")
    if ate is not None and ate not in _ETAPAS:
        raise ValueError("`ate` deve ser sr, pr ou pv.")
    fim = _ETAPAS.index(ate or "pv")
    inicio = _ETAPAS.index(a_partir_de)
    if fim < inicio:
        raise ValueError(f"Não dá para aprovar só até {ate} partindo de {a_partir_de}: "
                         "`ate` não pode vir antes de `a_partir_de`.")
    return _ETAPAS[inicio:fim + 1]


def _montar(periodos: list[str], a_partir_de: str, itens: list[dict], ate: str | None = None) -> dict:
    return {"periodos": [normalizar_periodo(p) or p for p in periodos], "a_partir_de": a_partir_de, "ate": ate,
            "desatualizado": any(i["desatualizado"] for i in itens), "trimestres": itens,
            "pendencias": [p for i in itens for p in i["pendencias"]]}


def _seguro(chamada, nome: str, vazio: dict) -> dict:
    """Um erro num passo vira pendência (e vai para o log): a prévia dos outros passos continua."""
    try:
        return chamada()
    except Exception as exc:  # noqa: BLE001 — a prévia não grava nada, então falhar aqui é inofensivo
        logger.exception("Prévia da cascata falhou em %s", nome)
        return {**vazio, "pendencias": [f"Não foi possível calcular {nome}: {_motivo(exc)}."]}


class ServicosCascata:
    def __init__(self, repo: SqlitePRRepository | None = None):
        self._proprio = repo is None
        self._repo = repo or SqlitePRRepository()

    def __enter__(self) -> "ServicosCascata":
        return self

    def __exit__(self, *_exc) -> bool:
        self.fechar()
        return False

    def fechar(self) -> None:
        if self._proprio:
            self._repo.fechar()

    # ── prévia (não grava) ──────────────────────────────────────────────────

    @staticmethod
    def _guias(periodos: list[str], a_partir_de: str) -> list[str]:
        """Um mês-guia por trimestre afetado, em ordem cronológica. Período inválido → ValueError (422)."""
        if a_partir_de not in ("sr", "pr", "pv"):
            raise ValueError("`a_partir_de` deve ser sr, pr ou pv.")
        guias: dict[Any, str] = {}
        for p in periodos:
            canonico = normalizar_periodo(p)
            if not canonico or not is_periodo_valido(canonico):
                raise ValueError(f"O período “{p}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, "
                                 "por exemplo Jan/2026.")
            chave = auto._trimestre_do_ciclo(canonico) if a_partir_de == "pv" else auto.meses_do_pr_do_civil(canonico)[0]
            guias.setdefault(chave, canonico)
        return sorted(guias.values(), key=periodo_sort_key)

    def _item(self, guia: str, a_partir_de: str, ate: str | None = None) -> dict:
        etapas = _etapas(a_partir_de, ate)
        pendencias: list[str] = []
        sr: dict = {"trimestre": None, "sr_antes": None, "sr": None, "linhas": [], "pendencias": []}
        trimestre_sr = None
        if a_partir_de == "pv":
            label, ano_pv = auto._trimestre_do_ciclo(guia)
            meses_pr = periodos_do_trimestre(label, ano_pv)
            chave_pr, chave_pv = _chaves(meses_pr)
            linha_pr = self._repo.buscar_pr(chave_pr)
            pr_salvo = float(linha_pr["pr"]) if linha_pr and linha_pr.get("pr") is not None else None
            pr = {"pr_antes": pr_salvo, "pr": pr_salvo}
            pv = _seguro(lambda: auto._gravar_pv(self._repo, label, ano_pv, None, gravar=False),
                         "o PV", {"pv_antes": None, "pv": None, "pendencias": []})
            pendencias += pv["pendencias"]
        else:
            civil = auto.meses_do_trimestre_civil(guia)
            trimestre_sr = f"{civil[0]}_{civil[-1]}"
            if a_partir_de == "sr":
                sr = _seguro(lambda: auto.atualizar_sr_do_mes(guia, gravar=False), "o SR", sr)
                pendencias += sr["pendencias"]
            meses_pr = auto.meses_do_pr_do_civil(guia)
            chave_pr, chave_pv = _chaves(meses_pr)
            vazio = {"pr_antes": None, "pr": None, "pv_antes": None, "pv": None, "pendencias": []}
            if "pr" in etapas:
                # Com o SR novo calculado, o PR da prévia sai dele (e não do SR velho que está gravado).
                sr_linhas = sr["linhas"] if sr["sr"] is not None and not sr["pendencias"] else None
                r = _seguro(lambda: auto.atualizar_do_mes(guia, self._repo, gravar=False, sr_linhas=sr_linhas,
                                                         com_pv="pv" in etapas),
                            "o PR e o PV" if "pv" in etapas else "o PR", vazio)
                pendencias += r["pendencias"]
            else:
                r = vazio  # aprovação só do SR: PR e PV nem entram (o PMPV seguinte não é exigido)
            pr, pv = r, r
        item = {
            "periodo": guia, "trimestre_sr": trimestre_sr,
            "sr_antes": sr["sr_antes"], "sr_novo": sr["sr"],
            "meses_pr": meses_pr, "chave_pr": chave_pr, "pr_antes": pr["pr_antes"], "pr_novo": pr["pr"],
            "chave_pv": chave_pv, "pv_antes": pv["pv_antes"], "pv_novo": pv["pv"],
            "pendencias": pendencias, "pendencias_sr": list(sr["pendencias"]),  # `pendencias_sr` só para o campo legado
        }
        item["desatualizado"] = _atualizacao_pendente(item)
        return item

    def previa(self, periodos: list[str], a_partir_de: str = "sr", ate: str | None = None) -> dict:
        """O que mudaria em cada trimestre afetado por `periodos`. NÃO grava nada.

        `a_partir_de`: "sr" (Auditoria, CGF, RET, RP, SCG: SR, PR e PV), "pr" (o SR acabou de ser salvo:
        PR e PV) ou "pv" (o PMPV ou o PR acabou de ser salvo: só o PV).
        `ate` (opcional) corta no meio: "sr" só o SR (não exige o PMPV seguinte), "pr" até o PR (exige SR
        salvo e PMPV novo), "pv" até o PV (exige o PR). Sem `ate`, vai até o PV."""
        _etapas(a_partir_de, ate)
        itens = [self._item(g, a_partir_de, ate) for g in self._guias(periodos, a_partir_de)]
        return _montar(periodos, a_partir_de, itens, ate)

    def pendente(self, limite: int = 4) -> dict:
        """Só os trimestres desatualizados entre os `limite` mais recentes que têm SCG gravado:
        é o aviso geral do Painel do Ciclo. NÃO grava nada. Cada trimestre olha o Banco Central
        para a SELIC, por isso o limite (o mais recente é o que importa no dia a dia)."""
        with ServicosConsolidacao() as cons:
            meses = [p["periodo"] for p in cons.obter_periodos()
                     if p.get("periodo") and is_periodo_valido(normalizar_periodo(p["periodo"]))]
        guias = self._guias(meses, "sr") if meses else []
        itens = [self._item(g, "sr") for g in guias[-limite:]]
        itens = [i for i in itens if i["desatualizado"]]
        return {**_montar([i["periodo"] for i in itens], "sr", itens), "pendencias": []}

    # ── aplicar (grava) ─────────────────────────────────────────────────────

    def aplicar(self, periodos: list[str], a_partir_de: str = "sr", ate: str | None = None,
                esperado: list[dict] | None = None) -> dict:
        """Aprovado pelo analista: recalcula de novo e grava SR → PR → PV, nessa ordem, por trimestre
        (só as etapas de `a_partir_de` até `ate`).

        Com qualquer pendência levanta ValueError (422) e NADA é gravado. Os números gravados são
        os do servidor; o que a tela mostrou na prévia não entra. Se `esperado` (o que o analista viu)
        difere do cálculo de agora, levanta CascataMudou (409) e também NADA é gravado.
        Devolve a cascata como ficou gravada."""
        previa = self.previa(periodos, a_partir_de, ate)
        if previa["pendencias"]:
            raise ValueError("A cascata não foi aplicada e nada foi gravado. Resolva antes:\n"
                             + "\n".join(f"- {p}" for p in previa["pendencias"]))
        if esperado:
            self._conferir_esperado(previa, a_partir_de, ate, esperado)
        with origem_da_alteracao("cascata"):  # a trilha de alterações registra que foi a aprovação da cascata
            itens = [self._gravar_item(i, a_partir_de, ate) if i["desatualizado"] else i
                     for i in previa["trimestres"]]
        return _montar(periodos, a_partir_de, itens, ate)

    def _conferir_esperado(self, previa: dict, a_partir_de: str, ate: str | None, esperado: list[dict]) -> None:
        """409 se algum valor que o analista viu (sr_novo, pr_novo, pv_novo) mudou desde a prévia."""
        etapas = _etapas(a_partir_de, ate)
        por_guia = {i["periodo"]: i for i in previa["trimestres"]}
        tolerancia = {"sr": TOL_SR, "pr": TOL_TARIFA, "pv": TOL_TARIFA}
        mudancas: list[str] = []
        for visto in esperado:
            guia = self._guias([visto["periodo"]], a_partir_de)[0]
            item = por_guia.get(guia)
            if item is None:
                raise ValueError(f"O trimestre de {visto['periodo']} não faz parte deste pedido de aprovação.")
            for etapa in etapas:
                valor_visto = visto.get(f"{etapa}_novo")
                if valor_visto is None:
                    continue
                agora = item[f"{etapa}_novo"]
                if agora is None or abs(agora - valor_visto) > tolerancia[etapa]:
                    mudancas.append(f"{etapa.upper()} de {guia}: você viu {valor_visto}, agora o cálculo dá {agora}")
        if mudancas:
            raise CascataMudou("Os dados mudaram desde a prévia e nada foi gravado. Confira a prévia de novo "
                               "e aprove outra vez:\n" + "\n".join(f"- {m}" for m in mudancas))

    def _gravar_item(self, item: dict, a_partir_de: str, ate: str | None = None) -> dict:
        etapas = _etapas(a_partir_de, ate)
        guia = item["periodo"]
        gravado = dict(item)
        if a_partir_de == "pv":
            label, ano_pv = auto._trimestre_do_ciclo(guia)
            pv = auto._gravar_pv(self._repo, label, ano_pv, None)
            self._exigir(pv["atualizado"], pv["pendencias"])
            gravado["pv_novo"] = pv["pv"]
        else:
            if a_partir_de == "sr" and _mudou(item["sr_antes"], item["sr_novo"], TOL_SR):
                sr = auto.atualizar_sr_do_mes(guia, gravar=True)
                self._exigir(sr["atualizado"], sr["pendencias"])
                gravado["sr_novo"] = sr["sr"]
            if "pr" in etapas:
                r = auto.atualizar_do_mes(guia, self._repo, gravar=True, com_pv="pv" in etapas)
                self._exigir(r["atualizado"], r["pendencias"])
                gravado["pr_novo"], gravado["pv_novo"] = r["pr"], r["pv"]
        gravado["pendencias"] = []
        gravado["desatualizado"] = False  # acabou de ser gravado
        return gravado

    @staticmethod
    def _exigir(gravou: bool, pendencias: list[str]) -> None:
        if not gravou:  # a prévia passou, mas algo mudou no meio do caminho
            raise ValueError("A cascata parou no meio e o que faltava não foi gravado:\n"
                             + "\n".join(f"- {p}" for p in pendencias))


# ── para as rotas de "salvar" ───────────────────────────────────────────────

def previa_sem_falhar(periodos: list[str], a_partir_de: str = "sr") -> dict:
    """A prévia que as rotas de salvar devolvem no campo `cascata`. O salvamento principal já aconteceu:
    um problema aqui nunca desfaz nada, vira pendência. Período inválido é ignorado (o próprio salvar recusa)."""
    validos = [p for p in periodos if p and is_periodo_valido(normalizar_periodo(p))]
    try:
        with ServicosCascata() as servico:
            return servico.previa(validos, a_partir_de) if validos else _montar([], a_partir_de, [])
    except Exception as exc:  # noqa: BLE001
        logger.exception("Prévia da cascata falhou para %s", periodos)
        return {"periodos": validos, "a_partir_de": a_partir_de, "desatualizado": False, "trimestres": [],
                "pendencias": [f"Não foi possível calcular a prévia do SR, PR e PV: {_motivo(exc)}."]}


def pr_automatico_legado(cascata: dict) -> dict:
    """Campo antigo `pr_automatico` (por um ciclo, para o site antigo não quebrar): SEMPRE `atualizado=False`,
    porque agora nada é regravado sozinho. `pr` e `pv` ficam None (não foi gravado); o valor novo está em `cascata`."""
    item = (cascata["trimestres"] or [None])[0]
    if item is None:
        return {"meses_pr": [], "atualizado": False, "pr_antes": None, "pr": None, "pv_antes": None, "pv": None,
                "pendencias": list(cascata["pendencias"]), "sr_automatico": None}
    sr = None
    if cascata["a_partir_de"] == "sr" and item["trimestre_sr"]:  # a cascata "pr" não recalcula o SR
        sr = {"trimestre": item["trimestre_sr"], "atualizado": False, "sr_antes": item["sr_antes"], "sr": None,
              "pendencias": list(item.get("pendencias_sr", []))}
    return {"meses_pr": item["meses_pr"], "atualizado": False, "pr_antes": item["pr_antes"], "pr": None,
            "pv_antes": item["pv_antes"], "pv": None, "pendencias": list(item["pendencias"]), "sr_automatico": sr}


def pv_automatico_legado(cascata: dict) -> list[dict]:
    """Campo antigo `pv_automatico` (um item por trimestre), sempre `atualizado=False`. Ver `pr_automatico_legado`."""
    return [{"trimestre": i["chave_pv"], "atualizado": False, "pv_antes": i["pv_antes"], "pv": None,
             "pendencias": list(i["pendencias"])} for i in cascata["trimestres"]]
