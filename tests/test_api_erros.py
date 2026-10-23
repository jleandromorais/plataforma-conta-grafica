"""Mensagens de erro da API: dizem o que fazer, sem caminho de arquivo,
traceback ou texto em inglês."""
import sqlite3

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from Src.api import auth
from Src.api.errors import registrar_exception_handlers


@pytest.fixture()
def cliente():
    app = FastAPI()
    registrar_exception_handlers(app)

    @app.get("/regra")
    def regra():
        raise ValueError("O PMPV está zerado: carregue o PMPV do trimestre.")

    @app.get("/arquivo")
    def arquivo():
        raise FileNotFoundError(2, "No such file", "/app/data/uploads/abc/NF Faturadas 01.26.xlsx")

    @app.get("/banco")
    def banco():
        raise sqlite3.OperationalError("database is locked")

    @app.get("/bug")
    def bug():
        raise KeyError("cgr")

    return TestClient(app, raise_server_exceptions=False)


def test_regra_de_negocio_vira_422_com_a_propria_mensagem(cliente):
    r = cliente.get("/regra")
    assert r.status_code == 422
    assert r.json()["detail"] == "O PMPV está zerado: carregue o PMPV do trimestre."


def test_arquivo_nao_encontrado_sem_caminho_do_servidor(cliente):
    detail = cliente.get("/arquivo").json()["detail"]
    assert "NF Faturadas 01.26.xlsx" in detail
    assert "/app/data" not in detail and "Errno" not in detail


def test_banco_ocupado(cliente):
    r = cliente.get("/banco")
    assert r.status_code == 503
    assert "ocupado" in r.json()["detail"]


def test_erro_inesperado_tem_mensagem_amigavel_e_codigo(cliente):
    r = cliente.get("/bug")
    corpo = r.json()
    assert r.status_code == 500
    assert "erro inesperado" in corpo["detail"] and corpo["codigo"] in corpo["detail"]
    assert "KeyError" not in corpo["detail"] and "Internal Server Error" not in corpo["detail"]


def _motivo(cred):
    with pytest.raises(HTTPException) as e:
        auth.usuario_atual(cred)
    return e.value.detail


def test_401_diz_o_motivo(monkeypatch):
    monkeypatch.setattr(auth, "_segredo", lambda: "segredo-de-teste-com-tamanho-suficiente")
    assert "não está conectado" in _motivo(None)
    expirado = jwt.encode({"sub": "1", "exp": 1}, "segredo-de-teste-com-tamanho-suficiente", algorithm="HS256")
    assert "expirou" in _motivo(HTTPAuthorizationCredentials(scheme="Bearer", credentials=expirado))
    assert "não é mais válido" in _motivo(HTTPAuthorizationCredentials(scheme="Bearer", credentials="lixo"))
