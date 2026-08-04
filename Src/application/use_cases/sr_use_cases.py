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

from typing import Any

from Src.common.periodos import MESES_ABREVS
from Src.domain.ports.repositories import SRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqliteSRRepository
from Src.Services.servicos_consolidacao import ServicosConsolidacao


def labels_trimestre(meses: list[str], ano: int) -> list[str]:
    """Reproduz TelaSR._get_trimestre_labels: monta os labels 'Mes/Ano' do
    trimestre, avançando o ano quando o mês seguinte "volta" no calendário
    (ex.: Nov, Dez, Jan cruza virada de ano)."""
    resultado: list[str] = []
    ano_atual = ano
    for i, mes in enumerate(meses):
        idx = MESES_ABREVS.index(mes) if mes in MESES_ABREVS else i
        if i > 0:
            mes_ant = meses[i - 1]
            idx_ant = MESES_ABREVS.index(mes_ant) if mes_ant in MESES_ABREVS else i - 1
            if idx < idx_ant:
                ano_atual += 1
        resultado.append(f"{mes}/{ano_atual}")
    return resultado


def _trimestre_label(labels: list[str]) -> str:
    return f"{labels[0]}_{labels[-1]}"


class SRUseCases:
    def __init__(self, repo: SRRepository | None = None):
        self.repo = repo or SqliteSRRepository()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.fechar()
        return False

    def carregar_vp_vf_pr(self, sessao_id: int, labels_meses: list[str]) -> list[dict[str, Any]]:
        """Para cada mês do trimestre (1, 2, 3), preenche VP (soma de volume
        da sessão PMPV), VF (volume_final do CGF do período) e PR (salvo em
        sr_resultados, com fallback calculado a partir de SCG/SR/VP)."""
        resultado = []
        servicos_cons = ServicosConsolidacao()
        try:
            for i, periodo in enumerate(labels_meses, start=1):
                dados_mes = self.repo.carregar_dados_mes(sessao_id, i) or []
                vp = sum(float(l.get("volume", 0) or 0) for l in dados_mes)

                resumo = self.repo.buscar_cgf_resumo(periodo)
                vf = float(resumo["volume_final"]) if resumo and resumo.get("volume_final") is not None else 0.0

                pr_row = self.repo.buscar_sr(periodo)
                pr = float((pr_row or {}).get("pr") or 0.0)
                if pr == 0.0 and vp > 0:
                    dados_cons = servicos_cons.buscar_consolidacao(periodo)
                    scg_m = float((dados_cons or {}).get("scg") or 0.0)
                    sr_m = float((pr_row or {}).get("sr") or 0.0)
                    pr = (scg_m + sr_m) / vp if vp else 0.0

                resultado.append({"mes": periodo, "vp": vp, "vf": vf, "pr": pr})
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
