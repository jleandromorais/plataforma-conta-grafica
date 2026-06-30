from __future__ import annotations

from Src.Database.database import DatabasePMPV
from Src.domain.ports.repositories import (
    ConsolidacaoRepository,
    PMPVRepository,
    PRRepository,
    SRRepository,
)


class SqliteConsolidacaoRepository(ConsolidacaoRepository):
    def __init__(self, db: DatabasePMPV | None = None):
        self.db = db or DatabasePMPV()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.__exit__(exc_type, exc_val, exc_tb)
        return False

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.__exit__(exc_type, exc_val, exc_tb)
        return False

    def criar_sessao(self, nome: str, observacoes: str = "") -> int:
        return self.db.criar_sessao(nome, observacoes)

    def salvar_dados_mes(self, sessao_id: int, mes: int, dados):
        return self.db.salvar_dados_mes(sessao_id, mes, dados)

    def salvar_resultado(self, sessao_id: int, vol_tot: float, vp_tot: float, vf_tot: float, custo_tot: float, pmpv: float, cg: float, final: float):
        return self.db.salvar_resultado(sessao_id, vol_tot, vp_tot, vf_tot, custo_tot, pmpv, cg, final)

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


class SqliteSRRepository(SRRepository):
    def __init__(self, db: DatabasePMPV | None = None):
        self.db = db or DatabasePMPV()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.__exit__(exc_type, exc_val, exc_tb)
        return False

    def listar_sessoes_com_volumes(self):
        return self.db.listar_sessoes_com_volumes()

    def fechar(self):
        self.db.fechar()


class SqlitePRRepository(PRRepository):
    def __init__(self, db: DatabasePMPV | None = None):
        self.db = db or DatabasePMPV()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db.__exit__(exc_type, exc_val, exc_tb)
        return False

    # PR
    def listar_sr(self):
        return self.db.listar_sr()

    def buscar_sr(self, periodo: str):
        return self.db.buscar_sr(periodo)

    def buscar_pr(self, periodo: str):
        return self.db.buscar_pr(periodo)

    def salvar_pr(self, periodo: str, scg: float, sr: float, vp: float, pr: float):
        return self.db.salvar_pr(periodo, scg, sr, vp, pr)

    def listar_pr(self):
        return self.db.listar_pr()

    # PV
    def buscar_pmpv_mensal(self, periodo: str):
        return self.db.buscar_pmpv_mensal(periodo)

    def buscar_pv(self, periodo: str):
        return self.db.buscar_pv(periodo)

    def salvar_pv(self, periodo: str, pmpv: float, pr: float, pv: float):
        return self.db.salvar_pv(periodo, pmpv, pr, pv)

    def listar_pv(self):
        return self.db.listar_pv()

    def fechar(self):
        self.db.fechar()

