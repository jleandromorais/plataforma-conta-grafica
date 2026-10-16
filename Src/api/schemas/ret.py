from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentoRET(BaseModel):
    """Um PDF de encargo lido por RegrasRET.extrair_dados_pdf."""
    model_config = ConfigDict(extra="allow")  # demais campos do extrator passam adiante

    arquivo: str
    caminho: str             # relativo à pasta enviada (define EAT/EC e o mês)
    tipo_encargo: str        # "EAT" | "EC" | "Penalidades…" | "TOP" | "Outros"
    empresa: str
    nota_tipo: str
    numero_nd: str
    data_vencimento: str
    valor_total: float
    mes_ref: str = ""
    valores_encontrados: list[Any] = []


class RETMes(BaseModel):
    periodo: str
    qtd_documentos: int
    eat_bruto: float         # Σ documentos da pasta EAT
    ec_docs_total: float     # Σ documentos da pasta EC
    ret: float               # EAT × (1 − PIS/COFINS) + EC
    qtd_outros: int          # fora das pastas EAT/EC: não entram no RET


class ProcessarRETResponse(BaseModel):
    periodo_detectado: str
    qtd_lidos: int
    qtd_ignorados: int       # notas fiscais e pastas "Notas Fiscais"
    pis_cofins_rate: float
    meses: list[RETMes]
    documentos: list[DocumentoRET]


class SalvarRETRequest(BaseModel):
    documentos: list[DocumentoRET]
    periodo_padrao: str = ""  # para documentos sem mês no caminho


class RETSalvo(BaseModel):
    periodo: str
    ret: float
    qtd_documentos: int


class HistoricoRETLinha(BaseModel):
    periodo: str
    qtd_documentos: int
    ret_gravado: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
