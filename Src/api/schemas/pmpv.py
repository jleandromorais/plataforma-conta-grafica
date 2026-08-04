from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CalcularPMPVRequest(BaseModel):
    dados_extraidos: dict[str, Any]
    valor_cg: float
    dias_config: dict[str, int]
    lista_meses: list[str]
    idx_start: int = 0


class SalvarPMPVRequest(BaseModel):
    nome: str
    dados_por_mes: dict[str, list[dict[str, Any]]]
    resultado: dict[str, Any]


class SalvarPMPVResponse(BaseModel):
    sessao_id: int


class PMPVMensalRequest(BaseModel):
    pmpv: float


class PMPVMensalResponse(BaseModel):
    pmpv: float


class TrimestreAtivoRequest(BaseModel):
    meses: list[str]


class TrimestreAtivoResponse(BaseModel):
    meses: list[str]
