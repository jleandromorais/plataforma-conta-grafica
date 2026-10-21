"""Fixtures comuns aos testes.

A API exige login (Src/api/main.py); nos testes de API o usuário logado é
simulado, para que cada teste exercite só a regra do módulo.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _usuario_logado():
    from Src.api.auth import usuario_atual
    from Src.api.main import app

    app.dependency_overrides[usuario_atual] = lambda: {"id": 1, "nome": "Teste", "email": "teste@local"}
    yield
    app.dependency_overrides.pop(usuario_atual, None)
