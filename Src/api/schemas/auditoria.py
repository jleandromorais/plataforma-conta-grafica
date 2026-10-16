from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ItemAuditoria(BaseModel):
    empresa: str
    tipo: str               # "NF-e" | "CT-e"
    numero: str
    valor_total: float
    icms: float             # R$
    icms_taxa: float        # decimal (0.12 = 12%)
    pis: float
    cofins: float
    volume: int
    status: str             # "OK" (XML) | "OCR" (PDF)
    volume_total: float
    caminho: str            # relativo à pasta enviada — define se é devolução
    # Calculados (somente leitura; ignorados ao salvar)
    cgr_liquido: float = 0.0
    integra_cgr: bool = False
    devolucao: bool = False


class EmpresaTotais(BaseModel):
    empresa: str
    qtd_nfe: int
    qtd_cte: int
    valor_total: float
    cgr_liquido: float
    frete_fora_do_cgr: float


class TotaisAuditoria(BaseModel):
    qtd_nfe: int
    qtd_cte: int
    qtd_devolucoes: int
    valor_total_geral: float
    icms_cgr: float
    cgr_liquido: float
    por_empresa: list[EmpresaTotais]


class ComparacaoAuditoria(BaseModel):
    periodo: str
    qtd_em_ambas: int
    notas_apenas_auditoria: list[dict[str, Any]]
    notas_apenas_planilha: list[dict[str, Any]]
    abas_planilha: list[str]
    abas_do_periodo: list[str]
    avisos: list[str]


class ProcessarAuditoriaResponse(BaseModel):
    periodo_detectado: str
    qtd_xml_lidos: int
    qtd_pdf_lidos: int
    itens: list[ItemAuditoria]
    totais: TotaisAuditoria
    comparacao: ComparacaoAuditoria | None
    aviso_comparacao: str


class SalvarAuditoriaRequest(BaseModel):
    periodo: str
    itens: list[ItemAuditoria]


class SalvarAuditoriaResponse(BaseModel):
    cgr_liquido: float
    rpv: float
    qtd_itens: int


class HistoricoAuditoriaLinha(BaseModel):
    periodo: str
    qtd_notas: int
    cgr_gravado: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
