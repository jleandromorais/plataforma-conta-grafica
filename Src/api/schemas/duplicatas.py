"""Formato do aviso "Possível duplicata" (mesmo valor), usado nas provas reais de RP, RET e Auditoria."""
from __future__ import annotations

from pydantic import BaseModel

from Src.api.schemas.cascata import Cascata


class DetalheDuplicata(BaseModel):
    """Contexto de uma nota do aviso, para o analista ver se é cópia ou nota diferente."""
    id: int | None = None
    nome: str
    numero: str | None = None
    valor: float
    volume: float | None = None       # Auditoria: auditoria_itens.volume_total
    vencimento: str | None = None     # RET: ret_itens.data_vencimento (texto como veio do documento)


class PossivelDuplicataValor(BaseModel):
    grupo: str          # onde a repetição aconteceu: "Receita", "EAT · Empresa X", "NF-e · Empresa Y"
    valor: float        # o valor que se repete (bruto da nota)
    qtd: int
    notas: list[str]    # nome/número de cada nota
    ids: list[int] = []  # id gravado de cada nota (mesma ordem de `notas`): serve para tirá-la do cálculo
    detalhes: list[DetalheDuplicata] = []  # número, valor e, quando houver, volume ou vencimento de cada nota


class RemoverNotaRequest(BaseModel):
    periodo: str
    id: int


class RemoverNotaResponse(BaseModel):
    periodo: str
    valor_gravado: float   # RP, RET ou CGR do mês depois de tirar a nota
    qtd_itens: int         # notas que ficaram gravadas no mês do grupo
    cascata: Cascata | None = None  # prévia do SR, PR e PV (nada foi regravado); aprovar em /cascata/aplicar
