from __future__ import annotations

from pydantic import BaseModel


class RPVResultado(BaseModel):
    cgr: float
    cgf: float
    rpv: float


class RPVSalvarRequest(BaseModel):
    periodo: str
    cgr: float
    cgf: float


class RPVSalvarResponse(BaseModel):
    rpv: float
