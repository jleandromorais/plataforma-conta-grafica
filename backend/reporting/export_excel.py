"""
Exportador de Excel do Pipeline — Plataforma Conta Gráfica

Delega diretamente ao ExcelConsolidado do desktop (Src/infrastructure/exporters/excel_consolidado.py),
que lê do SQLite e gera o mesmo Excel profissional que o programa gera manualmente.

O arquivo gerado é idêntico ao produzido pelo desktop — mesmas abas, mesma formatação,
mesmos cálculos (PMPV, Auditoria, RET, Conciliação, CGF, SCG, SR, PR, PV).
"""

import os
import sys
import logging
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Garante que o Src do desktop está no path (montado em /opt/airflow/Src no Docker)
_SRC_PATH = os.getenv("SRC_PATH", "/opt/airflow/Src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

# Raiz do projeto para salvar em reports/
_BASE_DIR = Path(os.getenv("BASE_DIR", "/opt/airflow"))
_REPORTS_DIR = _BASE_DIR / "reports"


def _resolver_periodo() -> tuple[str, list[str]]:
    """
    Determina o período principal e o trimestre com base na data atual.
    Retorna (periodo, periodos_trimestre) no formato do desktop (ex: 'Abr/2026').
    """
    _ABREVS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

    now = datetime.now()
    mes_idx = now.month - 1  # 0-based

    # Período principal = mês atual
    periodo = f"{_ABREVS[mes_idx]}/{now.year}"

    # Trimestre = 3 meses anteriores ao período principal (inclusive)
    trimestre = []
    for i in range(2, -1, -1):
        idx = (mes_idx - i) % 12
        ano = now.year if (mes_idx - i) >= 0 else now.year - 1
        trimestre.append(f"{_ABREVS[idx]}/{ano}")

    return periodo, trimestre


def _periodo_do_env() -> tuple[str | None, list[str] | None]:
    """Lê período e trimestre das variáveis de ambiente, se definidos."""
    periodo = os.getenv("EXPORT_PERIODO")           # ex: "Abr/2026"
    trimestre_raw = os.getenv("EXPORT_TRIMESTRE")   # ex: "Fev/2026,Mar/2026,Abr/2026"

    if trimestre_raw:
        periodos_trimestre = [p.strip() for p in trimestre_raw.split(",") if p.strip()]
    else:
        periodos_trimestre = None

    return periodo, periodos_trimestre


def main() -> str:
    """
    Gera o Excel consolidado completo usando o exportador do desktop.

    Retorna o caminho do arquivo gerado.
    """
    logger.info("Iniciando exportação do Relatório Conta Gráfica...")

    # Garantir pasta de saída
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Determinar período
    periodo_env, trimestre_env = _periodo_do_env()
    if periodo_env:
        periodo = periodo_env
        periodos_trimestre = trimestre_env
        logger.info(f"Período via env: {periodo} | Trimestre: {periodos_trimestre}")
    else:
        periodo, periodos_trimestre = _resolver_periodo()
        logger.info(f"Período calculado automaticamente: {periodo} | Trimestre: {periodos_trimestre}")

    # Nome do arquivo de saída
    hoje_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_arquivo = str(_REPORTS_DIR / f"Relatorio_ContaGrafica_{periodo.replace('/', '-')}_{hoje_str}.xlsx")

    # Chamar o ExcelConsolidado do desktop
    try:
        from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

        caminho_gerado = ExcelConsolidado.exportar(
            periodo=periodo,
            nome_arquivo=nome_arquivo,
            periodos_trimestre=periodos_trimestre,
        )

        logger.info(f"Excel gerado com sucesso: {caminho_gerado}")
        return caminho_gerado

    except ImportError as e:
        logger.error(f"Não foi possível importar ExcelConsolidado: {e}")
        logger.error(f"Verifique se SRC_PATH={_SRC_PATH} está correto e montado no container.")
        raise

    except Exception as e:
        logger.error(f"Erro ao gerar Excel: {e}")
        raise


if __name__ == "__main__":
    caminho = main()
    print(f"\nRelatório disponível em: {caminho}")
