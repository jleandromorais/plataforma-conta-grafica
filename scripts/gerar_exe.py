"""Gera o .exe da plataforma pronto para entrega.

Uso (na raiz do projeto, com o ambiente virtual):
    python scripts/gerar_exe.py

Passos:
1. Confere se o banco dentro do .exe anterior tem dados mais novos que o banco
   oficial — se tiver, para (para não apagar trabalho feito pelo .exe);
2. Compila com PyInstaller (PlataformaFinanceira.spec);
3. Copia o banco oficial para dentro da pasta do .exe usando o backup do
   SQLite (inclui o que ainda está no arquivo -wal);
4. Apaga a pasta build/ (temporária; tem um .exe que NÃO funciona e confunde);
5. Gera dist/PlataformaFinanceira_AAAAMMDD.zip para enviar.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from Src.common.app_paths import caminho_banco  # noqa: E402

PASTA_EXE = RAIZ / "dist" / "PlataformaFinanceira"
BANCO_EXE = PASTA_EXE / "pmpv_data.db"
# Data de modificação do banco do .exe logo após a cópia feita por este
# script — sem isso, a própria cópia parece "alteração pelo .exe".
MARCA_COPIA = PASTA_EXE / "pmpv_data.db.copiado"


def _ultima_alteracao(banco: Path) -> float:
    """Data da última gravação, considerando o arquivo -wal."""
    datas = [banco.stat().st_mtime]
    wal = banco.with_name(banco.name + "-wal")
    if wal.exists() and wal.stat().st_size > 0:
        datas.append(wal.stat().st_mtime)
    return max(datas)


def _conteudo(banco: Path) -> str:
    con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
    try:
        return "\n".join(con.iterdump())
    finally:
        con.close()


def _exe_alterou_banco() -> bool:
    if MARCA_COPIA.exists():
        return _ultima_alteracao(BANCO_EXE) > float(MARCA_COPIA.read_text().strip()) + 1
    return True  # sem marca: decide pelo conteúdo (ver _conferir_banco_do_exe)


def _conferir_banco_do_exe(oficial: Path) -> None:
    if not BANCO_EXE.exists() or not _exe_alterou_banco():
        return
    if _conteudo(BANCO_EXE) == _conteudo(oficial):
        return  # igual ao oficial: nada a perder
    if _ultima_alteracao(BANCO_EXE) > _ultima_alteracao(oficial):
        sys.exit(
            f"PARADO: o banco do .exe ({BANCO_EXE}) foi alterado depois do banco "
            f"oficial ({oficial}).\nAlguém salvou dados pelo .exe. Copie esse banco "
            f"para o local oficial (ou faça backup dele) antes de gerar de novo."
        )


def _copiar_banco(oficial: Path) -> None:
    origem = sqlite3.connect(oficial)
    destino = sqlite3.connect(BANCO_EXE)
    try:
        origem.backup(destino)
        destino.execute("PRAGMA journal_mode=DELETE")
        destino.commit()
        status = destino.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            sys.exit(f"ERRO: cópia do banco falhou na verificação de integridade: {status}")
    finally:
        destino.close()
        origem.close()
    MARCA_COPIA.write_text(str(BANCO_EXE.stat().st_mtime))


def main() -> None:
    oficial = caminho_banco()
    print(f"Banco oficial: {oficial}")
    _conferir_banco_do_exe(oficial)

    print("Compilando (alguns minutos)...")
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "PlataformaFinanceira.spec", "--noconfirm"],
        cwd=RAIZ, check=True,
    )

    _copiar_banco(oficial)
    print(f"Banco copiado para {BANCO_EXE}")

    shutil.rmtree(RAIZ / "build", ignore_errors=True)
    print("Pasta build/ removida")

    zip_base = RAIZ / "dist" / f"PlataformaFinanceira_{datetime.now():%Y%m%d}"
    arquivo_zip = shutil.make_archive(str(zip_base), "zip", root_dir=PASTA_EXE.parent,
                                      base_dir=PASTA_EXE.name)
    print(f"\nPronto. Entregar: {arquivo_zip}")
    print(f"(ou a pasta inteira: {PASTA_EXE})")


if __name__ == "__main__":
    main()
