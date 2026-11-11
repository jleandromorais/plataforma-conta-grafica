from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from Src.api.schemas.comum import ProblemaArquivo
from Src.api.schemas.duplicatas import PossivelDuplicataValor


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
    # Modelo Alexandre: comparação valor a valor
    modelo: str = "generico"            # "alexandre" | "nt" | "generico"
    modelo_rotulo: str = ""             # "Modelo NT" — para mostrar
    tipo: str = "generico"              # "por_nota" | "por_supridor" | "generico" — define o layout da tela
    fontes_cgr: list[dict[str, Any]] = []   # [{"rotulo", "valor"|None}]: CGR das fontes da planilha, a comparar com o das notas
    notas_mes_na_planilha: bool = True  # False: a aba de NFs não tem o mês; só o total foi comparado
    cgr_auditoria: float | None = None
    cgr_planilha_notas: float | None = None
    cgr_planilha_conta_grafica: float | None = None
    divergencias_valor: list[dict[str, Any]] = []
    por_empresa: list[dict[str, Any]] = []


class ProcessarAuditoriaResponse(BaseModel):
    periodo_detectado: str
    qtd_xml_lidos: int
    qtd_pdf_lidos: int
    itens: list[ItemAuditoria]
    totais: TotaisAuditoria
    comparacao: ComparacaoAuditoria | None
    aviso_comparacao: str
    problemas: list[ProblemaArquivo] = []


class SalvarAuditoriaRequest(BaseModel):
    periodo: str
    itens: list[ItemAuditoria]


class SalvarAuditoriaResponse(BaseModel):
    cgr_liquido: float
    rpv: float
    qtd_itens: int


class ProvaRealEmpresa(BaseModel):
    empresa: str
    qtd_nfe: int
    qtd_cte: int
    qtd_devolucoes: int
    compras: float            # CGR das notas de compra (positivo)
    devolucoes: float         # CGR das devoluções (negativo)
    frete_fora_do_cgr: float  # valor dos CT-e de frete comum (não entra)
    cgr: float                # compras + devoluções


class NotaDigitada(BaseModel):
    """Nota incluída à mão no mês (não veio nos arquivos)."""
    id: int
    empresa: str
    tipo: str
    numero: str
    cgr_liquido: float
    motivo: str = ""


class IncluirNotaRequest(BaseModel):
    """Nota que só está na planilha, incluída no CGR do mês com o motivo (POST /auditoria/incluir-nota)."""
    periodo: str
    empresa: str
    numero: str
    cgr_liquido: float
    motivo: str
    valor_total: float | None = None
    volume_total: float | None = None
    linha_excel: int | None = None
    tipo: str | None = None


class ProvaRealAuditoria(BaseModel):
    """A conta do CGR gravado do mês, aberta por empresa (GET /auditoria/prova-real)."""
    periodo: str
    qtd_notas: int
    por_empresa: list[ProvaRealEmpresa]
    compras: float
    devolucoes: float
    frete_fora_do_cgr: float
    cgr_das_notas: float
    cgr_gravado: float | None
    diferenca: float | None
    confere: bool
    possiveis_duplicatas_valor: list[PossivelDuplicataValor] = []
    notas_digitadas: list[NotaDigitada] = []
    data_atualizacao: str


class HistoricoAuditoriaLinha(BaseModel):
    periodo: str
    qtd_notas: int
    cgr_gravado: float
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")


class DiferencaNota(BaseModel):
    empresa: str
    tipo: str
    numero: str
    situacao: str           # "so_no_gravado" | "so_no_processado" | "valor_diferente"
    gravado: float
    processado: float
    diferenca: float
    ocr: bool


class DiferencaEmpresa(BaseModel):
    empresa: str
    gravado: float
    processado: float
    diferenca: float


class DiferencasAuditoriaResponse(BaseModel):
    tem_notas_gravadas: bool
    cgr_gravado_notas: float
    cgr_processado: float
    diferenca: float
    por_empresa: list[DiferencaEmpresa]
    notas: list[DiferencaNota]
    qtd_notas_diferentes: int
    resumo: list[str]
