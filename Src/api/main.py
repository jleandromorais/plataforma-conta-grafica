"""Backend FastAPI sobre Src/Services — ver SPEC_BACKEND_FASTAPI.md.

Rodar localmente (a partir da raiz do repo `plataforma-conta-grafica`):
    uvicorn Src.api.main:app --reload --port 8080

O front (Front_end/) espera VITE_API_URL apontando para esta base + "/api"
(default hoje: http://localhost:8080/api).
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Src.api.errors import registrar_exception_handlers
from Src.api.routers import config, dashboard, pmpv, pr, pv, rpv, scg, sr

app = FastAPI(
    title="Plataforma Conta Gráfica — API",
    description="Backend FastAPI sobre Src/Services (fonte única dos cálculos).",
    version="0.1.0",
)

_origins = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

registrar_exception_handlers(app)

app.include_router(pmpv.router, prefix="/api")
app.include_router(scg.router, prefix="/api")
app.include_router(pr.router, prefix="/api")
app.include_router(pv.router, prefix="/api")
app.include_router(rpv.router, prefix="/api")
app.include_router(sr.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(config.router, prefix="/api")

# TODO(spec §5): routers de CGF, Auditoria, Conciliação, RET ainda não
# existem — dependem de Repository/Use Case novos (ver
# SPEC_BACKEND_FASTAPI.md §5). Não incluir aqui rotas que chamem
# Src.Database.database.DatabasePMPV diretamente (regra da spec §3).


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
