from __future__ import annotations

from typing import Any

from Src.domain.ports.repositories import ConsolidacaoRepository
from Src.infrastructure.repositories.sqlite_repositories import SqliteConsolidacaoRepository


class ServicosConsolidacao:
    """Centraliza regras e orquestração da consolidação SCG."""

    def __init__(self, repo: ConsolidacaoRepository | None = None):
        self.repo = repo or SqliteConsolidacaoRepository()

    @staticmethod
    def calcular_rpv(cgr: float, cgf: float) -> float:
        """Regra oficial do RPV: CGR - CGF."""
        return (cgr or 0.0) - (cgf or 0.0)

    @classmethod
    def calcular_scg(cls, cgr: float, cgf: float, ret: float, rp: float) -> float:
        """
        Regra oficial do SCG.

        Mantemos o comportamento já praticado pelo sistema:
        SCG = RPV + RET + RP, com RPV = CGR - CGF.
        """
        rpv = cls.calcular_rpv(cgr, cgf)
        return rpv + (ret or 0.0) + (rp or 0.0)

    @staticmethod
    def _normalizar_dados(dados: dict[str, Any] | None) -> dict[str, Any] | None:
        if not dados:
            return None

        cgr = dados.get("cgr") or 0.0
        cgf = dados.get("cgf") or 0.0
        ret = dados.get("ret") or 0.0
        rp = dados.get("rp") or 0.0
        rpv = dados.get("rpv")
        scg = dados.get("scg")

        if rpv is None:
            rpv = ServicosConsolidacao.calcular_rpv(cgr, cgf)
        if scg is None:
            scg = ServicosConsolidacao.calcular_scg(cgr, cgf, ret, rp)

        normalizado = dict(dados)
        normalizado.update({
            "cgr": cgr,
            "cgf": cgf,
            "ret": ret,
            "rp": rp,
            "rpv": rpv,
            "scg": scg,
        })
        return normalizado

    def fechar(self):
        self.repo.fechar()

    def obter_periodos(self) -> list[dict[str, Any]]:
        return self.repo.listar_periodos()

    def criar_periodo(self, periodo: str, observacoes: str = "") -> int:
        return self.repo.criar_periodo_consolidacao(periodo.strip(), observacoes)

    def apagar_periodo(self, periodo: str):
        self.repo.apagar_periodo(periodo)

    def buscar_consolidacao(self, periodo: str) -> dict[str, Any] | None:
        return self._normalizar_dados(self.repo.buscar_consolidacao(periodo))

    def salvar_cgr(self, periodo: str, valor: float) -> dict[str, Any]:
        self.repo.atualizar_cgr(periodo, valor)
        return self.recalcular_rpv(periodo)

    def salvar_cgf(self, periodo: str, valor: float) -> dict[str, Any]:
        self.repo.atualizar_cgf(periodo, valor)
        return self.recalcular_rpv(periodo)

    def salvar_ret(self, periodo: str, valor: float) -> dict[str, Any]:
        self.repo.atualizar_ret(periodo, valor)
        return self.buscar_consolidacao(periodo)

    def salvar_rp(self, periodo: str, valor: float) -> dict[str, Any]:
        self.repo.atualizar_rp(periodo, valor)
        return self.buscar_consolidacao(periodo)

    def salvar_valores(self, periodo: str, **campos: float) -> dict[str, Any]:
        if campos:
            self.repo.atualizar_campos_consolidacao(periodo, **campos)
        return self.recalcular_rpv(periodo)

    def recalcular_rpv(self, periodo: str) -> dict[str, Any]:
        dados = self.buscar_consolidacao(periodo) or {
            "cgr": 0.0,
            "cgf": 0.0,
            "ret": 0.0,
            "rp": 0.0,
        }
        rpv = self.calcular_rpv(dados.get("cgr", 0.0), dados.get("cgf", 0.0))
        self.repo.salvar_rpv(periodo, rpv)
        return self.buscar_consolidacao(periodo)

    def recalcular_scg(self, periodo: str) -> dict[str, Any]:
        dados = self.recalcular_rpv(periodo)
        scg = self.calcular_scg(
            dados.get("cgr", 0.0),
            dados.get("cgf", 0.0),
            dados.get("ret", 0.0),
            dados.get("rp", 0.0),
        )
        self.repo.salvar_scg(periodo, scg)
        return self.buscar_consolidacao(periodo)
