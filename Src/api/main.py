"""Backend FastAPI sobre Src/Services — ver docs/SPEC_BACKEND_FASTAPI.md.

Rodar localmente (a partir da raiz do repo `plataforma-conta-grafica`):
    uvicorn Src.api.main:app --reload --port 8080

O front (Front_end/) espera VITE_API_URL apontando para esta base + "/api"
(default hoje: http://localhost:8080/api).
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Src.api.auth import usuario_atual
from Src.api.errors import registrar_exception_handlers
from Src.api.routers import auth as auth_router, auditoria, cgf, conciliacao, config, dashboard, excel_final, nota_tecnica, periodos, pmpv, pr, pv, relatorio_trimestral, ret, rpv, scg, sr

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

# Tudo exige login, exceto /api/auth/* e /api/health.
_protegido = [Depends(usuario_atual)]
app.include_router(auth_router.router, prefix="/api")

app.include_router(pmpv.router, prefix="/api", dependencies=_protegido)
app.include_router(scg.router, prefix="/api", dependencies=_protegido)
app.include_router(pr.router, prefix="/api", dependencies=_protegido)
app.include_router(pv.router, prefix="/api", dependencies=_protegido)
app.include_router(rpv.router, prefix="/api", dependencies=_protegido)
app.include_router(sr.router, prefix="/api", dependencies=_protegido)
app.include_router(dashboard.router, prefix="/api", dependencies=_protegido)
app.include_router(config.router, prefix="/api", dependencies=_protegido)
app.include_router(cgf.router, prefix="/api", dependencies=_protegido)
app.include_router(auditoria.router, prefix="/api", dependencies=_protegido)
app.include_router(ret.router, prefix="/api", dependencies=_protegido)
app.include_router(conciliacao.router, prefix="/api", dependencies=_protegido)
app.include_router(excel_final.router, prefix="/api", dependencies=_protegido)
app.include_router(nota_tecnica.router, prefix="/api", dependencies=_protegido)
app.include_router(relatorio_trimestral.router, prefix="/api", dependencies=_protegido)
app.include_router(periodos.router, prefix="/api", dependencies=_protegido)

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
