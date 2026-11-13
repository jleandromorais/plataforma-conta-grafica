"""Limpeza de períodos gravados com nome inválido (ex.: "Teste2", "Geral").

Regra de segurança: só apaga o que NÃO é um período válido (Mês/Ano) e também
não parece um trimestre real ("Nov - Jan/2027", "Q1/2026"), que a validação de
mês/ano considera "inválido" mas que o PR, o SCG etc. usam como chave.
"""
from __future__ import annotations

import re
from typing import Dict

from Src.Database.database import DatabasePMPV
from Src.common.periodos import is_periodo_valido

# "Nov - Jan/2027", "Jan–Mar/26", "Q1/2026"
_PARECE_TRIMESTRE = re.compile(
    r"^\s*(?:[A-Za-zÀ-ÿ]{3}\s*[-–—]\s*[A-Za-zÀ-ÿ]{3}|[Qq]\d)\s*/\s*\d{2}(?:\d{2})?\s*$"
)


class PeriodoProtegidoError(Exception):
    """O nome informado é de um período real (mês ou trimestre): não pode ser apagado por aqui."""


class ServicosPeriodos:
    def __init__(self, db: DatabasePMPV | None = None):
        self._repo = db or DatabasePMPV()

    def fechar(self) -> None:
        self._repo.fechar()

    def limpar_periodo_invalido(self, nome: str, aplicar: bool = False) -> Dict:
        """Simula (aplicar=False) ou apaga (aplicar=True) um período de nome inválido."""
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("Informe o nome do período que deseja limpar.")
        if is_periodo_valido(nome) or _PARECE_TRIMESTRE.match(nome):
            raise PeriodoProtegidoError(
                f"“{nome}” é um período real e não pode ser apagado por aqui. "
                "Só é permitido limpar períodos com nome inválido (ex.: Teste2)."
            )

        # Compara sem diferenciar maiúsculas: "teste2" também limpa "Teste2".
        contagem = self._repo.contar_periodo_completo(nome, ignorar_caixa=True)
        if sum(contagem.values()) == 0:
            raise LookupError(f"Não encontrei nenhum dado gravado com o período “{nome}”.")

        if aplicar:
            contagem = self._repo.apagar_periodo_completo(nome, ignorar_caixa=True)

        tabelas = [{"tabela": t, "linhas": n} for t, n in contagem.items() if n > 0]
        return {
            "periodo": nome,
            "aplicado": aplicar,
            "total_linhas": sum(contagem.values()),
            "tabelas": tabelas,
        }
