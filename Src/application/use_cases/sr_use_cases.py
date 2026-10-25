"""Casos de uso do módulo SR trimestral (camada application).

Extraído de Src/Views/tela_sr.py (TelaSR._get_trimestre_labels,
_carregar_do_banco, _calcular, _salvar) — essa lógica hoje só existia dentro
da View, chamando DatabasePMPV diretamente. Ver SPEC_SR.md §4.

Fórmula por mês:
    diferenca  = VP - VF
    sr_parcela = diferenca * PR
    sr_selic   = sr_parcela * (1 + SELIC% / 100) + SR_anterior

SR TOTAL = soma de sr_selic de todos os meses do trimestre.
"""
from __future__ import annotations

import re
from typing import Any

from Src.common.periodos import TRIMESTRES_FISCAIS_ABREVS, labels_meses, normalizar_periodo
from Src.domain.ports.repositories import SRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqliteSRRepository
from Src.Services.servicos_consolidacao import ServicosConsolidacao


def labels_trimestre(meses: list[str], ano: int) -> list[str]:
    """Reproduz TelaSR._get_trimestre_labels: monta os labels 'Mes/Ano' do
    trimestre, avançando o ano na virada (ex.: Nov, Dez, Jan). A lógica fica
    em Src/common/periodos.labels_meses (também usada pelo PV)."""
    return labels_meses(meses, ano)


def _trimestre_label(labels: list[str]) -> str:
    return f"{labels[0]}_{labels[-1]}"


_RE_NOME_SESSAO = re.compile(r"^PMPV_([A-Za-z]{3})_+([A-Za-z]{3})_(\d{4})$")


def periodos_da_sessao(nome: str) -> list[str]:
    """Meses do calendário de uma sessão salva pelo PMPV ("PMPV_Fev___Abr_2026"
    → Fev/2026, Mar/2026, Abr/2026; "PMPV_Nov___Jan_2025" → Nov/2025 … Jan/2026).
    Nome em outro formato (ex.: "PMPV_13042026_0906") → []."""
    m = _RE_NOME_SESSAO.match(nome or "")
    if not m:
        return []
    inicio, fim, ano = m.group(1).capitalize(), m.group(2).capitalize(), int(m.group(3))
    for _, meses in TRIMESTRES_FISCAIS_ABREVS:
        if meses[0] == inicio and meses[-1] == fim:
            return [normalizar_periodo(p) for p in labels_trimestre(meses, ano)]
    return []


def vp_do_mes(repo: SRRepository, periodo: str) -> float:
    """VP (m³) de um mês do calendário, vindo do PMPV que cobre esse mês.

    1º a tabela vp_mensal (gravada ao salvar o PMPV); senão, a sessão mais
    recente cujo nome indica o trimestre que contém o mês. Nunca usa a posição
    (mês 1/2/3) de uma sessão de outro trimestre: era isso que deslocava o VP
    quando o SR (Jan–Mar) não coincidia com o trimestre do PMPV (Fev–Abr).
    Sem PMPV para o mês → 0.0.
    """
    vp = repo.buscar_vp_periodo(periodo)
    if vp is not None:
        return vp
    alvo = normalizar_periodo(periodo)
    for sessao in repo.listar_sessoes_id_nome():
        periodos = periodos_da_sessao(sessao.get("nome", ""))
        if alvo in periodos:
            dados_mes = repo.carregar_dados_mes(sessao["id"], periodos.index(alvo) + 1) or []
            return sum(float(l.get("volume", 0) or 0) for l in dados_mes)
    return 0.0


_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def chave_pr_do_mes(periodo: str) -> str:
    """Chave sob a qual a tela PR grava o PR do trimestre que contém o mês.

    Os PRs vão de Nov–Jan, Fev–Abr, Mai–Jul e Ago–Out; a chave é "Ago - Out/2026"
    (o ano é o do último mês do trimestre). Jul/2026 → "Mai - Jul/2026"."""
    mes, ano = normalizar_periodo(periodo).split("/")
    i = _ABREV.index(mes)
    inicio = i - ((i + 2) % 3)                       # mês de início do trimestre do PR (pode ser < 0: Nov/Dez do ano anterior)
    fim = inicio + 2
    return f"{_ABREV[inicio % 12]} - {_ABREV[fim % 12]}/{int(ano) + (fim // 12 - i // 12)}"


class SRUseCases:
    def __init__(self, repo: SRRepository | None = None):
        self.repo = repo or SqliteSRRepository()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.fechar()
        return False

    def carregar_vp_vf_pr(self, sessao_id: int, labels_meses: list[str]) -> list[dict[str, Any]]:
        """Para cada mês do trimestre, preenche VP (do PMPV que cobre aquele mês
        do calendário — ver `vp_do_mes`), VF (volume_final do CGF do período) e
        PR (1º o salvo no próprio SR; 2º o PR do trimestre salvo na tela PR; 3º estimado
        a partir de SCG/SR/VP; `pr_origem` diz qual: "salvo", "estimado" ou "ausente").
        `sessao_id` fica na assinatura por compatibilidade; o VP não depende dela."""
        resultado = []
        servicos_cons = ServicosConsolidacao()
        try:
            for periodo in labels_meses:
                vp = vp_do_mes(self.repo, periodo)

                resumo = self.repo.buscar_cgf_resumo(periodo)
                vf = float(resumo["volume_final"]) if resumo and resumo.get("volume_final") is not None else 0.0

                pr_row = self.repo.buscar_sr(periodo)
                pr = float((pr_row or {}).get("pr") or 0.0)
                pr_origem = "salvo" if pr else "ausente"
                if pr == 0.0:
                    pr_tela = self.repo.buscar_pr(chave_pr_do_mes(periodo))
                    pr = float((pr_tela or {}).get("pr") or 0.0)
                    pr_origem = "salvo" if pr else "ausente"
                if pr == 0.0 and vp > 0:
                    dados_cons = servicos_cons.buscar_consolidacao(periodo)
                    scg_m = float((dados_cons or {}).get("scg") or 0.0)
                    sr_m = float((pr_row or {}).get("sr") or 0.0)
                    pr = (scg_m + sr_m) / vp if vp else 0.0
                    pr_origem = "estimado" if pr else "ausente"

                resultado.append({"mes": periodo, "vp": vp, "vf": vf, "pr": pr, "pr_origem": pr_origem})
        finally:
            servicos_cons.fechar()
        return resultado

    @staticmethod
    def calcular_trimestre(linhas: list[dict[str, Any]]) -> dict[str, Any]:
        """Aplica a fórmula linha a linha. `linhas` é uma lista de
        {mes, vp, vf, pr, selic_mensal, sr_anterior}."""
        calculadas = []
        total = 0.0
        for linha in linhas:
            vp = float(linha.get("vp") or 0)
            vf = float(linha.get("vf") or 0)
            pr = float(linha.get("pr") or 0)
            selic = float(linha.get("selic_mensal") or 0)
            sr_anterior = float(linha.get("sr_anterior") or 0)

            diferenca = vp - vf
            sr_parcela = diferenca * pr
            sr_selic = sr_parcela * (1 + selic / 100) + sr_anterior

            calculadas.append({
                "mes": linha["mes"],
                "vp": vp,
                "vf": vf,
                "pr": pr,
                "selic_mensal": selic,
                "diferenca": diferenca,
                "sr_parcela": sr_parcela,
                "sr_selic": sr_selic,
                "sr_anterior": sr_anterior,
                "total": sr_selic,
            })
            total += sr_selic

        return {"linhas": calculadas, "total": total}

    def salvar_trimestre(
        self,
        labels_meses: list[str],
        periodo_referencia: str,
        linhas_calculadas: list[dict[str, Any]],
    ) -> float:
        """Persiste o trimestre: total em sr_resultados(periodo_referencia),
        cada mês em sr_resultados(periodo_mes), e todas as linhas em
        sr_trimestre. Retorna o total salvo."""
        total = sum(r["sr_selic"] for r in linhas_calculadas)
        vp_tot = sum(r["vp"] for r in linhas_calculadas)
        vf_tot = sum(r["vf"] for r in linhas_calculadas)

        self.repo.salvar_sr(periodo_referencia, vp_tot, vf_tot, 0.0, total)
        for i, r in enumerate(linhas_calculadas):
            periodo_mes = labels_meses[i] if i < len(labels_meses) else r["mes"]
            self.repo.salvar_sr(periodo_mes, r["vp"], r["vf"], r["pr"], r["sr_selic"])

        self.repo.salvar_sr_trimestre(_trimestre_label(labels_meses), linhas_calculadas)
        return total

    def buscar_trimestre(self, labels_meses: list[str]) -> list[dict[str, Any]]:
        return self.repo.buscar_sr_trimestre(_trimestre_label(labels_meses))
