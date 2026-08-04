from __future__ import annotations

from pydantic import BaseModel


class SCGPeriodo(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    rpv: float
    ret: float
    rp: float
    scg: float


class SalvarManualRequest(BaseModel):
    periodo: str
    cgr: float
    cgf: float
    ret: float
    rp: float


class RPVResponse(BaseModel):
    rpv: float
