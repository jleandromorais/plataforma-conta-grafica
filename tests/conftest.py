"""Fixtures comuns aos testes.

A API exige login (Src/api/main.py); nos testes de API o usuário logado é
simulado, para que cada teste exercite só a regra do módulo.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _sem_internet_na_selic(monkeypatch, request):
    """Nenhum teste chama o Banco Central: o SR automático (salvar SCG/módulos) busca a SELIC.
    Quem precisa de SELIC troca `selic_do_trimestre` por uma falsa. (`test_selic.py` testa o
    próprio `buscar_bcb`, com a internet simulada por ele, então fica de fora.)"""
    from Src.Services.tarifa import servicos_selic

    if request.module.__name__.endswith("test_selic"):
        return

    def sem_bc(inicio, fim):
        raise servicos_selic.SelicIndisponivel("Banco Central desligado nos testes.")

    monkeypatch.setattr(servicos_selic, "buscar_bcb", sem_bc)


@pytest.fixture(autouse=True)
def _usuario_logado():
    from Src.api.auth import usuario_atual
    from Src.api.main import app

    app.dependency_overrides[usuario_atual] = lambda: {"id": 1, "nome": "Teste", "email": "teste@local"}
    yield
    app.dependency_overrides.pop(usuario_atual, None)
