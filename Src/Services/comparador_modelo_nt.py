"""Comparação da auditoria CGR com a planilha da Nota Técnica ("NT_xx_2026 -
Dados da Nota Técnica ...xlsx").

A aba "Q5 - SCG - Anexo A" tem, para cada mês, um bloco com o cabeçalho
"MM/AAAA | VF Líquido" e, logo abaixo, a tabela de supridores:

    Fornecedor | Volume Adquirido aos Fornecedores | Custo do Gás Realizado (CGR) | ...

Não há uma linha por nota: a comparação é por supridor (volume e CGR). Quando
há diferença, `explicar_*` diz o porquê com o que dá para provar a partir das
notas lidas (nota que sozinha explica o valor, alíquota, volume de outro mês,
leitura por OCR, supridor ausente...). Quando nada explica, diz isso também —
sem chutar causa.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import combinations
from typing import Any

from Src.common.periodos import normalizar_periodo
from Src.Services.comparador_conta_grafica import ResultadoComparacaoNotas, _normalizar_numero_nota
from Src.Services.comparador_modelo_alexandre import _aviso_total, _brl, supridor_canonico
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem

ABA_SCG = "q5scg"        # início do nome da aba, sem acento/símbolos ("Q5 - SCG - Anexo A")
TOL_VALOR = 1.00         # R$
TOL_VOLUME = 1.0         # m³
MAX_NOTAS_PAR = 300      # busca de pares de notas só até aqui (C(300,2) ≈ 45 mil)

_PERIODO_RE = re.compile(r"^\s*(\d{2})/(\d{4})\s*$")


def _token(texto: Any) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", limpo.lower())


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _n(v: float, casas: int = 0) -> str:
    """Número no padrão brasileiro: 1.234.567,89."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo_da_celula(v: Any) -> str:
    """'07/2026' ou datetime(2026, 7, 1) → 'Jul/2026'; outra coisa → ''."""
    if isinstance(v, (datetime, date)):
        return normalizar_periodo(f"{v.month:02d}/{v.year}") or ""
    m = _PERIODO_RE.match(v) if isinstance(v, str) else None
    return (normalizar_periodo(f"{m.group(1)}/{m.group(2)}") or "") if m else ""


@dataclass
class SupridorNT:
    volume: float = 0.0
    cgr: float = 0.0
    nomes: list[str] = field(default_factory=list)   # como está escrito na planilha


@dataclass
class ModeloNT:
    aba: str
    blocos: dict[str, dict[str, SupridorNT]] = field(default_factory=dict)   # período → supridor canônico → valores

    @property
    def periodos(self) -> list[str]:
        return list(self.blocos)


def _ler_blocos(ws) -> dict[str, dict[str, SupridorNT]]:
    linhas = [tuple(r) for r in ws.iter_rows(values_only=True)]
    blocos: dict[str, dict[str, SupridorNT]] = {}
    for i, row in enumerate(linhas):
        for c, v in enumerate(row):
            if _token(v) != "fornecedor" or i == 0:
                continue
            # Período: a célula "MM/AAAA" mais próxima, à esquerda (ou na mesma coluna), na linha de cima.
            acima = linhas[i - 1]
            cand = [(c - k, _periodo_da_celula(acima[k])) for k in range(0, c + 1) if k < len(acima) and _periodo_da_celula(acima[k])]
            if not cand:
                continue
            periodo = min(cand, key=lambda x: x[0])[1]
            # Colunas pelo texto do cabeçalho (há células vazias/mescladas entre elas).
            c_vol = next((k for k in range(c + 1, len(row)) if _token(row[k]).startswith("volume")), None)
            c_cgr = next((k for k in range((c_vol or c) + 1, len(row))
                          if _token(row[k]).startswith(("custodogas", "cgr"))), None)
            if c_vol is None or c_cgr is None:
                continue
            tabela: dict[str, SupridorNT] = {}
            for linha in linhas[i + 1:]:
                nome = linha[c] if c < len(linha) else None
                if not isinstance(nome, str) or not nome.strip() or _token(nome).startswith("total"):
                    break
                vol = _num(linha[c_vol]) if c_vol < len(linha) else None
                cgr = _num(linha[c_cgr]) if c_cgr < len(linha) else None
                s = tabela.setdefault(supridor_canonico(nome), SupridorNT())
                s.volume += vol or 0.0
                s.cgr += cgr or 0.0
                s.nomes.append(nome.strip())
            if tabela:
                blocos.setdefault(periodo, tabela)   # primeiro bloco do mês vale
    return blocos


def ler_modelo(caminho: str) -> ModeloNT | None:
    """Lê a NT. Devolve None se não houver a aba "Q5 - SCG - Anexo A" com blocos
    de supridores (aí o chamador usa o comparador genérico)."""
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    try:
        for nome in wb.sheetnames:
            if _token(nome).startswith(ABA_SCG):
                blocos = _ler_blocos(wb[nome])
                if blocos:
                    return ModeloNT(aba=nome, blocos=blocos)
        return None
    finally:
        wb.close()


# ── Auditoria agrupada por supridor ──────────────────────────────────────────

def _sinal(item: XMLItem) -> float:
    from Src.Services.servicos_auditoria_lote import eh_devolucao
    return -1.0 if eh_devolucao(item) else 1.0


def _agrupar(itens: list[XMLItem]) -> dict[str, list[XMLItem]]:
    from Src.Services.servicos_auditoria_lote import integra_cgr

    out: dict[str, list[XMLItem]] = defaultdict(list)
    for it in itens:
        if integra_cgr(it):
            out[supridor_canonico(it.empresa)].append(it)
    return out


def _cgr(it: XMLItem) -> float:
    return _sinal(it) * RegrasAuditoria.calcular_s_tributos(it.valor_total, it.icms_taxa)


def _vol(it: XMLItem) -> float:
    return _sinal(it) * float(it.volume_total or it.volume or 0)


def _rotulo(it: XMLItem) -> str:
    return f"{it.tipo} {it.numero}" + (" (devolução)" if _sinal(it) < 0 else "")


# ── Explicações ──────────────────────────────────────────────────────────────

def _notas_que_somam(notas: list[XMLItem], alvo: float, valor, tol: float) -> list[XMLItem] | None:
    """Uma nota (ou, se não houver, um par) cujo valor sozinho soma `alvo`."""
    for n in notas:
        if abs(valor(n) - alvo) <= tol:
            return [n]
    if len(notas) <= MAX_NOTAS_PAR:
        for a, b in combinations(notas, 2):
            if abs(valor(a) + valor(b) - alvo) <= tol:
                return [a, b]
    return None


def _explicar_cgr(nome: str, notas: list[XMLItem], cgr_aud: float, cgr_nt: float | None,
                  vol_aud: float, vol_nt: float | None) -> list[str]:
    """Por que o CGR das notas difere do CGR da NT (`dif` = notas − NT)."""
    out: list[str] = []
    if cgr_nt is None or (not cgr_nt and not vol_nt):
        out.append(f"A NT não tem {nome} neste mês, mas as notas lidas somam {_brl(cgr_aud)}. "
                   "Confira se as notas são mesmo deste mês ou se a NT deixou o supridor de fora.")
        return out
    if not notas:
        out.append(f"A NT tem {_brl(cgr_nt)} de {nome}, mas nenhuma nota dele entrou na auditoria. Confira se a subpasta "
                   "do supridor está na pasta enviada e se a empresa está marcada.")
        return out

    dif = cgr_aud - cgr_nt
    # 1) volume diferente → valor diferente (a conta mais comum)
    dvol = vol_aud - (vol_nt or 0.0)
    if vol_nt and abs(dvol) > TOL_VOLUME and vol_aud:
        preco = cgr_aud / vol_aud
        out.append(f"O volume é diferente: {_n(vol_aud)} m³ nas notas × {_n(vol_nt)} m³ na NT "
                   f"({'+' if dvol > 0 else '-'}{_n(abs(dvol))} m³). Ao preço médio das notas (R$ {_n(preco, 4)}/m³) "
                   f"isso vale ≈ {_brl(dvol * preco)}.")
    elif vol_nt and vol_aud:
        pa, pn = cgr_aud / vol_aud, cgr_nt / vol_nt
        out.append(f"O volume confere ({_n(vol_aud)} m³), mas o preço médio não: R$ {_n(pa, 4)}/m³ nas notas × "
                   f"R$ {_n(pn, 4)}/m³ na NT. Veja valor unitário e alíquota de ICMS das notas.")

    # 2) uma nota (ou um par) que sozinha explica a diferença
    achou = _notas_que_somam(notas, dif, _cgr, TOL_VALOR) if dif > 0 else None
    if achou:
        lista = " + ".join(f"{_rotulo(n)} ({_brl(_cgr(n))})" for n in achou)
        out.append(f"{lista} {'somam' if len(achou) > 1 else 'sozinha explica'} a diferença: está nas notas lidas e não está no CGR da NT.")
    elif dif < 0:
        devs = [n for n in notas if _sinal(n) < 0]
        dobro = [n for n in devs if abs(2 * _cgr(n) - dif) <= TOL_VALOR]
        if dobro:
            n = dobro[0]
            out.append(f"A devolução {n.numero} ({_brl(_cgr(n))}) explica a diferença: as notas a abatem e a NT não (ou a soma na NT).")
        else:
            out.append(f"A NT tem {_brl(-dif)} a mais do que as notas lidas e nenhuma nota ou devolução isolada explica esse valor. "
                       "Possíveis causas: nota deste supridor que não está na pasta, ajuste lançado à mão na NT, ou nota de outro mês.")

    # 3) alíquota de ICMS: a NT bate se todas as notas usassem uma alíquota única?
    taxas = sorted({round(float(n.icms_taxa or 0), 4) for n in notas})
    if len(taxas) > 1:
        cont = ", ".join(f"{t * 100:g}% ({sum(1 for n in notas if round(float(n.icms_taxa or 0), 4) == t)} notas)" for t in taxas)
        out.append(f"As notas têm alíquotas de ICMS diferentes: {cont}.")
    for t in sorted(set(taxas) | {0.07, 0.12, 0.17, 0.18}):
        alt = sum(_sinal(n) * RegrasAuditoria.calcular_s_tributos(n.valor_total, t) for n in notas)
        if abs(alt - cgr_nt) <= TOL_VALOR and abs(dif) > TOL_VALOR:
            out.append(f"A NT bate se todas as notas usassem alíquota de {t * 100:g}% — a NT parece ter calculado com essa alíquota.")
            break

    # 4) leitura por OCR / número ilegível
    ocr = [n for n in notas if n.status == "OCR"]
    sem_num = [n for n in notas if not _normalizar_numero_nota(n.numero).strip("0")]
    if sem_num:
        out.append(f"{len(sem_num)} nota(s) com número ilegível (lido por OCR do PDF): confira os valores dela(s) no arquivo.")
    elif ocr:
        out.append(f"{len(ocr)} nota(s) foram lidas por OCR do PDF (sem XML): o OCR pode errar valores.")
    return out


def _explicar_volume(notas: list[XMLItem], vol_aud: float, vol_nt: float, blocos: dict[str, dict[str, SupridorNT]],
                     periodo: str, canon: str, cgr_bate: bool) -> list[str]:
    """Só o volume diverge (o CGR bate ou não há como comparar CGR)."""
    dvol = vol_aud - vol_nt
    out = [f"Volume diferente: {_n(vol_aud)} m³ nas notas × {_n(vol_nt)} m³ na NT "
           f"({'+' if dvol > 0 else '-'}{_n(abs(dvol))} m³)."]
    if cgr_bate:
        out.append("O CGR em R$ confere com a NT; só o volume (m³) difere. Os valores das notas estão certos: "
                   "o volume lançado na NT é que não acompanha as notas.")
    devs = [n for n in notas if _sinal(n) < 0]
    if devs:
        out.append(f"As notas têm {len(devs)} devolução(ões) que reduzem o volume em {_n(sum(abs(_vol(n)) for n in devs))} m³: "
                   + ", ".join(f"{_rotulo(n)} ({_n(abs(_vol(n)))} m³)" for n in devs) + ". Veja se a NT abate essa devolução do volume.")
    achou = _notas_que_somam(notas, dvol, _vol, TOL_VOLUME) if dvol > 0 else None
    if achou:
        out.append(" + ".join(f"{_rotulo(n)} ({_n(_vol(n))} m³)" for n in achou)
                   + f" {'somam' if len(achou) > 1 else 'sozinha explica'} a diferença de volume.")
    for per, tabela in blocos.items():
        s = tabela.get(canon)
        if per != periodo and s and abs(s.volume - vol_aud) <= max(TOL_VOLUME, 0.001 * vol_aud):
            out.append(f"O volume das notas ({_n(vol_aud)} m³) é igual (ou quase) ao que a NT tem em {per} ({_n(s.volume)} m³): pode ser lançamento "
                       f"de mês trocado na NT ou nota de {per} na pasta de {periodo}.")
            break
    return out


# ── Comparação ───────────────────────────────────────────────────────────────

def comparar(itens: list[XMLItem], modelo: ModeloNT, periodo: str) -> ResultadoComparacaoNotas:
    periodo_norm = normalizar_periodo(periodo)
    if not periodo_norm:
        raise ValueError("Período inválido. Escreva o mês e o ano, por exemplo Jan/2026 ou 01/2026.")

    aud = _agrupar(itens)
    cgr_auditoria = sum(_cgr(n) for notas in aud.values() for n in notas)
    nome_aba = modelo.aba
    avisos: list[str] = []
    bloco = modelo.blocos.get(periodo_norm)

    if bloco is None:
        avisos.append(f"A aba '{nome_aba}' não tem o bloco de {periodo_norm} (blocos: {', '.join(modelo.periodos) or 'nenhum'}). "
                      "Confira o mês selecionado ou use a NT que tem este mês.")
        return ResultadoComparacaoNotas(
            periodo=periodo_norm, coluna_nota_excel="Fornecedor", coluna_periodo_excel=None,
            total_nossa_base=sum(len(v) for v in aud.values()), total_conta_grafica=0, qtd_em_ambas=0,
            notas_apenas_nossa=[], notas_apenas_conta_grafica=[], linhas_sem_numero_excel=[], avisos=avisos,
            sheets_excel=[nome_aba], sheets_periodo_match=[], total_linhas_periodo=0,
            modelo="nt", cgr_auditoria=cgr_auditoria, notas_mes_na_planilha=False,
        )

    linhas: list[dict[str, Any]] = []
    for canon in sorted(set(aud) | set(bloco)):
        notas = aud.get(canon, [])
        s = bloco.get(canon)
        cgr_a = sum(_cgr(n) for n in notas)
        vol_a = sum(_vol(n) for n in notas)
        cgr_n = s.cgr if s else None
        vol_n = s.volume if s else None
        if not notas and (cgr_n or 0) == 0 and (vol_n or 0) == 0:
            continue   # supridor sem movimento nos dois lados (ex.: Cegás, Shell zerados)
        dif_cgr = cgr_a - (cgr_n or 0.0)
        dif_vol = vol_a - (vol_n or 0.0)
        cgr_ok = abs(dif_cgr) <= TOL_VALOR
        vol_ok = vol_n is None and not notas or abs(dif_vol) <= TOL_VOLUME or (vol_n == 0 and vol_a == 0)
        explicacoes: list[str] = []
        if not cgr_ok:
            explicacoes = _explicar_cgr(canon, notas, cgr_a, cgr_n, vol_a, vol_n)
        elif not vol_ok:
            explicacoes = _explicar_volume(notas, vol_a, vol_n or 0.0, modelo.blocos, periodo_norm, canon, cgr_ok)
        linhas.append({
            "empresa": canon, "qtd_auditoria": len(notas), "qtd_planilha": len(notas),
            "cgr_auditoria": round(cgr_a, 2), "cgr_planilha": round(cgr_n or 0.0, 2), "diferenca": round(dif_cgr, 2),
            "volume_auditoria": round(vol_a, 2), "volume_planilha": round(vol_n or 0.0, 2), "diferenca_volume": round(dif_vol, 2),
            "confere": cgr_ok and vol_ok, "explicacoes": explicacoes,
        })
    linhas.sort(key=lambda r: (r["confere"], -abs(r["diferenca"]), -abs(r["diferenca_volume"])))

    cgr_nt = sum(s.cgr for s in bloco.values())
    _aviso_total(avisos, f"aba '{nome_aba}'", cgr_auditoria, cgr_nt)
    n_div = sum(1 for r in linhas if not r["confere"])
    if n_div:
        avisos.append(f"{n_div} supridor(es) com diferença — veja o porquê de cada um em “Mostrar diferenças”.")

    return ResultadoComparacaoNotas(
        periodo=periodo_norm, coluna_nota_excel="Fornecedor", coluna_periodo_excel=None,
        total_nossa_base=sum(len(v) for v in aud.values()), total_conta_grafica=len(bloco), qtd_em_ambas=0,
        notas_apenas_nossa=[], notas_apenas_conta_grafica=[], linhas_sem_numero_excel=[], avisos=avisos,
        sheets_excel=[nome_aba], sheets_periodo_match=[f"{nome_aba} ({periodo_norm})"], total_linhas_periodo=len(bloco),
        modelo="nt", por_empresa=linhas, cgr_auditoria=cgr_auditoria, cgr_planilha_notas=cgr_nt,
        notas_mes_na_planilha=False,
    )
