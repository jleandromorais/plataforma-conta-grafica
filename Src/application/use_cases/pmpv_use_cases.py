from __future__ import annotations

from typing import Any

from Src.domain.ports.repositories import PMPVRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository
from Src.Services.servicos_pmpv import RegrasPMPV


class PMPVUseCases:
    """Casos de uso do módulo PMPV desacoplados da UI."""

    def __init__(self, repo: PMPVRepository | None = None):
        self.repo = repo or SqlitePMPVRepository()

    @staticmethod
    def calcular_resultados(
        dados_extraidos: dict[str, Any],
        valor_cg: float,
        dias_config: dict[str, int],
        lista_meses: list[str],
        idx_start: int,
    ) -> dict[str, Any]:
        return RegrasPMPV.calcular_resultados(
            dados_extraidos=dados_extraidos,
            valor_cg=valor_cg,
            dias_config=dias_config,
            lista_meses=lista_meses,
            idx_start=idx_start,
        )

    def salvar_sessao_completa(
        self,
        nome: str,
        dados_por_mes: dict[str, list[dict[str, Any]]],
        resultado: dict[str, Any],
    ) -> int:
        sessao_id = self.repo.criar_sessao(nome)
        for idx, lista in enumerate(dados_por_mes.values(), start=1):
            self.repo.salvar_dados_mes(sessao_id, idx, lista)

        self.repo.salvar_resultado(
            sessao_id,
            resultado["volume_total"],
            resultado["custo_total"],
            resultado["pmpv"],
            resultado["conta_grafica"],
            resultado["preco_final"],
        )
        return sessao_id

    def salvar_pmpv_mensal(self, periodo: str, pmpv: float):
        self.repo.salvar_pmpv_mensal(periodo, pmpv)

    def fechar(self):
        self.repo.fechar()
