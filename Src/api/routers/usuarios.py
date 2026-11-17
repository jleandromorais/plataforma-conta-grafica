"""Usuários e perfis: só o administrador (vale mesmo com PERFIS_ATIVOS=0, ver Src/api/perfis.py)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from Src.api import auth
from Src.api.routers.auth import UsuarioOut

router = APIRouter(prefix="/usuarios", tags=["USUÁRIOS"])


class PerfisRequest(BaseModel):
    # consulta, operador, aprovador, analista, administrador. Lista vazia = sem acesso (com PERFIS_ATIVOS=1).
    perfis: list[str] = Field(max_length=len(auth.PERFIS))


@router.get("", response_model=list[UsuarioOut])
def listar() -> list[UsuarioOut]:
    """Usuários com seus perfis. Só administrador."""
    return [UsuarioOut(**u, perfis_ativos=auth.perfis_ativos()) for u in auth.listar_usuarios()]


@router.put("/{usuario_id}/perfis", response_model=UsuarioOut)
def definir_perfis(usuario_id: int, payload: PerfisRequest) -> UsuarioOut:
    """Troca os perfis de um usuário. Só administrador. Não deixa tirar o último administrador."""
    try:
        usuario = auth.definir_perfis(usuario_id, payload.perfis)
    except LookupError as e:
        raise HTTPException(404, str(e))
    return UsuarioOut(**usuario, perfis_ativos=auth.perfis_ativos())
