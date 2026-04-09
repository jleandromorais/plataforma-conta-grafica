from __future__ import annotations

from Src.Database.database import DatabasePMPV


class ServicosSR:
    """
    Regras de negócio e acesso ao banco de dados para o módulo SR.

    SR = (VP − VF) × PR
        - VP: Volume Produzido — soma dos volumes informados de todas as
            empresas/meses de uma sessão salva no PMPV.
        - VF: Volume Faturado — volume real do trimestre, sem ponderação por dias.
    """

    def __init__(self, db: DatabasePMPV | None = None):
        self._db = db or DatabasePMPV()

    def listar_sessoes(self) -> list[dict]:
        """
        Retorna todas as sessões com VP e VF calculados, no formato:
        [{"id": 1, "nome": "Sessão X", "data_criacao": "...", "vp": 0.0, "vf": 0.0}, ...]
        """
        return self._db.listar_sessoes_com_volumes()

    def buscar_vp_vf(self, sessao_id: int) -> dict[str, float] | None:
        """
        Retorna {"vp": ..., "vf": ...} para a sessão informada, ou None se
        não encontrar.
        """
        sessoes = self._db.listar_sessoes_com_volumes()
        for s in sessoes:
            if s["id"] == sessao_id:
                return {"vp": s["vp"] or 0.0, "vf": s["vf"] or 0.0}
        return None

    @staticmethod
    def calcular_sr(vp: float, vf: float, pr: float) -> float:
        """SR = (VP − VF) × PR"""
        return (vp - vf) * pr

    @staticmethod
    def formatar_volume(valor: float) -> str:
        return f"{valor:,.2f} m³".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def formatar_brl(valor: float) -> str:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
