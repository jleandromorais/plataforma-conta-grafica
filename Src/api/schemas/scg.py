from __future__ import annotations

from pydantic import BaseModel

from Src.api.schemas.pr import PRAutomatico


class SCGPeriodo(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    rpv: float
    ret: float
    rp: float
    scg: float


class SCGSalvoResponse(SCGPeriodo):
    pr_automatico: PRAutomatico  # PR e PV do trimestre, regravados junto


class SCGReparoMes(BaseModel):
    periodo: str
    scg_gravado: float | None = None   # coluna crua antes do reparo (None = nunca gravada)
    scg_calculado: float               # RPV + RET + RP, o valor que fica depois do reparo


class SCGReparoIgnorado(BaseModel):
    periodo: str
    motivo: str                        # ex.: "falta RP"


class SCGReparoResponse(BaseModel):
    """Resultado de POST /scg/reparar-historico (simulação ou reparo de verdade)."""
    aplicado: bool                     # False = só simulou, nada foi gravado
    meses: list[SCGReparoMes] = []     # meses com o scg gravado diferente do calculado
    ignorados: list[SCGReparoIgnorado] = []
    sem_divergencia: int = 0


class SalvarManualRequest(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    ret: float
    rp: float


class RPVResponse(BaseModel):
    rpv: float


class SCGValores(BaseModel):
    cgr: float
    cgf: float
    rpv: float
    ret: float
    rp: float
    scg: float


class SCGComparacao(BaseModel):
    """Os dois lados que podem divergir num mês (ver ServicosSCG.buscar_dados_fontes)."""
    periodo: str
    modulos: SCGValores          # recalculado dos itens de Auditoria/Conciliação
    gravado: SCGValores | None   # consolidação (o que o Excel Final usa); None = período novo


class SCGHistoricoLinha(SCGValores):
    periodo: str
    diverge: bool  # módulos ≠ gravado em algum valor


class OrigemCGRSCG(BaseModel):
    tem_itens: bool                      # False: mês gravado só com o total, sem as notas
    valor_das_notas: float | None = None  # soma das notas gravadas (prova real da Auditoria)
    confere: bool


class OrigemItensSCG(BaseModel):
    """Prova real de RET e RP, que guardam itens."""
    tem_itens: bool                      # False: mês gravado só com o total, sem os itens
    valor_calculado: float | None = None  # refeito com os itens gravados
    confere: bool


class OrigemCGFSCG(BaseModel):
    tem_resumo: bool
    valor_calculado: float | None = None  # volume final × PMPV
    confere: bool


class OrigensSCG(BaseModel):
    cgr: OrigemCGRSCG
    cgf: OrigemCGFSCG
    ret: OrigemItensSCG
    rp: OrigemItensSCG


class ProvaRealSCG(BaseModel):
    """A conta do SCG gravado do mês e de onde vem cada número (GET /scg/prova-real)."""
    periodo: str
    gravado: bool                        # False: mês sem consolidação gravada
    cgr: float
    cgf: float
    rpv: float
    ret: float
    rp: float
    rpv_calculado: float                 # CGR − CGF
    scg_calculado: float                 # RPV calculado + RET + RP
    scg_gravado: float | None = None
    diferenca: float | None = None
    confere: bool
    origens: OrigensSCG
    data_atualizacao: str = ""
