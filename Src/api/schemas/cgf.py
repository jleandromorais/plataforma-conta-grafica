from __future__ import annotations

from pydantic import BaseModel


class CGFVolumes(BaseModel):
    volume_faturado: float          # já sem consumo próprio
    volume_canceladas: float        # informativo: não entra no volume final
    volume_devolucoes: float
    volume_consumo_proprio: float   # informativo: já retirado do faturado
    volume_final: float             # faturado − devoluções


class CGFProcessarResponse(CGFVolumes):
    periodo_detectado: str          # "" quando o nome dos arquivos não indica o mês
    arquivos_ignorados: list[str]   # nome não diz se é faturada/cancelada/devolução
    logs: list[str]


class CGFSalvarRequest(CGFVolumes):
    periodo: str
    pmpv: float


class CGFSalvarResponse(BaseModel):
    cgf_rs: float
    rpv: float


class CGFHistoricoLinha(CGFVolumes):
    periodo: str
    cgf_rs: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
