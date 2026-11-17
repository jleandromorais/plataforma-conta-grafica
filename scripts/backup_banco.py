"""Backup, validação e restauração do banco SQLite da plataforma.

É a "cópia de segurança do arquivo-morto": usa a API de backup do próprio SQLite
(`Connection.backup`), que gera uma cópia consistente mesmo com o banco aberto
pela API. Copiar o arquivo `.db` na mão com o servidor rodando pode sair
corrompido (o modo WAL guarda dados em arquivos laterais).

Origem: a mesma regra do resto do código (`Src.common.app_paths.caminho_banco`):
variável PLATAFORMA_DB, depois `caminho_banco.txt`, depois `pmpv_data.db`.
Pasta de backups: `--pasta`, ou a variável PLATAFORMA_BACKUP_DIR, ou `backups/`
na raiz do projeto. Retenção: `--manter` ou PLATAFORMA_BACKUP_MANTER (padrão 30).

Uso (na pasta plataforma-conta-grafica):
    python scripts/backup_banco.py criar                 # cria, valida e aplica a retenção
    python scripts/backup_banco.py criar --manter 10
    python scripts/backup_banco.py validar <arquivo.db>
    python scripts/backup_banco.py listar
    python scripts/backup_banco.py restaurar <backup.db> --destino <novo.db>
    python scripts/backup_banco.py restaurar <backup.db> --destino <banco_real.db> --confirmo-sobrescrever

A restauração NUNCA sobrescreve um arquivo existente sem `--confirmo-sobrescrever`
e, quando sobrescreve, guarda antes uma cópia do que estava lá.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

MANTER_PADRAO = 30
# Só arquivos com este nome são considerados "nossos" (e podem ser apagados pela
# retenção). Backups manuais com outros nomes ficam intocados.
PADRAO_NOME = re.compile(r"^(?P<base>.+)_(?P<data>\d{8}_\d{6})\.db$")


class BackupInvalido(Exception):
    """A cópia não passou na validação."""


def pasta_padrao() -> Path:
    env = os.environ.get("PLATAFORMA_BACKUP_DIR", "").strip().strip('"')
    return Path(env) if env else RAIZ / "backups"


def manter_padrao() -> int:
    env = os.environ.get("PLATAFORMA_BACKUP_MANTER", "").strip()
    return int(env) if env.isdigit() and int(env) > 0 else MANTER_PADRAO


def _abrir_leitura(caminho: Path) -> sqlite3.Connection:
    # mode=ro: a origem nunca é alterada pelo backup.
    return sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)


def _contar_tabelas(con: sqlite3.Connection) -> int:
    return con.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0]


def validar(caminho: Path, minimo_tabelas: int = 1) -> int:
    """Confere integridade e conta as tabelas. Devolve o número de tabelas.

    Levanta BackupInvalido se o arquivo não existir, estiver corrompido ou vazio.
    """
    if not caminho.is_file():
        raise BackupInvalido(f"Arquivo não encontrado: {caminho}")
    try:
        con = _abrir_leitura(caminho)
        try:
            resultado = con.execute("PRAGMA integrity_check").fetchall()
            tabelas = _contar_tabelas(con)
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        raise BackupInvalido(f"O SQLite não conseguiu ler {caminho.name}: {e}") from e
    if resultado != [("ok",)]:
        raise BackupInvalido(f"integrity_check falhou em {caminho.name}: {resultado[:3]}")
    if tabelas < minimo_tabelas:
        raise BackupInvalido(f"{caminho.name} tem {tabelas} tabela(s); esperado ao menos {minimo_tabelas}.")
    return tabelas


def listar(pasta: Path, base: str | None = None) -> list[Path]:
    """Backups no padrão de nome, do mais antigo para o mais novo."""
    if not pasta.is_dir():
        return []
    achados = []
    for p in pasta.iterdir():
        m = PADRAO_NOME.match(p.name)
        if m and p.is_file() and (base is None or m.group("base") == base):
            achados.append((m.group("data"), p))
    return [p for _, p in sorted(achados, key=lambda t: t[0])]


def aplicar_retencao(pasta: Path, manter: int, base: str | None = None) -> list[Path]:
    """Apaga os mais antigos, deixando só `manter` cópias. Devolve os apagados."""
    if manter < 1:
        raise ValueError("A retenção precisa ser de pelo menos 1 cópia.")
    todos = listar(pasta, base)
    apagar = todos[: max(0, len(todos) - manter)]
    for p in apagar:
        p.unlink()
    return apagar


def criar_backup(origem: Path, pasta: Path, manter: int = MANTER_PADRAO, agora: datetime | None = None) -> Path:
    """Cria a cópia com data e hora no nome, valida e aplica a retenção.

    Se a validação falhar, a cópia ruim é apagada e a retenção NÃO roda
    (para nunca trocar uma cópia boa por uma ruim).
    """
    if not origem.is_file():
        raise FileNotFoundError(f"Banco de origem não encontrado: {origem}")
    pasta.mkdir(parents=True, exist_ok=True)
    carimbo = (agora or datetime.now()).strftime("%Y%m%d_%H%M%S")
    destino = pasta / f"{origem.stem}_{carimbo}.db"
    if destino.exists():
        raise FileExistsError(f"Já existe um backup com este nome: {destino.name}")

    src = _abrir_leitura(origem)
    dst = sqlite3.connect(destino)
    try:
        src.backup(dst)
        tabelas_origem = _contar_tabelas(src)
        # a cópia herda o modo WAL; DELETE deixa o backup em um arquivo só
        dst.execute("PRAGMA journal_mode=DELETE")
    except Exception:
        dst.close()
        src.close()
        destino.unlink(missing_ok=True)
        raise
    dst.close()
    src.close()

    try:
        if validar(destino) != tabelas_origem:
            raise BackupInvalido("O número de tabelas da cópia difere do banco de origem.")
    except BackupInvalido:
        destino.unlink(missing_ok=True)
        raise
    aplicar_retencao(pasta, manter, base=origem.stem)
    return destino


def restaurar(backup: Path, destino: Path, confirmo_sobrescrever: bool = False) -> Path:
    """Restaura `backup` em `destino` (também pela API de backup, depois valida).

    Recusa sobrescrever um arquivo existente sem confirmação explícita; ao
    sobrescrever, guarda o que havia como `<destino>.antes_da_restauracao_<data>`.
    """
    validar(backup)
    if destino.resolve() == backup.resolve():
        raise ValueError("O destino não pode ser o próprio arquivo de backup.")
    if destino.exists() and not confirmo_sobrescrever:
        raise FileExistsError(
            f"{destino} já existe. Para sobrescrever, repita com --confirmo-sobrescrever "
            "(uma cópia do arquivo atual é guardada antes)."
        )
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(destino.name + ".restaurando")
    temporario.unlink(missing_ok=True)
    src = _abrir_leitura(backup)
    dst = sqlite3.connect(temporario)
    try:
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")
    finally:
        dst.close()
        src.close()
    try:
        validar(temporario)
    except BackupInvalido:
        temporario.unlink(missing_ok=True)
        raise
    if destino.exists():
        guarda = destino.with_name(f"{destino.name}.antes_da_restauracao_{datetime.now():%Y%m%d_%H%M%S}")
        os.replace(destino, guarda)
        # arquivos laterais do WAL do banco antigo não valem para o novo
        for sufixo in ("-wal", "-shm"):
            Path(str(destino) + sufixo).unlink(missing_ok=True)
    os.replace(temporario, destino)
    return destino


def _origem() -> Path:
    from Src.common.app_paths import caminho_banco

    return caminho_banco()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Backup e restauração do banco SQLite.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("criar", help="cria, valida e aplica a retenção")
    c.add_argument("--origem", type=Path, help="banco de origem (padrão: PLATAFORMA_DB)")
    c.add_argument("--pasta", type=Path, help="pasta dos backups")
    c.add_argument("--manter", type=int, help=f"quantas cópias guardar (padrão {MANTER_PADRAO})")

    v = sub.add_parser("validar", help="integrity_check e contagem de tabelas")
    v.add_argument("arquivo", type=Path)

    ls = sub.add_parser("listar", help="lista os backups da pasta")
    ls.add_argument("--pasta", type=Path)

    r = sub.add_parser("restaurar", help="restaura um backup em um arquivo de destino")
    r.add_argument("backup", type=Path)
    r.add_argument("--destino", type=Path, required=True)
    r.add_argument("--confirmo-sobrescrever", action="store_true")

    a = ap.parse_args(argv)
    try:
        if a.cmd == "criar":
            manter = a.manter if a.manter is not None else manter_padrao()
            feito = criar_backup(a.origem or _origem(), a.pasta or pasta_padrao(), manter)
            print(f"Backup criado e validado: {feito} ({feito.stat().st_size} bytes). Retenção: {manter}.")
        elif a.cmd == "validar":
            print(f"OK: {a.arquivo.name} íntegro, {validar(a.arquivo)} tabelas.")
        elif a.cmd == "listar":
            for p in listar(a.pasta or pasta_padrao()):
                print(p.name)
        elif a.cmd == "restaurar":
            print(f"Restaurado em: {restaurar(a.backup, a.destino, a.confirmo_sobrescrever)}")
    except (BackupInvalido, FileNotFoundError, FileExistsError, ValueError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
