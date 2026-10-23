from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile

from Src.api.deps import get_pmpv_use_cases
from Src.api.schemas.pmpv import (
    CalcularPMPVRequest,
    ImportarMemoriaResponse,
    PMPVHistoricoLinha,
    PMPVMensalRequest,
    PMPVMensalResponse,
    SalvarPMPVRequest,
    SalvarPMPVResponse,
    TrimestreAtivoRequest,
    TrimestreAtivoResponse,
)
from Src.application.use_cases.pmpv_use_cases import PMPVUseCases

router = APIRouter(prefix="/pmpv", tags=["PMPV"])


@router.post("/calcular")
def calcular(payload: CalcularPMPVRequest) -> dict:
    return PMPVUseCases.calcular_resultados(
        dados_extraidos=payload.dados_extraidos,
        valor_cg=payload.valor_cg,
        dias_config=payload.dias_config,
        lista_meses=payload.lista_meses,
        idx_start=payload.idx_start,
    )


@router.post("/salvar", response_model=SalvarPMPVResponse)
def salvar(
    payload: SalvarPMPVRequest,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> SalvarPMPVResponse:
    sessao_id = uc.salvar_com_periodos(
        nome=payload.nome,
        dados_por_mes=payload.dados_por_mes,
        resultado=payload.resultado,
        periodos=payload.periodos,
    )
    return SalvarPMPVResponse(sessao_id=sessao_id)


@router.get("/mensal/{periodo:path}", response_model=PMPVMensalResponse)
def buscar_mensal(
    periodo: str,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> PMPVMensalResponse:
    pmpv = uc.repo.buscar_pmpv_mensal(periodo)
    return PMPVMensalResponse(pmpv=pmpv or 0.0)


@router.post("/mensal/{periodo:path}", status_code=204)
def salvar_mensal(
    periodo: str,
    payload: PMPVMensalRequest,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> None:
    uc.salvar_pmpv_mensal(periodo, payload.pmpv)


@router.get("/periodos")
def listar_periodos(uc: PMPVUseCases = Depends(get_pmpv_use_cases)) -> list:
    return uc.repo.listar_periodos()


@router.get("/historico", response_model=list[PMPVHistoricoLinha])
def historico(uc: PMPVUseCases = Depends(get_pmpv_use_cases)) -> list[PMPVHistoricoLinha]:
    """Sessões salvas com PMPV, Conta Gráfica, preço final e VP — da mais recente à mais antiga."""
    return [PMPVHistoricoLinha(**h) for h in uc.repo.listar_historico()]


@router.get("/trimestre-ativo", response_model=TrimestreAtivoResponse)
def buscar_trimestre_ativo(uc: PMPVUseCases = Depends(get_pmpv_use_cases)) -> TrimestreAtivoResponse:
    return TrimestreAtivoResponse(meses=uc.buscar_trimestre_ativo())


@router.post("/trimestre-ativo", status_code=204)
def salvar_trimestre_ativo(
    payload: TrimestreAtivoRequest,
    uc: PMPVUseCases = Depends(get_pmpv_use_cases),
) -> None:
    uc.salvar_trimestre_ativo(payload.meses)


_EXTENSOES_PLANILHA = {".xlsx", ".xls", ".xlsm"}


@router.post("/importar-memoria", response_model=ImportarMemoriaResponse)
def importar_memoria(
    arquivo: UploadFile = File(...),
    periodos: str = Form(..., description='Meses separados por vírgula, ex.: "Fev/2026,Mar/2026,Abr/2026"'),
) -> ImportarMemoriaResponse:
    """Lê a planilha "Memória de Cálculo" e devolve as empresas de cada mês."""
    sufixo = Path(arquivo.filename or "").suffix.lower()
    if sufixo not in _EXTENSOES_PLANILHA:
        raise ValueError("Envie a planilha da Memória de Cálculo (.xlsx ou .xls).")
    lista = [p.strip() for p in periodos.split(",") if p.strip()]
    if not lista:
        raise ValueError("Escolha os 3 meses do trimestre antes de importar a Memória de Cálculo.")

    # pandas precisa de um caminho em disco; o arquivo temporário é apagado ao final.
    fd, caminho = tempfile.mkstemp(suffix=sufixo)
    try:
        with os.fdopen(fd, "wb") as destino:
            destino.write(arquivo.file.read())
        return ImportarMemoriaResponse(**PMPVUseCases.importar_memoria(caminho, lista))
    finally:
        os.remove(caminho)
