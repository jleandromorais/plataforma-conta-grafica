"""Formato do aviso "Possível duplicata" (mesmo valor), usado nas provas reais de RP, RET e Auditoria."""
from __future__ import annotations

from pydantic import BaseModel


class PossivelDuplicataValor(BaseModel):
    grupo: str          # onde a repetição aconteceu: "Receita", "EAT · Empresa X", "NF-e · Empresa Y"
    valor: float        # o valor que se repete (bruto da nota)
    qtd: int
    notas: list[str]    # nome/número de cada nota do grupo
