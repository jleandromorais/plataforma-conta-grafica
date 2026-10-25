"""Por que a auditoria difere da planilha de referência.

Regras compartilhadas por todos os comparadores (cada um só traz os números
da sua planilha). Só afirma o que dá para provar com as notas lidas — nota que
sozinha explica o valor, alíquota, volume de outro mês, OCR, supridor ausente.
Quando nada explica, diz isso em vez de chutar uma causa.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any, Callable

from Src.Services.comparador_conta_grafica import _normalizar_numero_nota
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem
from Src.Services.supridores import supridor_canonico

TOL_VALOR = 1.00         # R$ — abaixo disso é arredondamento
TOL_VOLUME = 1.0         # m³
MAX_NOTAS_PAR = 300      # busca de pares de notas só até aqui (C(300,2) ≈ 45 mil)


# ── Formatação ───────────────────────────────────────────────────────────────

def n(v: float, casas: int = 0) -> str:
    """Número no padrão brasileiro: 1.234.567,89."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v: float) -> str:
    return f"{'-' if v < 0 else ''}R$ {n(abs(v), 2)}"


def aviso_total(avisos: list[str], fonte: str, auditoria: float, referencia: float | None) -> None:
    """Acrescenta a linha 'CGR confere' ou 'CGR DIVERGENTE' (a tela pinta pelo prefixo)."""
    if referencia is None:
        return
    dif = auditoria - referencia
    if abs(dif) <= TOL_VALOR:
        avisos.append(f"CGR confere com a planilha ({fonte}): {brl(auditoria)}.")
        return
    pct = f" ({dif / referencia * 100:+.2f}%)" if referencia else ""
    avisos.append(
        f"CGR DIVERGENTE: auditoria {brl(auditoria)} × planilha ({fonte}) {brl(referencia)} "
        f"→ diferença de {brl(dif)}{pct}."
    )


# ── Notas por supridor ───────────────────────────────────────────────────────

def _sinal(item: XMLItem) -> float:
    from Src.Services.servicos_auditoria_lote import eh_devolucao
    return -1.0 if eh_devolucao(item) else 1.0


def agrupar_por_supridor(itens: list[XMLItem]) -> dict[str, list[XMLItem]]:
    """Só o que entra no CGR (NF-e e CT-e de gasoduto), agrupado pelo nome canônico."""
    from Src.Services.servicos_auditoria_lote import integra_cgr

    out: dict[str, list[XMLItem]] = defaultdict(list)
    for it in itens:
        if integra_cgr(it):
            out[supridor_canonico(it.empresa)].append(it)
    return out


def cgr_nota(it: XMLItem) -> float:
    """CGR s/ tributos da nota; devolução entra negativa."""
    return _sinal(it) * RegrasAuditoria.calcular_s_tributos(it.valor_total, it.icms_taxa)


def vol_nota(it: XMLItem) -> float:
    return _sinal(it) * float(it.volume_total or it.volume or 0)


def rotulo_nota(it: XMLItem) -> str:
    return f"{it.tipo} {it.numero}" + (" (devolução)" if _sinal(it) < 0 else "")


def notas_que_somam(notas: list[XMLItem], alvo: float, valor: Callable[[XMLItem], float], tol: float) -> list[XMLItem] | None:
    """Uma nota (ou, se não houver, um par) cujo valor sozinho soma `alvo`."""
    for nota in notas:
        if abs(valor(nota) - alvo) <= tol:
            return [nota]
    if len(notas) <= MAX_NOTAS_PAR:
        for a, b in combinations(notas, 2):
            if abs(valor(a) + valor(b) - alvo) <= tol:
                return [a, b]
    return None


# ── Explicações ──────────────────────────────────────────────────────────────

def explicar_cgr(nome: str, notas: list[XMLItem], cgr_aud: float, cgr_ref: float | None,
                 vol_aud: float, vol_ref: float | None, fonte: str = "planilha") -> list[str]:
    """Por que o CGR das notas difere do CGR da `fonte` (dif = notas − fonte)."""
    out: list[str] = []
    if cgr_ref is None or (not cgr_ref and not vol_ref):
        out.append(f"A {fonte} não tem {nome} neste mês, mas as notas lidas somam {brl(cgr_aud)}. "
                   f"Confira se as notas são mesmo deste mês ou se a {fonte} deixou o supridor de fora.")
        return out
    if not notas:
        out.append(f"A {fonte} tem {brl(cgr_ref)} de {nome}, mas nenhuma nota dele entrou na auditoria. Confira se a subpasta "
                   "do supridor está na pasta enviada e se a empresa está marcada.")
        return out

    dif = cgr_aud - cgr_ref
    # 1) volume diferente → valor diferente (a conta mais comum)
    dvol = vol_aud - (vol_ref or 0.0)
    if vol_ref and abs(dvol) > TOL_VOLUME and vol_aud:
        preco = cgr_aud / vol_aud
        out.append(f"O volume é diferente: {n(vol_aud)} m³ nas notas × {n(vol_ref)} m³ na {fonte} "
                   f"({'+' if dvol > 0 else '-'}{n(abs(dvol))} m³). Ao preço médio das notas (R$ {n(preco, 4)}/m³) "
                   f"isso vale ≈ {brl(dvol * preco)}.")
    elif vol_ref and vol_aud:
        pa, pr = cgr_aud / vol_aud, cgr_ref / vol_ref
        out.append(f"O volume confere ({n(vol_aud)} m³), mas o preço médio não: R$ {n(pa, 4)}/m³ nas notas × "
                   f"R$ {n(pr, 4)}/m³ na {fonte}. Veja valor unitário e alíquota de ICMS das notas.")

    # 2) uma nota (ou um par) que sozinha explica a diferença
    achou = notas_que_somam(notas, dif, cgr_nota, TOL_VALOR) if dif > 0 else None
    if achou:
        lista = " + ".join(f"{rotulo_nota(x)} ({brl(cgr_nota(x))})" for x in achou)
        out.append(f"{lista} {'somam' if len(achou) > 1 else 'sozinha explica'} a diferença: "
                   f"está nas notas lidas e não está no CGR da {fonte}.")
    elif dif < 0:
        dobro = [x for x in notas if _sinal(x) < 0 and abs(2 * cgr_nota(x) - dif) <= TOL_VALOR]
        if dobro:
            x = dobro[0]
            out.append(f"A devolução {x.numero} ({brl(cgr_nota(x))}) explica a diferença: as notas a abatem e a {fonte} não (ou a soma).")
        else:
            out.append(f"A {fonte} tem {brl(-dif)} a mais do que as notas lidas e nenhuma nota ou devolução isolada explica esse valor. "
                       f"Possíveis causas: nota deste supridor que não está na pasta, ajuste lançado à mão na {fonte}, ou nota de outro mês.")

    # 3) alíquota de ICMS: a fonte bate se todas as notas usassem uma alíquota única?
    taxas = sorted({round(float(x.icms_taxa or 0), 4) for x in notas})
    if len(taxas) > 1:
        cont = ", ".join(f"{t * 100:g}% ({sum(1 for x in notas if round(float(x.icms_taxa or 0), 4) == t)} notas)" for t in taxas)
        out.append(f"As notas têm alíquotas de ICMS diferentes: {cont}.")
    for t in sorted(set(taxas) | {0.07, 0.12, 0.17, 0.18}):
        alt = sum(_sinal(x) * RegrasAuditoria.calcular_s_tributos(x.valor_total, t) for x in notas)
        if abs(alt - cgr_ref) <= TOL_VALOR and abs(dif) > TOL_VALOR:
            out.append(f"A {fonte} bate se todas as notas usassem alíquota de {t * 100:g}% — ela parece ter calculado com essa alíquota.")
            break

    # 4) leitura por OCR / número ilegível
    ocr = [x for x in notas if x.status == "OCR"]
    sem_num = [x for x in notas if not _normalizar_numero_nota(x.numero).strip("0")]
    if sem_num:
        out.append(f"{len(sem_num)} nota(s) com número ilegível (lido por OCR do PDF): confira os valores dela(s) no arquivo.")
    elif ocr:
        out.append(f"{len(ocr)} nota(s) foram lidas por OCR do PDF (sem XML): o OCR pode errar valores.")
    return out


def explicar_volume(notas: list[XMLItem], vol_aud: float, vol_ref: float, cgr_bate: bool, fonte: str = "planilha",
                    outros_meses: dict[str, float] | None = None, periodo: str = "") -> list[str]:
    """Só o volume diverge (o CGR bate ou não há como comparar CGR).

    `outros_meses`: período → volume que a fonte tem para o mesmo supridor.
    """
    dvol = vol_aud - vol_ref
    out = [f"Volume diferente: {n(vol_aud)} m³ nas notas × {n(vol_ref)} m³ na {fonte} "
           f"({'+' if dvol > 0 else '-'}{n(abs(dvol))} m³)."]
    if cgr_bate:
        out.append(f"O CGR em R$ confere com a {fonte}; só o volume (m³) difere. Os valores das notas estão certos: "
                   f"o volume lançado na {fonte} é que não acompanha as notas.")
    devs = [x for x in notas if _sinal(x) < 0]
    if devs:
        out.append(f"As notas têm {len(devs)} devolução(ões) que reduzem o volume em {n(sum(abs(vol_nota(x)) for x in devs))} m³: "
                   + ", ".join(f"{rotulo_nota(x)} ({n(abs(vol_nota(x)))} m³)" for x in devs)
                   + f". Veja se a {fonte} abate essa devolução do volume.")
    achou = notas_que_somam(notas, dvol, vol_nota, TOL_VOLUME) if dvol > 0 else None
    if achou:
        out.append(" + ".join(f"{rotulo_nota(x)} ({n(vol_nota(x))} m³)" for x in achou)
                   + f" {'somam' if len(achou) > 1 else 'sozinha explica'} a diferença de volume.")
    for per, vol in (outros_meses or {}).items():
        if per != periodo and abs(vol - vol_aud) <= max(TOL_VOLUME, 0.001 * vol_aud):
            out.append(f"O volume das notas ({n(vol_aud)} m³) é igual (ou quase) ao que a {fonte} tem em {per} ({n(vol)} m³): "
                       f"pode ser lançamento de mês trocado na {fonte} ou nota de {per} na pasta de {periodo}.")
            break
    return out


def explicar_notas_faltando(apenas_aud: list[dict[str, Any]], apenas_ref: list[dict[str, Any]], fonte: str = "planilha",
                            dif_cgr: float | None = None) -> tuple[list[str], bool]:
    """Notas que só existem de um dos lados (comparadores que têm a lista de notas).

    Cada nota é {"numero", "cgr"}. Devolve (frases, explica_tudo): `explica_tudo` é True
    quando a soma das notas que faltam fecha a diferença de CGR (`dif_cgr` = notas − fonte).
    """
    out: list[str] = []
    for lista, texto in ((apenas_ref, f"estão na {fonte} e NÃO vieram nos arquivos enviados"),
                         (apenas_aud, f"vieram nos arquivos e NÃO estão na {fonte}")):
        if not lista:
            continue
        itens = ", ".join(f"{x.get('numero')} ({brl(x.get('cgr', 0.0))})" for x in lista[:8]) + (" …" if len(lista) > 8 else "")
        dica = (f"Confira se faltam XML/PDF na pasta do supridor ou se a {fonte} lançou nota de outro mês."
                if lista is apenas_ref else f"Confira se a {fonte} foi atualizada com elas.")
        out.append(f"{len(lista)} nota(s) {texto}: {itens}. {dica}")
    explica = False
    if dif_cgr is not None and (apenas_aud or apenas_ref):
        fecha = sum(x.get("cgr", 0.0) for x in apenas_aud) - sum(x.get("cgr", 0.0) for x in apenas_ref)
        explica = abs(dif_cgr - fecha) <= TOL_VALOR
        if explica:
            out.append(f"Essas notas explicam toda a diferença de CGR ({brl(dif_cgr)}).")
    return out, explica
