from __future__ import annotations

from Src.Database.database import DatabasePMPV
from Src.domain.ports.repositories import ConsolidacaoRepository, PMPVRepository


class SqliteConsolidacaoRepository(ConsolidacaoRepository):
    def __init__(self, db: DatabasePMPV | None = None):
        self.db = db or DatabasePMPV()

    def listar_periodos(self):
        return self.db.listar_periodos()

    def criar_periodo_consolidacao(self, periodo: str, obs: str = "") -> int:
        return self.db.criar_periodo_consolidacao(periodo, obs)

    def apagar_periodo(self, periodo: str):
        self.db.apagar_periodo(periodo)

    def buscar_consolidacao(self, periodo: str):
        return self.db.buscar_consolidacao(periodo)

    def atualizar_cgr(self, periodo: str, valor: float):
        self.db.atualizar_cgr(periodo, valor)

    def atualizar_cgf(self, periodo: str, valor: float):
        self.db.atualizar_cgf(periodo, valor)

    def atualizar_ret(self, periodo: str, valor: float):
        self.db.atualizar_ret(periodo, valor)

    def atualizar_rp(self, periodo: str, valor: float):
        self.db.atualizar_rp(periodo, valor)

    def atualizar_campos_consolidacao(self, periodo: str, **campos: float):
        self.db.atualizar_campos_consolidacao(periodo, **campos)

    def salvar_rpv(self, periodo: str, rpv: float):
        self.db.salvar_rpv(periodo, rpv)

    def salvar_scg(self, periodo: str, scg: float):
        self.db.salvar_scg(periodo, scg)

    def fechar(self):
        self.db.fechar()


class SqlitePMPVRepository(PMPVRepository):
    def __init__(self, db: DatabasePMPV | None = None):
        self.db = db or DatabasePMPV()

    def criar_sessao(self, nome: str, observacoes: str = "") -> int:
        return self.db.criar_sessao(nome, observacoes)

    def salvar_dados_mes(self, sessao_id: int, mes: int, dados):
        return self.db.salvar_dados_mes(sessao_id, mes, dados)

    def salvar_resultado(self, sessao_id: int, vol_tot: float, custo_tot: float, pmpv: float, cg: float, final: float):
        return self.db.salvar_resultado(sessao_id, vol_tot, custo_tot, pmpv, cg, final)

    def salvar_pmpv_mensal(self, periodo: str, pmpv: float):
        self.db.salvar_pmpv_mensal(periodo, pmpv)

    def listar_periodos(self):
        return self.db.listar_periodos()

    def listar_pmpv_mensal(self):
        return self.db.listar_pmpv_mensal()

    def buscar_pmpv_mensal(self, periodo: str):
        return self.db.buscar_pmpv_mensal(periodo)

    def fechar(self):
        self.db.fechar()
