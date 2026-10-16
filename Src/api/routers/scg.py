from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_scg
from Src.api.schemas.scg import (
    RPVResponse,
    SalvarManualRequest,
    SCGComparacao,
    SCGHistoricoLinha,
    SCGPeriodo,
    SCGValores,
)
from Src.Services.servicos_scg import ServicosSCG
from Src.common.periodos import is_periodo_valido

router = APIRouter(prefix="/scg", tags=["SCG"])

_CAMPOS = ("cgr", "cgf", "ret", "rp", "scg")
_TOLERANCIA = 0.01  # R$ — diferenças de centavo por arredondamento não contam


def _diverge(modulos: dict, gravado: dict | None) -> bool:
    if gravado is None:
        return any(abs(modulos[c]) > _TOLERANCIA for c in _CAMPOS)
    return any(abs(modulos[c] - gravado[c]) > _TOLERANCIA for c in _CAMPOS)


@router.get("/periodos")
def listar_periodos(servico: ServicosSCG = Depends(get_servicos_scg)) -> list:
    return servico.obter_periodos()


@router.get("", response_model=SCGPeriodo)
def buscar_periodo(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> SCGPeriodo:
    """`periodo` via query string — path param quebraria com a barra do
    formato mês/ano (ex: 'Jan/2026'), igual ao caso resolvido em SR."""
    dados = servico.buscar_dados_periodo(periodo)
    if not dados:
        raise HTTPException(status_code=404, detail=f"Período '{periodo}' não encontrado")
    return SCGPeriodo(periodo=periodo, **dados)


@router.get("/comparar", response_model=SCGComparacao)
def comparar(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> SCGComparacao:
    """Valores dos módulos (itens) × gravados na consolidação, para o
    usuário escolher qual vale antes de salvar."""
    gravado = servico.buscar_dados_periodo(periodo)
    return SCGComparacao(
        periodo=periodo,
        modulos=SCGValores(**ServicosSCG.buscar_dados_fontes(periodo)),
        gravado=SCGValores(**gravado) if gravado else None,
    )


@router.get("/historico", response_model=list[SCGHistoricoLinha])
def historico(servico: ServicosSCG = Depends(get_servicos_scg)) -> list[SCGHistoricoLinha]:
    """Valores gravados por período + se diverge dos módulos."""
    return [
        SCGHistoricoLinha(**h, diverge=_diverge(ServicosSCG.buscar_dados_fontes(h["periodo"]), h))
        for h in servico.historico()
    ]


@router.post("/salvar", response_model=SCGPeriodo)
def salvar(
    payload: SalvarManualRequest,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> SCGPeriodo:
    """Grava CGR/CGF/RET/RP escolhidos e recalcula RPV e SCG."""
    if not is_periodo_valido(payload.periodo):
        raise ValueError(f"Período inválido: {payload.periodo!r}. Use o formato Jan/2026.")
    dados = servico.salvar_e_calcular(payload.periodo, payload.cgr, payload.cgf, payload.ret, payload.rp)
    return SCGPeriodo(periodo=payload.periodo, **{k: dados[k] for k in ("cgr", "cgf", "rpv", "ret", "rp", "scg")})


@router.post("/calcular", response_model=SCGPeriodo)
def calcular(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> SCGPeriodo:
    dados = servico.calcular_scg_oficial(periodo)
    dados.setdefault("periodo", periodo)
    return SCGPeriodo(**dados)


@router.post("/manual", response_model=RPVResponse)
def salvar_manual(
    payload: SalvarManualRequest,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> RPVResponse:
    rpv = servico.salvar_valores_manuais(
        payload.periodo, payload.cgr, payload.cgf, payload.ret, payload.rp
    )
    return RPVResponse(rpv=rpv)


@router.delete("", status_code=204)
def apagar_periodo(
    periodo: str,
    servico: ServicosSCG = Depends(get_servicos_scg),
) -> None:
    servico.apagar_periodo(periodo)


# TODO(spec §4.6/§8): modo Trimestral (tabela mensal CGR/CGF/RPV/RET/RP/SCG)
# e /scg/trimestre-ativo (compartilha tabela `config` com /pmpv/trimestre-ativo,
# depende do mesmo trabalho de extração pendente no PMPVRepository).
