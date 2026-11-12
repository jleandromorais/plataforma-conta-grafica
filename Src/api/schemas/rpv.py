from __future__ import annotations

from pydantic import BaseModel


class RPVResultado(BaseModel):
    cgr: float
    cgf: float
    rpv: float


class RPVSalvarRequest(BaseModel):
    periodo: str
    cgr: float
    cgf: float


class RPVSalvarResponse(BaseModel):
    rpv: float


class RPVHistoricoLinha(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    rpv: float
    data_atualizacao: str


class OrigemCGR(BaseModel):
    tem_notas: bool                        # False: mês gravado só com o total, sem as notas
    valor_das_notas: float | None          # soma das notas gravadas (prova real da Auditoria)
    confere: bool


class OrigemCGF(BaseModel):
    tem_resumo: bool
    valor_calculado: float | None          # volume final × PMPV (prova real do CGF)
    confere: bool


class ProvaRealRPV(BaseModel):
    """A conta do RPV gravado do mês e de onde vêm CGR e CGF (GET /rpv/prova-real)."""
    periodo: str
    gravado: bool                          # False: nada gravado neste mês
    cgr: float
    cgf: float
    rpv_calculado: float                   # CGR − CGF
    rpv_gravado: float | None
    diferenca: float | None
    confere: bool
    origem_cgr: OrigemCGR
    origem_cgf: OrigemCGF
    data_atualizacao: str
    erros: list[str] = []   # frases de erro para o site; [] = nada errado
