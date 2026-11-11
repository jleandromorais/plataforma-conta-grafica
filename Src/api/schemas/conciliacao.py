from __future__ import annotations

from pydantic import BaseModel

from Src.api.schemas.duplicatas import PossivelDuplicataValor


class ItemConciliacao(BaseModel):
    arquivo: str
    caminho: str        # relativo à pasta enviada
    categoria: str      # "Receita" | "Despesa"
    valor: float        # negativo nas notas "cancelado"
    status: str         # "OK" | "REVISAR" | "ERRO"
    metodo: str


class TotaisConciliacao(BaseModel):
    total_receitas: float
    total_despesas: float
    rp: float           # despesas − receitas
    qtd_revisar: int


class ProcessarConciliacaoResponse(BaseModel):
    itens: list[ItemConciliacao]
    totais: TotaisConciliacao
    logs: list[str]
    ocr_disponivel: bool = True   # False: PDF de imagem (escaneado) não é lido neste computador


class SalvarConciliacaoRequest(BaseModel):
    periodo: str
    itens: list[ItemConciliacao]


class SalvarConciliacaoResponse(BaseModel):
    rp: float
    qtd_itens: int


class LadoProvaRealRP(BaseModel):
    qtd: int
    bruto: float
    liquido: float


class JaNoRETProvaRealRP(BaseModel):
    qtd: int
    bruto: float


class ItemProvaRealRP(BaseModel):
    arquivo: str
    nome: str
    lado: str      # "receita" | "despesa" | "ja_no_ret"
    tipo: str      # "PFP" | "TOP" | "OUTRA"
    numero: str
    valor: float
    liquido: float
    status: str
    repetida: bool = False


class DuplicadaProvaRealRP(BaseModel):
    tipo: str
    numero: str
    qtd: int
    valor_total: float
    liquido_total: float
    arquivos: list[str]


class ProvaRealRP(BaseModel):
    periodo: str
    tem_itens: bool
    qtd_itens: int
    taxa: float
    receitas: LadoProvaRealRP
    despesas: LadoProvaRealRP
    ja_no_ret: JaNoRETProvaRealRP
    rp_calculado: float | None = None
    rp_gravado: float | None = None
    diferenca: float | None = None
    confere: bool
    itens: list[ItemProvaRealRP] = []
    possiveis_duplicadas: list[DuplicadaProvaRealRP] = []
    possiveis_duplicatas_valor: list[PossivelDuplicataValor] = []
    data_atualizacao: str = ""


class HistoricoConciliacaoLinha(BaseModel):
    periodo: str
    qtd_itens: int
    total_receitas: float
    total_despesas: float
    rp_dos_itens: float   # despesas − receitas dos itens gravados
    rp_gravado: float     # consolidação (o que vai para o SCG/Excel)
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
