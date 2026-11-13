"""Nome canônico do supridor, compartilhado pelos comparadores de planilha.

A primeira palavra-chave encontrada no nome (pasta da auditoria ou coluna da
planilha) define o grupo.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

_SUPRIDORES = (
    ("brava", "Brava"), ("3r", "Brava"),
    ("eneva", "Eneva"),
    ("galp", "Galp"),
    ("gnllink", "GNLink"), ("gnlink", "GNLink"), ("gnl", "GNLink"),
    ("orizon", "Orizon"),
    ("petroreconcavo", "Petrorecôncavo"),
    ("petrobras", "Petrobras"),
    ("mastergas", "Mastergás"),
    ("shell", "Shell"),
    ("tag", "TAG"),
    ("cegas", "Cegás"),
    ("sergas", "Sergás"),
    ("vector", "GNC Vector"),
)


def token(texto: Any) -> str:
    """Minúsculas, sem acento e só letras/dígitos — para comparar rótulos."""
    limpo = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", limpo.lower())


def supridor_canonico(nome: Any) -> str:
    tok = token(nome)
    for chave, canon in _SUPRIDORES:
        if chave in tok:
            return canon
    return str(nome or "").strip() or "?"
