"""Ponto de entrada para rodar a API em servidor (Docker/nuvem).

    python -m Src.api.serve

- Porta: variável PORT (padrão 8080), escutando em 0.0.0.0.
- Banco: se PLATAFORMA_DB aponta para um arquivo que ainda não existe (primeira
  subida com disco vazio), cria o banco com todas as tabelas. Se o arquivo já
  existe (você copiou o seu banco para o disco), ele é usado como está.
"""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn


def garantir_banco() -> None:
    destino = os.environ.get("PLATAFORMA_DB", "").strip().strip('"')
    if not destino:
        return
    caminho = Path(destino)
    if caminho.is_file():
        return
    caminho.parent.mkdir(parents=True, exist_ok=True)
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV(str(caminho)):
        pass  # criar as tabelas é feito no construtor
    print(f"[serve] banco novo criado em {caminho}", flush=True)


def main() -> None:
    garantir_banco()
    uvicorn.run(
        "Src.api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
