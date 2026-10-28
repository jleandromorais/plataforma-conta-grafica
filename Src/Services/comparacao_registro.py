"""Registro dos modelos de planilha que a auditoria sabe comparar.

Para ensinar uma planilha nova:
  1. crie `comparador_modelo_<nome>.py` com `ler_modelo(caminho)` (devolve o modelo
     lido, ou None se a planilha não segue o layout) e `comparar(itens, modelo, periodo)`
     (devolve um `ResultadoComparacaoNotas`); reaproveite as regras de
     `explicador_diferencas` para dizer o porquê das diferenças;
  2. acrescente uma linha em `MODELOS` abaixo.

Nada mais muda: a tela e o relatório Excel escolhem o layout pelo `tipo`:

  - "por_nota"      a planilha lista nota a nota (compara presença, valor, volume, alíquota);
  - "por_supridor"  a planilha só traz totais por supridor (volume e CGR);
  - "generico"      só presença das notas (comparador sem modelo conhecido).

Os modelos são tentados na ordem; o primeiro que reconhece o layout vence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from Src.Services import comparador_modelo_alexandre as _alexandre
from Src.Services import comparador_modelo_apuracao as _apuracao
from Src.Services import comparador_modelo_nt as _nt
from Src.Services.comparador_conta_grafica import ResultadoComparacaoNotas
from Src.Services.servicos_auditoria import XMLItem

TIPOS = ("por_nota", "por_supridor", "generico")


@dataclass(frozen=True)
class ModeloComparacao:
    nome: str       # vai em `modelo` na resposta ("alexandre", "nt")
    rotulo: str     # texto para o usuário
    tipo: str       # um de TIPOS
    ler: Callable[[str], Any | None]
    comparar: Callable[[list[XMLItem], Any, str], ResultadoComparacaoNotas]


MODELOS: tuple[ModeloComparacao, ...] = (
    ModeloComparacao("alexandre", "Modelo Alexandre", "por_nota", _alexandre.ler_modelo, _alexandre.comparar),
    ModeloComparacao("apuracao", "Conta Gráfica e Apuração de Custos", "por_nota", _apuracao.ler_modelo, _apuracao.comparar),
    ModeloComparacao("nt", "Modelo NT", "por_supridor", _nt.ler_modelo, _nt.comparar),
)


def comparar_com_modelo(itens: list[XMLItem], caminho: str, periodo: str) -> ResultadoComparacaoNotas | None:
    """Compara com o primeiro modelo que reconhece a planilha; None se nenhum reconhece."""
    for m in MODELOS:
        lido = m.ler(caminho)
        if lido is None:
            continue
        r = m.comparar(itens, lido, periodo)
        r.modelo, r.tipo, r.modelo_rotulo = m.nome, m.tipo, m.rotulo
        return r
    return None
