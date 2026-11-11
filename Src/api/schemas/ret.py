from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from Src.api.schemas.duplicatas import PossivelDuplicataValor


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
    ocr_disponivel: bool = True   # False: PDF de imagem (escaneado) não é lido neste computador


class SalvarRETRequest(BaseModel):
    documentos: list[DocumentoRET]
    periodo_padrao: str = ""  # para documentos sem mês no caminho


class RETSalvo(BaseModel):
    periodo: str
    ret: float
    qtd_documentos: int


class ProvaRealEmpresaRET(BaseModel):
    empresa: str
    tipo_encargo: str        # "EAT" | "EC"
    qtd: int
    valor: float


class ProvaRealRET(BaseModel):
    """A conta do RET gravado do mês refeita com os itens gravados."""
    periodo: str
    tem_itens: bool          # False: mês gravado só com o total, sem os itens
    qtd_documentos: int
    qtd_eat: int
    qtd_ec: int
    qtd_outros: int          # fora de EAT/EC: não entram no RET
    eat_bruto: float
    pis_cofins_rate: float
    eat_liquido: float       # eat_bruto × (1 − taxa)
    ec: float                # Σ itens EC
    ret_calculado: float | None = None
    ret_gravado: float | None = None
    diferenca: float | None = None
    confere: bool
    por_empresa: list[ProvaRealEmpresaRET] = []
    possiveis_duplicatas_valor: list[PossivelDuplicataValor] = []
    data_atualizacao: str = ""


class HistoricoRETLinha(BaseModel):
    periodo: str
    qtd_documentos: int
    ret_gravado: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
