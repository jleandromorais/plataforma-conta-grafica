"""Recebimento de PASTAS enviadas pelo navegador (Auditoria, RET, Conciliação).

O navegador manda cada arquivo com o caminho relativo no nome
("EMPRESA/sub/arquivo.xml"); também aceita um .zip com a mesma estrutura.
As regras de vários módulos dependem dos nomes das pastas (empresa, EAT/EC,
devolução, mês), por isso a estrutura é recriada fielmente.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath

from starlette.datastructures import UploadFile

MAX_ARQUIVOS = 20_000  # uma pasta de notas passa fácil do padrão do servidor (1.000)


def caminho_seguro(nome: str) -> PurePosixPath | None:
    """Caminho relativo sem '..' nem raiz/unidade (evita escrever fora da pasta)."""
    partes = [p for p in PurePosixPath(nome.replace("\\", "/")).parts if p not in ("", ".", "/")]
    if not partes or any(p == ".." or p.endswith(":") for p in partes):
        return None
    return PurePosixPath(*partes)


def gravar_envio(form, destino: Path, extensoes: set[str], campo: str = "arquivos") -> int:
    """Grava em `destino` os arquivos de `campo` com as extensões aceitas
    (e o conteúdo de .zip), mantendo as subpastas. Retorna quantos gravou."""
    gravados = 0
    for nome_campo, valor in form.multi_items():
        if nome_campo != campo or not isinstance(valor, UploadFile):
            continue
        rel = caminho_seguro(valor.filename or "")
        if rel is None:
            continue
        if rel.suffix.lower() == ".zip":
            caminho_zip = destino / "__envio.zip"
            with caminho_zip.open("wb") as f:
                shutil.copyfileobj(valor.file, f)
            with zipfile.ZipFile(caminho_zip) as z:
                for info in z.infolist():
                    rel_z = caminho_seguro(info.filename)
                    if info.is_dir() or rel_z is None or rel_z.suffix.lower() not in extensoes:
                        continue
                    alvo = destino.joinpath(*rel_z.parts)
                    alvo.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(info) as src, alvo.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
                    gravados += 1
            caminho_zip.unlink()
            continue
        if rel.suffix.lower() not in extensoes:
            continue
        alvo = destino.joinpath(*rel.parts)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        with alvo.open("wb") as f:
            shutil.copyfileobj(valor.file, f)
        gravados += 1
    return gravados


def descer_pasta_unica(pasta: Path) -> Path:
    """Se tudo veio dentro de uma única pasta (ex.: o zip da pasta pai), desce nela."""
    atual = pasta
    while True:
        filhos = list(atual.iterdir())
        if len(filhos) == 1 and filhos[0].is_dir() and any(c.is_dir() for c in filhos[0].iterdir()):
            atual = filhos[0]
        else:
            return atual


def gravar_arquivo(form, campo: str, pasta: Path, nome_base: str) -> Path | None:
    """Grava um arquivo avulso do formulário (ex.: a planilha de comparação)."""
    up = form.get(campo)
    if not isinstance(up, UploadFile) or not up.filename:
        return None
    destino = pasta / (nome_base + (Path(up.filename).suffix.lower() or ".xlsx"))
    with destino.open("wb") as f:
        shutil.copyfileobj(up.file, f)
    return destino
