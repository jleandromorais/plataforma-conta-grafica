"""Aviso de "possível duplicata" das provas reais: notas do mesmo grupo com o mesmo valor.

O dedupe por número da nota (ND, número da NF-e/CT-e) só pega a repetição quando o número é lido
igual nas duas cópias. Uma cópia renomeada ("... -~7bf95f atualizada.pdf") escapa. Este aviso é o
segundo pente: duas notas do mesmo grupo com o mesmo valor merecem um olhar do analista.
É só um aviso, nada é removido nem recalculado.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Iterable


def possiveis_duplicatas_por_valor(
    itens: Iterable[dict[str, Any]],
    *,
    grupo: Callable[[dict[str, Any]], str],
    valor: Callable[[dict[str, Any]], float | None],
    nome: Callable[[dict[str, Any]], str],
    ja_avisada: Callable[[dict[str, Any]], bool] = lambda _i: False,
    contexto: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Grupos de 2+ notas com o mesmo valor (2 casas) dentro do mesmo `grupo`.

    Valor zero fica fora (nota que não pesa na conta). Um grupo cujas notas já foram todas
    avisadas como repetidas pelo número (`ja_avisada`) não é repetido aqui. Devolve
    `[{"grupo", "valor", "qtd", "notas", "ids"}]` do maior valor (em módulo) para o menor.
    `ids` são os ids gravados das notas (campo `id` do item), na mesma ordem de `notas`:
    é por eles que a tela tira uma nota do cálculo.

    `detalhes` traz o contexto de cada nota, na mesma ordem de `notas`, para o analista decidir se é
    cópia ou nota diferente: `{id, nome, numero, valor, volume?, vencimento?}`. `contexto(item)`
    devolve o que cada módulo sabe (`numero`, `volume`, `vencimento`); o que for None não aparece."""
    por_chave: dict[tuple[str, float], list[dict[str, Any]]] = defaultdict(list)
    for item in itens:
        v = valor(item)
        if v is None or round(float(v), 2) == 0:
            continue
        por_chave[(grupo(item), round(float(v), 2))].append(item)

    def _detalhe(n: dict[str, Any], v: float) -> dict[str, Any]:
        extra = contexto(n) if contexto else {}
        numero = extra.get("numero")
        achado = {"id": n.get("id"), "nome": nome(n), "numero": None if numero is None else str(numero), "valor": v}
        for campo in ("volume", "vencimento"):
            if extra.get(campo) not in (None, ""):
                achado[campo] = extra[campo]
        return achado

    achadas = [
        {"grupo": g, "valor": v, "qtd": len(notas), "notas": [nome(n) for n in notas],
         "ids": [n["id"] for n in notas if n.get("id") is not None],
         "detalhes": [_detalhe(n, v) for n in notas]}
        for (g, v), notas in por_chave.items()
        if len(notas) > 1 and not all(ja_avisada(n) for n in notas)
    ]
    achadas.sort(key=lambda d: (-abs(d["valor"]), d["grupo"]))
    return achadas
