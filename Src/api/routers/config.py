from __future__ import annotations

from fastapi import APIRouter

from Src.api.schemas.config import TaxasConfig, TrimestreConfig
from Src.common.periodos import TRIMESTRES_CIVIS, TRIMESTRES_FISCAIS_ABREVS
from Src.Services.servicos_auditoria import COFINS_RATE, PIS_RATE
from Src.Services.servicos_auditoria import PIS_COFINS_RATE as PIS_COFINS_RATE_AUDITORIA
from Src.Services.servicos_ret import PIS_COFINS_RATE as PIS_COFINS_RATE_RET
from Src.Services.servicos_ret import TAXA_EUR_BRL

router = APIRouter(prefix="/config", tags=["Config"])


@router.get("/trimestres-fiscais", response_model=list[TrimestreConfig])
def trimestres_fiscais() -> list[TrimestreConfig]:
    """PMPV/PR/PV. Fonte única: Src/common/periodos.py — elimina o hardcode
    duplicado sinalizado em Front_end/TASKS.md item §10 (PMPV)."""
    return [TrimestreConfig(label=label, meses=meses) for label, meses in TRIMESTRES_FISCAIS_ABREVS]


@router.get("/trimestres-civis", response_model=list[TrimestreConfig])
def trimestres_civis() -> list[TrimestreConfig]:
    """SCG/CGR/CGF/RET/RP/SR."""
    return [TrimestreConfig(label=label, meses=meses) for label, meses in TRIMESTRES_CIVIS.items()]


@router.get("/taxas", response_model=TaxasConfig)
def taxas() -> TaxasConfig:
    """Elimina a taxa PIS/COFINS hardcoded (0.0465, valor errado) sinalizada
    em Front_end/TASKS.md item §9 (RET) — valor real é 0.0925."""
    return TaxasConfig(
        pis_cofins_rate_ret=PIS_COFINS_RATE_RET,
        pis_rate_auditoria=PIS_RATE,
        cofins_rate_auditoria=COFINS_RATE,
        pis_cofins_rate_auditoria=PIS_COFINS_RATE_AUDITORIA,
        taxa_eur_brl=TAXA_EUR_BRL,
    )
