"""Salvamento de planilhas com mensagem clara quando o arquivo está aberto."""

from __future__ import annotations

from pathlib import Path


class ArquivoEmUsoError(PermissionError):
    """O arquivo de destino está aberto (normalmente no Excel) e não pode ser gravado."""


def salvar_workbook(wb, caminho: str | Path) -> None:
    """`wb.save(caminho)` trocando o "[Errno 13] Permission denied" do Windows
    por uma mensagem que diz ao usuário o que fazer."""
    try:
        wb.save(caminho)
    except PermissionError as e:
        nome = Path(caminho).name
        raise ArquivoEmUsoError(
            f"O arquivo '{nome}' está aberto no Excel (ou em outro programa).\n\n"
            f"Feche o arquivo e tente novamente."
        ) from e
