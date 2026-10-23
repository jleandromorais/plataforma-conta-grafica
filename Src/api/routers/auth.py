from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from Src.api import auth

router = APIRouter(prefix="/auth", tags=["Autenticação"])


class CadastroIn(BaseModel):
    nome: str
    email: str
    senha: str
    confirmar_senha: str


class LoginIn(BaseModel):
    email: str
    senha: str


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str


class SessaoOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


@router.post("/cadastro", response_model=SessaoOut, status_code=201)
def cadastrar(payload: CadastroIn) -> SessaoOut:
    if not auth.cadastro_aberto():
        raise HTTPException(403, "O cadastro de novos usuários está desativado. Peça a um administrador para criar sua conta.")
    usuario = auth.criar_usuario(
        payload.nome, payload.email, payload.senha, payload.confirmar_senha
    )
    return SessaoOut(access_token=auth.criar_token(usuario), usuario=usuario)


@router.post("/login", response_model=SessaoOut)
def entrar(payload: LoginIn) -> SessaoOut:
    usuario = auth.autenticar(payload.email, payload.senha)
    if not usuario:
        raise HTTPException(401, "E-mail ou senha incorretos. Confira os dois e tente de novo.")
    return SessaoOut(access_token=auth.criar_token(usuario), usuario=usuario)


@router.get("/me", response_model=UsuarioOut)
def eu(usuario: dict = Depends(auth.usuario_atual)) -> UsuarioOut:
    return UsuarioOut(**usuario)
