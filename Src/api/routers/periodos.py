"""Limpeza de períodos com nome inválido (ex.: "Teste2") gravados por engano."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from Src.api.deps import get_servicos_periodos
from Src.api.schemas.periodos import LimpezaPeriodoResponse
from Src.Services.servicos_periodos import PeriodoProtegidoError, ServicosPeriodos

router = APIRouter(prefix="/periodos", tags=["Períodos"])


@router.delete("/{nome:path}", response_model=LimpezaPeriodoResponse)
def apagar_periodo_invalido(
    nome: str,
    aplicar: bool = False,
    servico: ServicosPeriodos = Depends(get_servicos_periodos),
) -> LimpezaPeriodoResponse:
    """Apaga um período de nome INVÁLIDO em todas as tabelas.

    Por padrão é só simulação (aplicar=false): devolve as tabelas e quantas
    linhas seriam removidas, SEM apagar nada. Só apaga com ?aplicar=true.
    Período válido (ex.: Jan/2026) ou trimestre real é recusado com 400.
    """
    try:
        resultado = servico.limpar_periodo_invalido(nome, aplicar=aplicar)
    except PeriodoProtegidoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return LimpezaPeriodoResponse(**resultado)
