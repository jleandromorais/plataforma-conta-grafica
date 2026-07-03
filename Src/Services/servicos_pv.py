from __future__ import annotations

from Src.domain.ports.repositories import PRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePRRepository


class ServicosPV:
    """
    PV = PMPV + PR

    - PMPV: valor mensal salvo no módulo PMPV (tabela pmpv_mensal)
    - PR: preço regulatório final salvo no módulo PR (tabela pr_resultados)
    """

    def __init__(self, repo: PRRepository | None = None):
        self._repo = repo or SqlitePRRepository()

    @staticmethod
    def calcular_pv(pmpv: float, pr: float) -> float:
        return (pmpv or 0.0) + (pr or 0.0)

    @staticmethod
    def formatar_brl(valor: float) -> str:
        from Src.common.formatting import format_brl4
        return format_brl4(valor)

    @staticmethod
    def parse_brl(texto: str) -> float:
        from Src.common.formatting import parse_brl
        return parse_brl(texto)

    def obter_periodos(self) -> list[dict]:
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        return ServicosConsolidacao().obter_periodos()

    def criar_periodo(self, nome: str):
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        ServicosConsolidacao().criar_periodo(nome.strip())

    def buscar_dados_periodo(self, periodo: str) -> dict[str, float] | None:
        pmpv = self._repo.buscar_pmpv_mensal(periodo) or 0.0
        pr_row = self._repo.buscar_pr(periodo)
        pr = (pr_row or {}).get("pr") or 0.0

        pv_row = self._repo.buscar_pv(periodo)
        pv = (pv_row or {}).get("pv") or self.calcular_pv(pmpv, pr)

        return {"pmpv": pmpv, "pr": pr, "pv": pv}

    def salvar_valores(self, periodo: str, pmpv: float, pr: float) -> float:
        pmpv = pmpv or 0.0
        pr = pr or 0.0
        pv = self.calcular_pv(pmpv, pr)
        self._repo.salvar_pv(periodo, pmpv, pr, pv)
        return pv

    def gerar_texto_historico(self) -> str:
        periodos = self._repo.listar_pv()
        cab = (
            f"{'Período':<14} {'PMPV (R$/m³)':>18} {'PR (R$/m³)':>18} "
            f"{'PV (R$/m³)':>18}   {'Atualizado':<16}\n"
        )
        texto = cab + "─" * 92 + "\n"
        for p in periodos:
            pmpv = p.get("pmpv") or 0.0
            pr = p.get("pr") or 0.0
            pv = p.get("pv") or 0.0
            data = (p.get("data_atualizacao") or "")[:16]
            linha = (
                f"{p['periodo']:<14} "
                f"{self.formatar_brl(pmpv):>18} "
                f"{self.formatar_brl(pr):>18} "
                f"{self.formatar_brl(pv):>18}   "
                f"{data:<16}\n"
            )
            texto += linha
        return texto
