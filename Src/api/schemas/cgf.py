from __future__ import annotations

from pydantic import BaseModel

from Src.api.schemas.comum import ProblemaArquivo


class CGFVolumes(BaseModel):
    volume_faturado: float          # já sem consumo próprio
    volume_canceladas: float        # informativo: não entra no volume final
    volume_devolucoes: float
    volume_consumo_proprio: float   # informativo: já retirado do faturado
    volume_final: float             # faturado − devoluções


class CGFProcessarResponse(CGFVolumes):
    periodo_detectado: str          # "" quando o nome dos arquivos não indica o mês
    arquivos_ignorados: list[str]   # nome não diz se é faturada/cancelada/devolução
    problemas: list[ProblemaArquivo] = []
    logs: list[str]


class CGFSalvarRequest(CGFVolumes):
    periodo: str
    pmpv: float


class CGFCalcularRSRequest(BaseModel):
    periodo: str
    volume_final: float
    pmpv: float | None = None       # ausente: usa o PMPV salvo do mês


class CGFCalcularRSResponse(BaseModel):
    periodo: str
    pmpv: float                     # 0 quando não há PMPV
    pmpv_origem: str                # "manual" | "banco" | "ausente"
    volume_final: float
    cgf_rs: float | None            # None sem PMPV
    erros: list[str] = []           # frases de erro para o site (ex.: PMPV ausente)


class CGFSalvarResponse(BaseModel):
    cgf_rs: float
    rpv: float


class ProvaRealCGF(BaseModel):
    """A conta do CGF gravado do mês, aberta (GET /cgf/prova-real)."""
    periodo: str
    tem_resumo: bool                       # False: mês sem resumo de volumes gravado
    volume_faturado: float
    volume_canceladas: float               # informativo: não entra no volume final
    volume_devolucoes: float
    volume_consumo_proprio: float          # informativo: já retirado do faturado
    volume_final_calculado: float          # faturado − devoluções
    volume_final_gravado: float | None
    diferenca_volume: float | None
    volume_confere: bool
    pmpv: float | None                     # PMPV do mês (4 casas); None sem PMPV gravado
    cgf_calculado: float | None            # volume final × PMPV
    cgf_gravado: float | None
    diferenca_cgf: float | None
    cgf_confere: bool
    confere: bool                          # volume e CGF conferem
    erros: list[str] = []                  # frases de erro para o site; [] = nada errado
    data_atualizacao: str


class CGFHistoricoLinha(CGFVolumes):
    periodo: str
    cgf_rs: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
