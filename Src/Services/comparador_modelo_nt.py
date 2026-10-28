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
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from Src.common.periodos import normalizar_periodo
from Src.Services import explicador_diferencas as exp
from Src.Services.comparador_conta_grafica import ResultadoComparacaoNotas
from Src.Services.servicos_auditoria import XMLItem
from Src.Services.supridores import supridor_canonico, token as _token

ABA_SCG = "q5scg"        # início do nome da aba, sem acento/símbolos ("Q5 - SCG - Anexo A")
FONTE = "NT"             # como a planilha é chamada nas explicações

_PERIODO_RE = re.compile(r"^\s*(\d{2})/(\d{4})\s*$")


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


# ── Comparação ───────────────────────────────────────────────────────────────

def comparar(itens: list[XMLItem], modelo: ModeloNT, periodo: str) -> ResultadoComparacaoNotas:
    periodo_norm = normalizar_periodo(periodo)
    if not periodo_norm:
        raise ValueError("Período inválido. Escreva o mês e o ano, por exemplo Jan/2026 ou 01/2026.")

    aud = exp.agrupar_por_supridor(itens)
    cgr_auditoria = sum(exp.cgr_nota(x) for notas in aud.values() for x in notas)
    nome_aba = modelo.aba
    avisos: list[str] = []
    bloco = modelo.blocos.get(periodo_norm)
    comum = dict(
        periodo=periodo_norm, coluna_nota_excel="Fornecedor", coluna_periodo_excel=None,
        total_nossa_base=sum(len(v) for v in aud.values()), notas_apenas_nossa=[], notas_apenas_conta_grafica=[],
        linhas_sem_numero_excel=[], sheets_excel=[nome_aba], modelo="nt", cgr_auditoria=cgr_auditoria,
        notas_mes_na_planilha=False,
    )

    if bloco is None:
        avisos.append(f"A aba '{nome_aba}' não tem o bloco de {periodo_norm} (blocos: {', '.join(modelo.periodos) or 'nenhum'}). "
                      "Confira o mês selecionado ou use a NT que tem este mês.")
        return ResultadoComparacaoNotas(**comum, total_conta_grafica=0, qtd_em_ambas=0, avisos=avisos,
                                        sheets_periodo_match=[], total_linhas_periodo=0)

    linhas: list[dict[str, Any]] = []
    for canon in sorted(set(aud) | set(bloco)):
        notas = aud.get(canon, [])
        s = bloco.get(canon)
        cgr_a = sum(exp.cgr_nota(x) for x in notas)
        vol_a = sum(exp.vol_nota(x) for x in notas)
        cgr_n = s.cgr if s else None
        vol_n = s.volume if s else None
        if not notas and (cgr_n or 0) == 0 and (vol_n or 0) == 0:
            continue   # supridor sem movimento nos dois lados (ex.: Cegás, Shell zerados)
        dif_cgr = cgr_a - (cgr_n or 0.0)
        dif_vol = vol_a - (vol_n or 0.0)
        cgr_ok = abs(dif_cgr) <= exp.TOL_VALOR
        vol_ok = abs(dif_vol) <= exp.TOL_VOLUME
        explicacoes: list[str] = []
        if not cgr_ok:
            explicacoes = exp.explicar_cgr(canon, notas, cgr_a, cgr_n, vol_a, vol_n, FONTE)
        elif not vol_ok:
            outros = {per: t[canon].volume for per, t in modelo.blocos.items() if canon in t}
            explicacoes = exp.explicar_volume(notas, vol_a, vol_n or 0.0, cgr_ok, FONTE, outros, periodo_norm)
        linhas.append({
            "empresa": canon, "qtd_auditoria": len(notas), "qtd_planilha": len(notas),
            "cgr_auditoria": round(cgr_a, 2), "cgr_planilha": round(cgr_n or 0.0, 2), "diferenca": round(dif_cgr, 2),
            "volume_auditoria": round(vol_a, 2), "volume_planilha": round(vol_n or 0.0, 2), "diferenca_volume": round(dif_vol, 2),
            "confere": cgr_ok and vol_ok, "explicacoes": explicacoes,
        })
    linhas.sort(key=lambda r: (r["confere"], -abs(r["diferenca"]), -abs(r["diferenca_volume"])))

    cgr_nt = sum(s.cgr for s in bloco.values())
    exp.aviso_total(avisos, f"aba '{nome_aba}'", cgr_auditoria, cgr_nt)
    n_div = sum(1 for r in linhas if not r["confere"])
    if n_div:
        avisos.append(f"{n_div} supridor(es) com diferença — veja o porquê de cada um em “Mostrar diferenças”.")

    return ResultadoComparacaoNotas(
        **comum, total_conta_grafica=len(bloco), qtd_em_ambas=0, avisos=avisos,
        sheets_periodo_match=[f"{nome_aba} ({periodo_norm})"], total_linhas_periodo=len(bloco),
        por_empresa=linhas, cgr_planilha_notas=cgr_nt,
        fontes_cgr=[{"rotulo": "NT (soma dos supridores)", "valor": cgr_nt}],
    )
