"""Precisão usada nos cálculos — regra praticada pelo desktop e pela planilha
oficial: tarifas por m³ (PMPV, PR) entram nas contas com 4 casas decimais.

Ex.: CGF de Mai/2026 gravado = 45.564.265,79 m³ × 2,2830 (PMPV 2,282982647…
arredondado) = R$ 104.023.218,80.
"""
from __future__ import annotations

CASAS_TARIFA = 4


def arredondar_tarifa(valor: float) -> float:
    """PMPV/PR (R$/m³) na precisão usada nos cálculos: 4 casas."""
    return round(float(valor or 0.0), CASAS_TARIFA)
