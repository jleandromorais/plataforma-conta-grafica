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
    # Meses do trimestre (ex.: ["Fev/2026","Mar/2026","Abr/2026"]). Quando
    # informado, grava também o PMPV mensal de cada mês e o trimestre ativo,
    # como o "Salvar Sessão" do desktop.
    periodos: list[str] = []


class LinhaEmpresa(BaseModel):
    empresa: str
    molecula: float
    transporte: float
    logistica: float
    volume: float


class ImportarMemoriaResponse(BaseModel):
    meses: dict[str, list[LinhaEmpresa]]
    erros: list[str]
    meses_encontrados: list[str] = []  # meses que a planilha tem (ex.: "Nov/2025")


class SalvarPMPVResponse(BaseModel):
    sessao_id: int


class PMPVHistoricoLinha(BaseModel):
    id: int
    nome: str
    data_criacao: str | None
    pmpv: float
    conta_grafica: float
    preco_final: float
    vp: float


class PMPVMensalRequest(BaseModel):
    pmpv: float


class PMPVMensalResponse(BaseModel):
    pmpv: float


class TrimestreAtivoRequest(BaseModel):
    meses: list[str]


class TrimestreAtivoResponse(BaseModel):
    meses: list[str]
