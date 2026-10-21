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


class CGFSalvarResponse(BaseModel):
    cgf_rs: float
    rpv: float


class CGFHistoricoLinha(CGFVolumes):
    periodo: str
    cgf_rs: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
