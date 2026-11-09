"""CGF — Volume Faturado. Mesma regra da tela desktop (tela_cgf.py), via
ServicosCGF: VF = faturado (sem consumo próprio) − devoluções; CGF em R$ =
VF × PMPV do mês."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from Src.api.schemas.cgf import (
    CGFCalcularRSRequest,
    CGFCalcularRSResponse,
    CGFHistoricoLinha,
    CGFProcessarResponse,
    CGFSalvarRequest,
    CGFSalvarResponse,
    ProvaRealCGF,
)
from Src.api.schemas.comum import ProblemaArquivo
from Src.Services import servicos_pr_automatico
from Src.Services.servicos_cgf import ServicosCGF
from Src.common.periodos import normalizar_periodo

router = APIRouter(prefix="/cgf", tags=["CGF"])

_EXTENSOES = {".xlsx", ".xls", ".xlsm", ".csv"}


@router.post("/processar", response_model=CGFProcessarResponse)
def processar(
    arquivos: list[UploadFile] = File(...),
    col_fat_volume: str = Form("Volume Faturado"),
    col_fat_consumo: str = Form("Produto"),
    val_fat_consumo: str = Form("consumo proprio"),
    col_canc_volume: str = Form("Volume Canc/Deneg"),
    col_dev_volume: str = Form("Volume Devolução"),
) -> CGFProcessarResponse:
    """Calcula os volumes a partir das planilhas de NF. NÃO grava nada.

    O tipo de cada planilha vem do NOME do arquivo (faturada/complementar,
    cancelada/denegada, devolução) — por isso o nome original é preservado.
    """
    if not arquivos:
        raise ValueError("Nenhuma planilha foi enviada. Selecione as planilhas de NF do mês "
                         "(faturadas, canceladas e devolvidas).")

    pasta = Path(tempfile.mkdtemp(prefix="cgf_"))
    try:
        caminhos: list[str] = []
        ignorados: list[str] = []
        for up in arquivos:
            nome = Path(up.filename or "").name  # sem diretórios
            if Path(nome).suffix.lower() not in _EXTENSOES:
                raise ValueError(f"O arquivo “{nome}” não é uma planilha. Envie arquivos .xlsx, .xls ou .csv.")
            if ServicosCGF.tipo_do_nome(nome) is None:
                ignorados.append(nome)
            destino = pasta / nome
            with destino.open("wb") as f:
                shutil.copyfileobj(up.file, f)
            caminhos.append(str(destino))

        r = ServicosCGF().processar_arquivos(
            caminhos, col_fat_volume, col_fat_consumo, val_fat_consumo, col_canc_volume, col_dev_volume,
        )
        periodo = next((p for p in map(ServicosCGF.periodo_do_nome_arquivo, caminhos) if p), "")
        return CGFProcessarResponse(
            volume_faturado=r["volume_faturado"],
            volume_canceladas=r["volume_canceladas"],
            volume_devolucoes=r["volume_devolucoes"],
            volume_consumo_proprio=r["volume_consumo_proprio"],
            volume_final=r["volume_final"],
            periodo_detectado=periodo,
            arquivos_ignorados=ignorados,
            problemas=[ProblemaArquivo(**p) for p in r["problemas"]],
            logs=r["logs"],
        )
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


@router.post("/calcular-rs", response_model=CGFCalcularRSResponse)
def calcular_rs(payload: CGFCalcularRSRequest) -> CGFCalcularRSResponse:
    """CGF em R$ = volume final × PMPV (do payload ou, se ausente, do banco). Não grava."""
    return CGFCalcularRSResponse(
        **ServicosCGF().calcular_cgf_rs(payload.periodo, payload.volume_final, payload.pmpv)
    )


@router.post("/salvar", response_model=CGFSalvarResponse)
def salvar(payload: CGFSalvarRequest) -> CGFSalvarResponse:
    """Grava CGF em R$ (volume final × PMPV) e o resumo de volumes. Exige PMPV."""
    salvo = ServicosCGF().salvar_com_pmpv(payload.periodo, payload.model_dump(), payload.pmpv)
    # O CGF mudou o RPV e o SCG do mês: o PR e o PV que o usam são regravados (em silêncio).
    servicos_pr_automatico.atualizar_dos_meses([payload.periodo])
    return CGFSalvarResponse(**salvo)


@router.get("/prova-real", response_model=ProvaRealCGF)
def prova_real(periodo: str) -> ProvaRealCGF:
    """A conta do CGF gravado do mês, aberta: volumes, PMPV e CGF em R$. Não grava nada."""
    return ProvaRealCGF(**ServicosCGF().prova_real(normalizar_periodo(periodo) or periodo))


@router.get("/historico", response_model=list[CGFHistoricoLinha])
def historico() -> list[CGFHistoricoLinha]:
    return [CGFHistoricoLinha(**h) for h in ServicosCGF().historico()]
