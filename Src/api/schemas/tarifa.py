"""Formato da tarifa média de um trimestre (GET /tarifa/media). Só leitura."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TarifaMargem(BaseModel):
    ano: int
    mb: float | None = None                          # null quando a origem é "ausente"
    origem: Literal["salva", "padrao", "ausente"]


class TarifaDoAno(BaseModel):
    ano: int
    mb: float | None = None
    tarifa_media: float | None = None                # PV + MB; null se faltar o PV ou a MB


class TarifaMediaResposta(BaseModel):
    trimestre: str                                   # "Nov/2025_Jan/2026"
    chave_pv: str                                    # "Nov - Jan/2025" (ano do 1º mês)
    pv_gravado: float | None = None
    margens: list[TarifaMargem] = []
    tarifas: list[TarifaDoAno] = []
    cruza_ano: bool = False
    aviso: str | None = None
    motivo: str | None = None                        # por que alguma tarifa é null
