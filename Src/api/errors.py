"""Mapeamento de exceções para respostas HTTP com mensagens para o usuário.

Os Services em Src/Services levantam ValueError para violações de regra de
negócio (ex.: "Volume Zero", período inválido): viram 422 com a própria
mensagem. O resto vira uma mensagem que diz o que fazer, sem caminho de
arquivo nem traceback; o erro inesperado ganha um `codigo` curto que também
vai para o log, para o suporte achar o caso.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _resposta(status: int, detail: str, codigo: str | None = None) -> JSONResponse:
    corpo = {"detail": detail}
    if codigo:
        corpo["codigo"] = codigo
    return JSONResponse(status_code=status, content=corpo)


def registrar_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return _resposta(422, str(exc))

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        # Só o nome do arquivo: o caminho no servidor não ajuda o usuário.
        nome = Path(exc.filename).name if getattr(exc, "filename", None) else None
        alvo = f"o arquivo “{nome}”" if nome else "um arquivo necessário"
        return _resposta(404, f"Não encontrei {alvo} no servidor. Envie o arquivo de novo e tente outra vez.")

    @app.exception_handler(sqlite3.OperationalError)
    async def banco_handler(request: Request, exc: sqlite3.OperationalError):
        if "locked" in str(exc).lower():
            return _resposta(503, "O banco de dados está ocupado com outra gravação. Aguarde alguns segundos e "
                                  "tente de novo.")
        return await _inesperado(request, exc)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, exc: Exception):
        codigo = uuid.uuid4().hex[:8].upper()
        logger.exception("Erro inesperado [%s] em %s %s", codigo, request.method, request.url.path)
        return _resposta(500, "Aconteceu um erro inesperado no servidor. Tente de novo em instantes; se continuar, "
                              f"mande um print desta mensagem para o suporte (código {codigo}).", codigo)
