"""Autenticação da API: usuários em SQLite (mesmo banco do app), senha com
scrypt e sessão por token JWT (HS256).

Variáveis de ambiente (opcionais):
    JWT_SECRET          segredo do token; se ausente, um aleatório é gerado e
                        guardado no banco (tokens sobrevivem a reinícios);
    JWT_EXPIRA_HORAS    validade do token (padrão 12);
    PERMITIR_CADASTRO   "0" fecha o auto-cadastro (padrão "1");
    PERFIS_ATIVOS       "1" faz valer a matriz de perfis (padrão "0": todo usuário logado pode tudo).

Perfis (tabela `usuario_perfis`): consulta, operador, aprovador, analista, administrador. Uma pessoa pode
ter mais de um. O perfil é lido do banco a cada requisição (não vai no token).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from Src.common.app_paths import caminho_banco

PERFIS = ("consulta", "operador", "aprovador", "analista", "administrador")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)
_bearer = HTTPBearer(auto_error=False)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(caminho_banco()))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS auth_config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usuario_perfis (
            usuario_id INTEGER NOT NULL,
            perfil TEXT NOT NULL,
            PRIMARY KEY (usuario_id, perfil)
        )"""
    )
    _migrar_perfis(conn)
    return conn


def _migrar_perfis(conn: sqlite3.Connection) -> None:
    """Uma vez só: quem já tinha conta antes dos perfis vira administrador (ninguém perde acesso ao
    ligar PERFIS_ATIVOS). A marca em `auth_config` impede que usuários novos virem administrador depois."""
    if conn.execute("SELECT 1 FROM auth_config WHERE chave='perfis_migrados'").fetchone():
        return
    conn.execute(
        "INSERT OR IGNORE INTO usuario_perfis(usuario_id, perfil) SELECT id, 'administrador' FROM usuarios"
    )
    conn.execute("INSERT INTO auth_config(chave, valor) VALUES('perfis_migrados', '1')")
    conn.commit()


def perfis_ativos() -> bool:
    """PERFIS_ATIVOS=1 liga a matriz de perfis. Lido a cada chamada (muda sem reiniciar o código dos testes)."""
    return os.environ.get("PERFIS_ATIVOS", "0").strip() == "1"


def _perfis_do_usuario(conn: sqlite3.Connection, uid: int) -> list[str]:
    linhas = conn.execute("SELECT perfil FROM usuario_perfis WHERE usuario_id=?", (uid,)).fetchall()
    achados = {r["perfil"] for r in linhas}
    return [p for p in PERFIS if p in achados]


def listar_usuarios() -> list[dict]:
    with _conn() as c:
        return [{"id": r["id"], "nome": r["nome"], "email": r["email"], "perfis": _perfis_do_usuario(c, r["id"])}
                for r in c.execute("SELECT id, nome, email FROM usuarios ORDER BY id").fetchall()]


def definir_perfis(uid: int, perfis: list[str]) -> dict:
    """Troca os perfis de um usuário (lista vazia = sem acesso quando PERFIS_ATIVOS=1).
    Recusa perfil que não existe e a remoção do último administrador (ninguém mais conseguiria gerenciar)."""
    invalidos = [p for p in perfis if p not in PERFIS]
    if invalidos:
        raise ValueError(f"Perfil inexistente: {', '.join(invalidos)}. Use: {', '.join(PERFIS)}.")
    with _conn() as c:
        row = c.execute("SELECT id, nome, email FROM usuarios WHERE id=?", (uid,)).fetchone()
        if not row:
            raise LookupError(f"Não encontrei o usuário nº {uid}. Confira a lista de usuários.")
        if "administrador" not in perfis and "administrador" in _perfis_do_usuario(c, uid):
            outros = c.execute(
                "SELECT COUNT(*) FROM usuario_perfis WHERE perfil='administrador' AND usuario_id<>?", (uid,)
            ).fetchone()[0]
            if outros == 0:
                raise ValueError("Este é o último administrador: dê o perfil administrador a outra pessoa "
                                 "antes de tirá-lo, senão ninguém conseguirá gerenciar os perfis.")
        c.execute("DELETE FROM usuario_perfis WHERE usuario_id=?", (uid,))
        c.executemany("INSERT INTO usuario_perfis(usuario_id, perfil) VALUES(?,?)", [(uid, p) for p in set(perfis)])
        return {"id": row["id"], "nome": row["nome"], "email": row["email"],
                "perfis": [p for p in PERFIS if p in perfis]}


def cadastro_aberto() -> bool:
    return os.environ.get("PERMITIR_CADASTRO", "1").strip() != "0"


def _segredo() -> str:
    env = os.environ.get("JWT_SECRET", "").strip()
    if env:
        return env
    with _conn() as c:
        row = c.execute("SELECT valor FROM auth_config WHERE chave='jwt_secret'").fetchone()
        if row:
            return row["valor"]
        novo = secrets.token_hex(32)
        c.execute("INSERT INTO auth_config(chave, valor) VALUES('jwt_secret', ?)", (novo,))
        return novo


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, **_SCRYPT)
    return f"scrypt${sal.hex()}${h.hex()}"


def conferir_senha(senha: str, armazenado: str) -> bool:
    try:
        _, sal, h = armazenado.split("$")
        calc = hashlib.scrypt(senha.encode(), salt=bytes.fromhex(sal), **_SCRYPT)
        return hmac.compare_digest(calc, bytes.fromhex(h))
    except (ValueError, TypeError):
        return False


def normalizar_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not _EMAIL.match(email):
        raise ValueError(f"O e-mail “{email}” não é válido. Confira se tem @ e domínio, por exemplo nome@empresa.com.br.")
    return email


def criar_usuario(nome: str, email: str, senha: str, confirmar: str) -> dict:
    nome = (nome or "").strip()
    if len(nome) < 2:
        raise ValueError("Informe o nome.")
    email = normalizar_email(email)
    if len(senha) < 8:
        raise ValueError("A senha deve ter pelo menos 8 caracteres.")
    if senha != confirmar:
        raise ValueError("As senhas não coincidem.")
    with _conn() as c:
        try:
            cur = c.execute(
                "INSERT INTO usuarios(nome, email, senha_hash) VALUES(?,?,?)",
                (nome, email, hash_senha(senha)),
            )
        except sqlite3.IntegrityError:
            raise ValueError("Já existe uma conta com este e-mail. Entre pela tela de login ou cadastre outro e-mail.")
        # Usuário novo nasce só com "consulta"; o 1º da instalação (sem nenhum administrador) vira
        # administrador, para ninguém ficar trancado para fora ao ligar PERFIS_ATIVOS.
        ha_admin = c.execute("SELECT 1 FROM usuario_perfis WHERE perfil='administrador'").fetchone()
        perfil = "consulta" if ha_admin else "administrador"
        c.execute("INSERT INTO usuario_perfis(usuario_id, perfil) VALUES(?,?)", (cur.lastrowid, perfil))
        return {"id": cur.lastrowid, "nome": nome, "email": email, "perfis": [perfil]}


def autenticar(email: str, senha: str) -> dict | None:
    try:
        email = normalizar_email(email)
    except ValueError:
        return None
    with _conn() as c:
        row = c.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
        perfis = _perfis_do_usuario(c, row["id"]) if row else []
    if row and conferir_senha(senha, row["senha_hash"]):
        return {"id": row["id"], "nome": row["nome"], "email": row["email"], "perfis": perfis}
    # gasta o mesmo tempo quando o e-mail não existe (evita enumerar contas)
    if not row:
        conferir_senha(senha, "scrypt$" + "00" * 16 + "$" + "00" * 32)
    return None


def criar_token(usuario: dict) -> str:
    horas = int(os.environ.get("JWT_EXPIRA_HORAS", "12"))
    exp = datetime.now(timezone.utc) + timedelta(hours=horas)
    return jwt.encode({"sub": str(usuario["id"]), "exp": exp}, _segredo(), algorithm="HS256")


def usuario_atual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    def erro(motivo: str) -> HTTPException:
        return HTTPException(status.HTTP_401_UNAUTHORIZED, motivo, headers={"WWW-Authenticate": "Bearer"})

    if cred is None:
        raise erro("Você não está conectado. Entre com seu e-mail e senha.")
    try:
        dados = jwt.decode(cred.credentials, _segredo(), algorithms=["HS256"])
        uid = int(dados["sub"])
    except jwt.ExpiredSignatureError:
        raise erro("Sua sessão expirou (por segurança, o acesso vale algumas horas). Entre novamente.")
    except (jwt.PyJWTError, KeyError, ValueError):
        raise erro("Seu acesso não é mais válido (o sistema pode ter sido atualizado). Entre novamente.")
    with _conn() as c:
        row = c.execute("SELECT id, nome, email FROM usuarios WHERE id=?", (uid,)).fetchone()
        perfis = _perfis_do_usuario(c, uid) if row else []
    if not row:
        raise erro("Seu usuário não foi encontrado. Entre novamente ou peça um novo cadastro ao administrador.")
    # O perfil vem do banco a cada requisição (não do token): tirar um perfil vale na hora.
    return {**dict(row), "perfis": perfis}
