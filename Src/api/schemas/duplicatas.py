"""Formato do aviso "Possível duplicata" (mesmo valor), usado nas provas reais de RP, RET e Auditoria."""
from __future__ import annotations

from pydantic import BaseModel


class PossivelDuplicataValor(BaseModel):
    grupo: str          # onde a repetição aconteceu: "Receita", "EAT · Empresa X", "NF-e · Empresa Y"
    valor: float        # o valor que se repete (bruto da nota)
    qtd: int
    notas: list[str]    # nome/número de cada nota
    ids: list[int] = []  # id gravado de cada nota (mesma ordem de `notas`): serve para tirá-la do cálculo


class RemoverNotaRequest(BaseModel):
    periodo: str
    id: int


class RemoverNotaResponse(BaseModel):
    periodo: str
    valor_gravado: float   # RP, RET ou CGR do mês depois de tirar a nota
    qtd_itens: int         # notas que ficaram gravadas no mês do grupo
