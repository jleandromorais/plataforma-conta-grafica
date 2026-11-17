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
    # Quem fez. Vazios nas linhas antigas e nas gravações que não vieram da API com login (app desktop).
    usuario_id: int | None = None
    usuario_nome: str | None = None
    usuario_email: str | None = None
    perfil: str | None = None       # perfil que deu acesso à ação (com PERFIS_ATIVOS=0, os perfis da pessoa)
    acao: str | None = None         # ex.: "salvar_modulo", "aprovar_sr", "apagar_pr", "escolher_mb"
    motivo: str | None = None       # obrigatório nas escolhas (SCG, SR anterior, SELIC manual, MB) com PERFIS_ATIVOS=1
