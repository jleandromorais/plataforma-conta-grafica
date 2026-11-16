"""Trilha de alterações: o que mudou nos valores gravados, de quanto para quanto e quando."""
from __future__ import annotations

from pydantic import BaseModel


class TrilhaLinha(BaseModel):
    id: int
    tabela: str                     # consolidacao, sr_resultados, pr_resultados, pv_resultados ou pmpv_mensal
    periodo: str                    # "Jul/2026" ou a chave do trimestre ("Nov - Jan/2027")
    campo: str                      # ex.: "scg", "pr", "pv", "sr", "pmpv"
    valor_antigo: float | None = None   # None = ainda não havia valor
    valor_novo: float | None = None     # None = o valor foi apagado
    origem: str                     # "salvar", "cascata" (aprovação) ou "apagar"
    data_hora: str                  # "AAAA-MM-DD HH:MM:SS" (UTC, como as outras datas do banco)
