from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProblemaArquivo(BaseModel):
    """Problema num arquivo enviado, para a tela explicar o que houve (ver Front_end/SPEC_ERROS.md).

    `codigo` é estável (testes e UI dependem dele); `mensagem` é o texto pt-BR
    para o usuário; `tecnico` é um detalhe opcional, nunca com caminho do servidor.
    """
    arquivo: str
    empresa: str | None = None
    gravidade: Literal["erro", "aviso", "info"]
    codigo: str
    mensagem: str
    tecnico: str | None = None
