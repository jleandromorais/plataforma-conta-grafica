from __future__ import annotations

from pydantic import BaseModel


class TabelaLimpeza(BaseModel):
    tabela: str
    linhas: int


class LimpezaPeriodoResponse(BaseModel):
    periodo: str
    aplicado: bool = False  # False = simulação (nada foi apagado)
    total_linhas: int = 0
    tabelas: list[TabelaLimpeza] = []
