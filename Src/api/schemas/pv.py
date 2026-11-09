from __future__ import annotations

from pydantic import BaseModel, Field


class PVResultado(BaseModel):
    pmpv: float
    pr: float
    pv: float


class PVSalvarRequest(BaseModel):
    periodo: str
    pmpv: float
    pr: float


class PVSalvarResponse(BaseModel):
    pv: float


class PVCriarPeriodoRequest(BaseModel):
    nome: str


class PVSalvo(BaseModel):
    pmpv: float
    pr: float
    pv: float
    data: str = ""


class PVTrimestreResultado(BaseModel):
    chave: str              # "Fev - Abr/2026"
    periodos: list[str]     # ["Fev/2026", "Mar/2026", "Abr/2026"]
    pmpv: float             # valores atuais dos módulos PMPV e PR
    pr: float
    pv: float
    salvo: PVSalvo | None = None  # PV já gravado (o que o Excel Final usa)
    avisos: list[str] = []


class PVTrimestreSalvarRequest(BaseModel):
    trimestre: str          # "Fev - Abr"
    ano: int = Field(ge=2000, le=2098)  # ano do 1º mês (Nov – Jan/2098 termina em 2099)
    pmpv: float = Field(allow_inf_nan=False)
    pr: float = Field(allow_inf_nan=False)


class PVTrimestreSalvarResponse(BaseModel):
    pv: float
    gravado_em: list[str]   # chave do trimestre + os 3 meses


class PVHistoricoTrimestre(BaseModel):
    """PV gravado de um trimestre fiscal (linha do histórico da tela PV)."""
    chave: str              # "Fev - Abr/2026"
    trimestre: str          # "Fev - Abr"
    ano: int                # ano do 1º mês
    pmpv: float
    pr: float
    pv: float
    data_atualizacao: str


class ProvaRealPV(BaseModel):
    """A conta do PV gravado do trimestre e se ele ainda bate com os módulos (GET /pv/prova-real)."""
    chave: str
    periodos: list[str]
    tem_salvo: bool                    # False: o trimestre ainda não tem PV gravado
    pmpv_gravado: float | None
    pr_gravado: float | None
    pv_gravado: float | None
    pv_da_soma: float | None           # PMPV gravado + PR gravado
    diferenca_conta: float | None
    conta_confere: bool                # PV gravado = PMPV gravado + PR gravado
    pmpv_atual: float                  # o dos módulos hoje
    pr_atual: float
    pv_atual: float
    pmpv_confere: bool                 # o PMPV gravado no PV é o PMPV de hoje
    pr_confere: bool                   # o PR gravado no PV é o PR de hoje
    confere: bool
    data_atualizacao: str
    avisos: list[str] = []


class PVAutomatico(BaseModel):
    """PV regravado ao salvar o PMPV ou o PR (servicos_pr_automatico.atualizar_pv)."""
    trimestre: str               # "Nov - Jan/2026" (ano do 1º mês); "" se deu erro inesperado
    atualizado: bool             # False = nada gravado; ver `pendencias`
    pv_antes: float | None       # PV que estava salvo antes (None = nunca salvo)
    pv: float | None             # PV novo gravado (None = não gravou)
    pendencias: list[str] = []
