"""Mensagens de ERRO do ciclo (campo `erros` das respostas), só a partir de dados já calculados.

Não faz conta nova: lê o que as provas reais e a comparação já devolvem e, quando algo
não confere, escreve uma frase em português (etapa, mês e valores) para o site mostrar
como aviso de erro. Lista vazia = nada de errado. Nunca grava nada.
"""
from __future__ import annotations

from typing import Any

from Src.Services.comparacao.explicador_diferencas import TOL_VALOR, brl

_NUMEROS_VAZIOS = {"", "0", "n/a", "na", "s/n", "s/nº"}


def _fora(a: float | None, b: float | None, tol: float = TOL_VALOR) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) > tol


def _conta(etapa: str, periodo: str, gravado: float | None, calculado: float | None, rotulo: str) -> list[str]:
    if gravado is None or calculado is None or not _fora(gravado, calculado):
        return []
    return [f"{etapa} {periodo}: o valor gravado ({brl(gravado)}) é diferente do {rotulo} ({brl(calculado)}); "
            f"diferença de {brl(float(gravado) - float(calculado))}. Reprocesse e grave de novo."]


def erros_prova_real_cgf(d: dict[str, Any]) -> list[str]:
    if not d.get("tem_resumo"):
        return []
    p, erros = d.get("periodo", ""), []
    if d.get("pmpv") is None:
        erros.append(f"CGF {p}: não há PMPV gravado para o mês, então o CGF em R$ não pode ser conferido. "
                     "Grave o PMPV do mês primeiro.")
    if not d.get("volume_confere"):
        erros.append(f"CGF {p}: o volume final gravado ({d.get('volume_final_gravado')} m³) não confere com o calculado "
                     f"({d.get('volume_final_calculado')} m³). Reprocesse as planilhas de NF e grave de novo.")
    if d.get("pmpv") is not None and not d.get("cgf_confere"):
        erros += _conta("CGF", p, d.get("cgf_gravado"), d.get("cgf_calculado"), "calculado (volume final × PMPV)")
    return erros


def erros_calcular_rs(d: dict[str, Any]) -> list[str]:
    if d.get("pmpv_origem") == "ausente" or d.get("cgf_rs") is None:
        return [f"CGF {d.get('periodo', '')}: PMPV ausente; o CGF em R$ não foi calculado. Grave o PMPV do mês ou informe-o."]
    return []


def erros_prova_real_cgr(d: dict[str, Any]) -> list[str]:
    if d.get("cgr_gravado") is None or d.get("confere", True):
        return []
    return _conta("Auditoria CGR", d.get("periodo", ""), d.get("cgr_gravado"), d.get("cgr_das_notas"),
                  "soma das notas gravadas")


def erros_prova_real_rp(d: dict[str, Any]) -> list[str]:
    if d.get("rp_gravado") is None or d.get("confere", True):
        return []
    return _conta("RP", d.get("periodo", ""), d.get("rp_gravado"), d.get("rp_calculado"), "refeito com os itens gravados")


def erros_prova_real_ret(d: dict[str, Any]) -> list[str]:
    if d.get("ret_gravado") is None or d.get("confere", True):
        return []
    return _conta("RET", d.get("periodo", ""), d.get("ret_gravado"), d.get("ret_calculado"), "refeito com os itens gravados")


def erros_prova_real_rpv(d: dict[str, Any]) -> list[str]:
    if not d.get("gravado") or d.get("confere", True):
        return []
    p = d.get("periodo", "")
    erros = _conta("RPV", p, d.get("rpv_gravado"), d.get("rpv_calculado"), "calculado (CGR − CGF)")
    if d.get("origem_cgr") and not d["origem_cgr"].get("confere", True):
        erros.append(f"RPV {p}: o CGR gravado não confere com a soma das notas da Auditoria CGR.")
    if d.get("origem_cgf") and not d["origem_cgf"].get("confere", True):
        erros.append(f"RPV {p}: o CGF gravado não confere com volume final × PMPV.")
    return erros


def erros_diferencas_auditoria(d: dict[str, Any], periodo: str) -> list[str]:
    """Processado x gravado do CGR além da tolerância (R$ 1,00)."""
    if not d.get("tem_notas_gravadas") or abs(d.get("diferenca", 0.0)) <= TOL_VALOR:
        return []
    erros = [f"Auditoria CGR {periodo}: o CGR processado ({brl(d['cgr_processado'])}) difere do gravado "
             f"({brl(d['cgr_gravado_notas'])}) em {brl(d['diferenca'])}; "
             f"{d.get('qtd_notas_diferentes', 0)} nota(s) diferente(s)."]
    for n in d.get("notas", [])[:3]:
        if n.get("ocr"):
            erros.append(f"Auditoria CGR {periodo}: a nota {n['tipo']} {n['numero']} de {n['empresa']} foi lida por OCR "
                         f"e difere em {brl(n['diferenca'])}. Confira o valor no PDF.")
    return erros


def erros_notas_ocr(itens: list[Any], periodo: str = "") -> list[str]:
    """Notas lidas por OCR com valor suspeito: sem número, valor zero/negativo ou ICMS maior que a nota."""
    sufixo = f" {periodo}" if periodo else ""
    erros = []
    for i in itens:
        if str(i.status).upper() != "OCR":
            continue
        valor, numero = float(i.valor_total or 0), str(i.numero).strip().lower()
        if numero in _NUMEROS_VAZIOS or valor <= 0 or float(i.icms or 0) > valor:
            erros.append(f"Auditoria CGR{sufixo}: nota {i.tipo} {i.numero or 's/nº'} de {i.empresa} lida por OCR com valor "
                         f"suspeito ({brl(valor)}). Confira o PDF.")
    return erros


def erros_comparacao_planilha(comp: Any, periodo: str = "") -> list[str]:
    """CGR das notas x CGR da Conta Gráfica da planilha."""
    if comp is None:
        return []
    sufixo = f" {periodo}" if periodo else ""
    erros = []
    if _fora(comp.cgr_auditoria, comp.cgr_planilha_conta_grafica):
        erros.append(f"Auditoria CGR{sufixo}: o CGR das notas ({brl(comp.cgr_auditoria)}) difere do da planilha "
                     f"({brl(comp.cgr_planilha_conta_grafica)}) em {brl(comp.cgr_auditoria - comp.cgr_planilha_conta_grafica)}.")
    if comp.divergencias_valor:
        erros.append(f"Auditoria CGR{sufixo}: {len(comp.divergencias_valor)} nota(s) com valor diferente da planilha.")
    return erros
