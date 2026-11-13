from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from Src.api.schemas.pv import PVAutomatico


class CalcularPMPVRequest(BaseModel):
    dados_extraidos: dict[str, Any]
    valor_cg: float
    dias_config: dict[str, int]
    lista_meses: list[str]
    idx_start: int = 0
    # Margem regulatória do ano (R$/m³). Informada: a resposta traz também a Tarifa Média (PV + margem).
    margem_regulatoria: float | None = None


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
    pv_automatico: list[PVAutomatico] = []  # PV dos trimestres desses meses, regravado junto


class SessaoDoTrimestre(BaseModel):
    """O que já foi salvo para um trimestre: a tela PMPV preenche a tabela com isto ao trocar de trimestre."""
    encontrada: bool
    sessao_id: int | None = None
    nome: str | None = None
    data_criacao: str | None = None
    pmpv: float | None = None
    conta_grafica: float | None = None
    preco_final: float | None = None
    meses: dict[str, list[LinhaEmpresa]] = {}   # "Mai/2026" → empresas; `volume` = QDC (m³/dia)


class PMPVHistoricoLinha(BaseModel):
    id: int
    nome: str
    data_criacao: str | None
    pmpv: float
    conta_grafica: float
    preco_final: float
    vp: float


class ProvaRealEmpresaPMPV(BaseModel):
    empresa: str
    molecula: float
    transporte: float
    logistica: float
    preco: float          # molécula + transporte + logística (R$/m³)
    volume: float         # m³
    custo: float          # preço × volume (R$)


class ProvaRealMesPMPV(BaseModel):
    mes: int              # 1, 2 ou 3 do trimestre
    empresas: list[ProvaRealEmpresaPMPV]
    volume: float
    custo: float
    pmpv_do_mes: float


class ProvaRealPMPV(BaseModel):
    """A conta do PMPV de uma sessão salva, refeita com as linhas gravadas (GET /pmpv/prova-real)."""
    sessao_id: int
    nome: str
    data_criacao: str | None
    tem_linhas: bool                       # False: sessão sem linhas com volume
    tem_resultado: bool                    # False: sessão sem resultado gravado
    meses: list[ProvaRealMesPMPV]
    custo_total_calculado: float | None
    custo_total_gravado: float | None
    diferenca_custo: float | None
    volume_total: float | None             # Σ volume (o VP da sessão)
    vp_gravado: float | None
    diferenca_vp: float | None
    pmpv_calculado: float | None           # Σ(preço × volume) ÷ Σ volume
    pmpv_gravado: float | None
    diferenca_pmpv: float | None
    conta_grafica: float | None            # a gravada: não é recalculada aqui (vem do PR)
    preco_final_calculado: float | None    # PMPV calculado + Conta Gráfica
    preco_final_gravado: float | None
    diferenca_preco_final: float | None
    confere: bool


class MargemRegulatoria(BaseModel):
    """Margem regulatória de um ano e de onde ela vem (GET /pmpv/margem-regulatoria)."""
    ano: int
    margem: float | None                   # None: ninguém informou ainda
    origem: str                            # "salva" | "padrao" | "ausente"


class MargemRegulatoriaRequest(BaseModel):
    ano: int
    margem: float


class PMPVMensalRequest(BaseModel):
    pmpv: float


class PMPVMensalResponse(BaseModel):
    pmpv: float


class TrimestreAtivoRequest(BaseModel):
    meses: list[str]


class TrimestreAtivoResponse(BaseModel):
    meses: list[str]
