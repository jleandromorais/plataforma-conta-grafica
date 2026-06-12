"""Caminhos base da aplicação — funcionam tanto rodando via `python main.py`
quanto a partir do .exe gerado pelo PyInstaller.

Em modo congelado (PyInstaller), `Path(__file__).resolve().parents[N]` aponta
para dentro da pasta `_internal`, e não para a pasta onde está o .exe. Isso faz
com que o banco de dados (`pmpv_data.db`) e os logs sejam criados dentro de
`_internal`, isolados/perdidos a cada nova instalação — diferente do banco
usado em desenvolvimento. `raiz_aplicacao()` resolve isso apontando sempre
para a pasta que contém o executável (ou a raiz do projeto, em dev).
"""

from __future__ import annotations

import sys
from pathlib import Path


def raiz_aplicacao() -> Path:
    """Retorna a pasta raiz da aplicação.

    - Empacotado (.exe via PyInstaller): pasta onde está o executável.
    - Em desenvolvimento: raiz do projeto (3 níveis acima deste arquivo).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]
