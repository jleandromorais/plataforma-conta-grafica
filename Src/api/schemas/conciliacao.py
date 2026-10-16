from __future__ import annotations

from pydantic import BaseModel


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


class SalvarConciliacaoRequest(BaseModel):
    periodo: str
    itens: list[ItemConciliacao]


class SalvarConciliacaoResponse(BaseModel):
    rp: float
    qtd_itens: int


class HistoricoConciliacaoLinha(BaseModel):
    periodo: str
    qtd_itens: int
    total_receitas: float
    total_despesas: float
    rp_dos_itens: float   # despesas − receitas dos itens gravados
    rp_gravado: float     # consolidação (o que vai para o SCG/Excel)
    data_atualizacao: str
    periodo_valido: bool = True  # False: período inválido gravado (ex.: "Teste2")
