"""Mapeamento de exceções de domínio para respostas HTTP.

Os Services em Src/Services levantam ValueError para violações de regra de
negócio (ex.: "Volume Zero", período inválido). Este handler garante que
essas exceções virem 422 em vez de 500, sem que cada router precise de um
try/except repetido.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def registrar_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})
