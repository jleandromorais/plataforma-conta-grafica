"""Caminhos base da aplicação — funcionam tanto rodando via `python main.py`
quanto a partir do .exe gerado pelo PyInstaller.

Em modo congelado (PyInstaller), `Path(__file__).resolve().parents[N]` aponta
para dentro da pasta `_internal`, e não para a pasta onde está o .exe. Isso faz
com que o banco de dados (`pmpv_data.db`) e os logs sejam criados dentro de
`_internal`, isolados/perdidos a cada nova instalação — diferente do banco
usado em desenvolvimento. `raiz_aplicacao()` resolve isso apontando sempre
para a pasta que contém o executável (ou a raiz do projeto, em dev).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def raiz_aplicacao() -> Path:
    """Retorna a pasta raiz da aplicação.

    - Empacotado (.exe via PyInstaller): pasta onde está o executável.
    - Em desenvolvimento: raiz do projeto (3 níveis acima deste arquivo).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


# Arquivo opcional, ao lado do .exe (ou na raiz do projeto), com o caminho do
# banco oficial numa única linha — ex.: Z:\Conta Grafica\pmpv_data.db.
# Permite que o .exe e o `python main.py` usem o MESMO banco em vez de cada
# um ter sua cópia.
ARQUIVO_CAMINHO_BANCO = "caminho_banco.txt"


def caminho_banco() -> Path:
    """Caminho do banco de dados principal.

    Ordem de prioridade:
    1. Variável de ambiente PLATAFORMA_DB;
    2. Primeira linha não vazia de `caminho_banco.txt` na raiz da aplicação
       (linhas iniciadas por # são comentários);
    3. `pmpv_data.db` na raiz da aplicação (padrão).
    """
    configurado: Path | None = None
    origem = ""
    env = os.environ.get("PLATAFORMA_DB", "").strip().strip('"')
    if env:
        configurado, origem = Path(env), "variável PLATAFORMA_DB"
    else:
        cfg = raiz_aplicacao() / ARQUIVO_CAMINHO_BANCO
        if cfg.is_file():
            for linha in cfg.read_text(encoding="utf-8-sig").splitlines():
                linha = linha.strip().strip('"')
                if linha and not linha.startswith("#"):
                    configurado, origem = Path(linha), str(cfg)
                    break

    if configurado is None:
        return raiz_aplicacao() / "pmpv_data.db"

    # Banco configurado precisa existir: senão o SQLite criaria um banco VAZIO
    # em silêncio (ex.: caminho digitado errado ou unidade Z: desconectada).
    if not configurado.is_file():
        raise FileNotFoundError(
            f"Banco de dados não encontrado em:\n{configurado}\n\n"
            f"(configurado em {origem}). Verifique se a pasta/unidade de rede "
            f"está acessível ou corrija o caminho."
        )
    return configurado


def em_pasta_de_rede(caminho: Path | str) -> bool:
    """True se o caminho está num compartilhamento de rede (\\\\servidor\\... ou
    unidade mapeada como Z:). O modo WAL do SQLite não é seguro nesses casos."""
    texto = str(caminho)
    if texto.startswith("\\\\") or texto.startswith("//"):
        return True
    if sys.platform == "win32" and len(texto) >= 2 and texto[1] == ":":
        try:
            import ctypes
            DRIVE_REMOTE = 4
            return ctypes.windll.kernel32.GetDriveTypeW(f"{texto[0]}:\\") == DRIVE_REMOTE
        except Exception:
            return False
    return False
