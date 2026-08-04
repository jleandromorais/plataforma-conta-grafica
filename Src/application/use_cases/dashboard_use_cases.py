"""Caso de uso do Dashboard (camada application).

Replica a lógica de agregação que hoje vive em Src/Views/dashboard_resumo.py
(PainelResumo._carregar_banco / _atualizar_kpis / _agrupar_trimestres),
extraída para ser reutilizável pela API sem depender de Tkinter/matplotlib.

Modelo de dados real do dashboard: KPIs mensais de CGR, RET, CGF, RP, RPV,
SCG (tabela `consolidacao`) + série de PMPV mensal — não "parcela de
recuperação"/"SR total" (esses conceitos pertencem aos módulos PR/SR, não a
este dashboard). Ver Front_end/TASKS.md item §2 para o achado que motivou
esta extração.
"""
from __future__ import annotations

import re

from Src.common.periodos import TRIMESTRES_CIVIS
from Src.domain.ports.repositories import ConsolidacaoRepository, PMPVRepository
from Src.infrastructure.repositories.sqlite_repositories import (
    SqliteConsolidacaoRepository,
    SqlitePMPVRepository,
)

_MESES_ORDEM = {
    m: i
    for i, m in enumerate(
        ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    )
}
_PERIODO_VALIDO = re.compile(r"^(" + "|".join(_MESES_ORDEM) + r")/(\d{4})$")


def _chave(periodo: str) -> tuple[int, int]:
    m = _PERIODO_VALIDO.match(periodo)
    mes, ano = m.groups()
    return (int(ano), _MESES_ORDEM[mes])


class DashboardUseCases:
    """Monta o resumo do dashboard a partir de Consolidação + PMPV mensal."""

    def __init__(
        self,
        consolidacao_repo: ConsolidacaoRepository | None = None,
        pmpv_repo: PMPVRepository | None = None,
    ):
        self._consolidacao_repo = consolidacao_repo or SqliteConsolidacaoRepository()
        self._pmpv_repo = pmpv_repo or SqlitePMPVRepository()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._consolidacao_repo.fechar()
        self._pmpv_repo.fechar()
        return False

    def montar_resumo(self, ano: str | None = None) -> dict:
        cons = self._listar_consolidacao_valida()
        pmpvs = self._listar_pmpv_valido()

        if ano:
            cons = [c for c in cons if _chave(c["periodo"])[0] == int(ano)]
            pmpvs = [p for p in pmpvs if _chave(p["periodo"])[0] == int(ano)]

        historico = [
            {
                "periodo": c["periodo"],
                "cgr": float(c.get("cgr") or 0),
                "ret": float(c.get("ret") or 0),
                "cgf": float(c.get("cgf") or 0),
                "rp": float(c.get("rp") or 0),
                "rpv": float(c.get("rpv") or 0),
                "scg": float(c.get("scg") or 0),
            }
            for c in cons
        ]

        ultimo_mes = None
        if historico:
            atual = historico[-1]
            anterior = historico[-2] if len(historico) >= 2 else None
            variacao = None
            if anterior and anterior["scg"] != 0:
                variacao = (atual["scg"] - anterior["scg"]) / abs(anterior["scg"]) * 100
            ultimo_mes = {**atual, "variacao_scg_pct": variacao}

        serie_pmpv = [
            {"periodo": p["periodo"], "valor": float(p.get("pmpv") or 0)} for p in pmpvs
        ]
        serie_scg = [{"periodo": c["periodo"], "valor": c["scg"]} for c in historico]

        return {
            "ano_filtro": ano,
            "ultimo_mes": ultimo_mes,
            "historico": historico,
            "serie_pmpv": serie_pmpv,
            "serie_scg": serie_scg,
        }

    def _listar_consolidacao_valida(self) -> list[dict]:
        # ConsolidacaoRepository (port) não expõe listar_consolidacao_completa
        # hoje, só listar_periodos — usamos o db subjacente do repositório
        # SQLite diretamente aqui (leitura, sem grafar).
        db = getattr(self._consolidacao_repo, "db", None)
        registros = db.listar_consolidacao_completa() if db else self._consolidacao_repo.listar_periodos()
        return sorted(
            (r for r in registros if _PERIODO_VALIDO.match(r.get("periodo", ""))),
            key=lambda r: _chave(r["periodo"]),
        )

    def _listar_pmpv_valido(self) -> list[dict]:
        registros = self._pmpv_repo.listar_pmpv_mensal()
        return sorted(
            (r for r in registros if _PERIODO_VALIDO.match(r.get("periodo", ""))),
            key=lambda r: _chave(r["periodo"]),
        )
