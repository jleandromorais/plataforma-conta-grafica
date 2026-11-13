from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api import erros_ciclo
from Src.api.deps import get_servicos_rpv
from Src.api.schemas.rpv import (
    RPVHistoricoLinha,
    RPVResultado,
    RPVSalvarRequest,
    RPVSalvarResponse,
    ProvaRealRPV,
)
from Src.Services.apuracao.servicos_rpv import ServicosRPV
from Src.common.periodos import is_periodo_valido, normalizar_periodo

router = APIRouter(prefix="/rpv", tags=["RPV"])


@router.get("/periodos")
def listar_periodos(servico: ServicosRPV = Depends(get_servicos_rpv)) -> list:
    return servico.obter_periodos()


@router.get("/historico", response_model=list[RPVHistoricoLinha])
def historico(servico: ServicosRPV = Depends(get_servicos_rpv)) -> list[RPVHistoricoLinha]:
    """CGR, CGF e RPV de cada período — mesma tabela do histórico do desktop."""
    return [RPVHistoricoLinha(**h) for h in servico.historico()]


@router.get("/prova-real", response_model=ProvaRealRPV)
def prova_real(periodo: str, servico: ServicosRPV = Depends(get_servicos_rpv)) -> ProvaRealRPV:
    """A conta do RPV gravado do mês (CGR − CGF) e de onde vêm os dois. Não grava nada."""
    if not is_periodo_valido(periodo):
        raise ValueError("Período inválido. Escolha o mês e o ano, por exemplo Jan/2026.")
    r = servico.prova_real(normalizar_periodo(periodo) or periodo)
    return ProvaRealRPV(**r, erros=erros_ciclo.erros_prova_real_rpv(r))


@router.get("", response_model=RPVResultado)
def buscar_periodo(
    periodo: str,
    servico: ServicosRPV = Depends(get_servicos_rpv),
) -> RPVResultado:
    """`periodo` via query string — path param quebraria com a barra do
    formato mês/ano (ex: 'Jan/2026'), igual ao caso resolvido em SR."""
    dados = servico.buscar_dados_periodo(periodo)
    if not dados:
        raise HTTPException(status_code=404, detail=f"Ainda não há RPV gravado para {periodo}: salve o CGR (Auditoria CGR) e o CGF (tela CGF) deste mês.")
    return RPVResultado(**dados)


@router.post("/salvar", response_model=RPVSalvarResponse)
def salvar(
    payload: RPVSalvarRequest,
    servico: ServicosRPV = Depends(get_servicos_rpv),
) -> RPVSalvarResponse:
    if not is_periodo_valido(payload.periodo):
        raise ValueError(f'O período “{payload.periodo}” não é válido. Escreva o mês com 3 letras e o ano com 4 dígitos, por exemplo Jan/2026.')
    rpv = servico.salvar_valores(payload.periodo, payload.cgr, payload.cgf)
    return RPVSalvarResponse(rpv=rpv)
