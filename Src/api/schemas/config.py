from __future__ import annotations

from pydantic import BaseModel


class TrimestreConfig(BaseModel):
    label: str
    meses: list[str]


class TaxasConfig(BaseModel):
    pis_cofins_rate_ret: float
    pis_rate_auditoria: float
    cofins_rate_auditoria: float
    pis_cofins_rate_auditoria: float
    taxa_eur_brl: float
