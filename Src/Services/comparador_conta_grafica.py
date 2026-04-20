from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import re
import unicodedata
from typing import Any

import pandas as pd

from Src.common.periodos import normalizar_periodo, variantes_periodo, _ABREV_TO_FULL
from Src.Services.servicos_auditoria import XMLItem, RegrasAuditoria


def _token(texto: str) -> str:
    limpo = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", limpo.lower())


def _tokens_periodo(periodo_norm: str) -> set[str]:
    partes = periodo_norm.split("/")
    if len(partes) != 2:
        return {periodo_norm.lower()}
    mes, ano = partes
    mes_low = mes.lower()
    ano2 = ano[-2:]
    tokens = {
        f"{mes_low}/{ano}",
        f"{mes_low}/{ano2}",
        f"{mes_low}{ano2}",
        f"{mes_low}-{ano2}",
        f"{mes_low}_{ano2}",
        f"{mes_low}.{ano2}",
    }
    # Adiciona variantes com nome completo do mês (ex: "janeiro26", "janeiro/2026")
    nome_completo = _ABREV_TO_FULL.get(mes_low)
    if nome_completo:
        tokens.update({
            f"{nome_completo}{ano2}",
            f"{nome_completo}{ano}",
            f"{nome_completo}/{ano2}",
            f"{nome_completo}/{ano}",
            f"{nome_completo}-{ano2}",
        })
    return tokens


def _sheet_corresponde_periodo(sheet_name: Any, periodo_norm: str) -> bool:
    if sheet_name is None or pd.isna(sheet_name):
        return False
    bruto = str(sheet_name).strip()
    if not bruto:
        return False
    # Normaliza: remove acentos, minúsculas, remove espaços
    sem_acento = unicodedata.normalize("NFKD", bruto).encode("ascii", "ignore").decode("ascii").lower()
    canon = re.sub(r"\s+", "", sem_acento)
    return any(tok in canon for tok in _tokens_periodo(periodo_norm))


def _normalizar_numero_nota(valor: Any) -> str:
    if pd.isna(valor):
        return ""
    # Float sem parte fracionária (ex: 123456.0 lido pelo pandas) → converte para int
    # para evitar que "123456.0" vire "1234560" ao remover não-dígitos
    if isinstance(valor, float):
        int_val = int(valor)
        if float(int_val) == valor:
            valor = int_val
    txt = str(valor).strip()
    if not txt or txt.lower() in {"nan", "none", "n/a", "na", "-"}:
        return ""
    # Remove sufixo ".0" residual (ex: string "123456.0")
    if re.fullmatch(r"\d+\.0", txt):
        txt = txt[:-2]

    # Trata formatos comuns de planilha com série ao final:
    # 132893-55, 000001227-2, 7861/24 -> mantém apenas o número base.
    m_numero_serie = re.fullmatch(r"\s*0*(\d{3,})\s*[-/]\s*\d{1,3}\s*", txt)
    if m_numero_serie:
        base = m_numero_serie.group(1).lstrip("0")
        return base or "0"

    digitos = re.sub(r"\D", "", txt)
    if digitos:
        sem_zero = digitos.lstrip("0")
        return sem_zero or "0"

    alnum = re.sub(r"[^A-Z0-9]", "", txt.upper())
    return alnum


def _periodo_de_data(valor: Any) -> str:
    if pd.isna(valor):
        return ""

    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return normalizar_periodo(f"{int(valor.month):02d}/{valor.year}")

    if isinstance(valor, (int, float)):
        dt = pd.to_datetime(valor, errors="coerce", unit="D", origin="1899-12-30")
        if pd.notna(dt):
            return normalizar_periodo(f"{int(dt.month):02d}/{int(dt.year)}")

    texto = str(valor).strip()
    if not texto:
        return ""

    normalizado = normalizar_periodo(texto)
    if re.fullmatch(r"[A-Za-z]{3}/\d{4}", normalizado):
        return normalizado

    dt = pd.to_datetime(texto, errors="coerce", dayfirst=True)
    if pd.notna(dt):
        return normalizar_periodo(f"{int(dt.month):02d}/{int(dt.year)}")

    return ""


def _escolher_coluna_nota(df: pd.DataFrame, notas_referencia: set[str] | None = None) -> str:
    melhor_coluna = ""
    melhor_pontuacao = -1.0
    melhor_matches = -1

    for col in df.columns:
        if str(col).startswith("__"):
            continue
        nome = _token(col)
        score = 0.0
        if "nota" in nome:
            score += 5
        if "numero" in nome or re.search(r"(^|_)num($|_)", nome):
            score += 4
        if "nf" in nome or "nfe" in nome:
            score += 4
        if "cte" in nome:
            score += 3
        if "doc" in nome or "documento" in nome:
            score += 2
        if "fiscal" in nome or "fisc" in nome:
            score += 2
        if "chave" in nome:
            score += 2
        if "item" in nome or "serie" in nome:
            score -= 2

        amostra = df[col].head(500)
        normalizados = amostra.apply(_normalizar_numero_nota).astype(str)
        validos = normalizados.str.len().gt(0)
        digitos = normalizados.str.fullmatch(r"\d+")
        digitos_longos = digitos & normalizados.str.len().ge(4)
        qualidade = float(validos.mean()) if len(validos) else 0.0
        qualidade_numerica = float(digitos_longos.mean()) if len(digitos_longos) else 0.0
        qtd_validos = int(validos.sum())
        qtd_unicos = len({n for n in normalizados[validos].tolist() if n})
        diversidade = (qtd_unicos / qtd_validos) if qtd_validos else 0.0
        score += qualidade * 1.5
        score += qualidade_numerica * 10
        score += diversidade * 8

        matches = 0
        if notas_referencia:
            unicos = {n for n in normalizados.tolist() if n}
            matches = len(unicos & notas_referencia)
            total_unicos = len(unicos) or 1
            score += (matches * 20) + ((matches / total_unicos) * 24)

        # Sem nenhuma pista no nome e sem match real, a coluna tende a ser ruído.
        if score <= 0 and matches == 0:
            continue

        # Evita selecionar colunas praticamente vazias (comuns após concat de abas heterogêneas).
        if qualidade < 0.03 and matches == 0:
            continue

        # Colunas numéricas com baixíssima diversidade tendem a ser mês/série/índice, não número de NF.
        if diversidade < 0.05 and matches == 0:
            continue

        if (matches > melhor_matches) or (matches == melhor_matches and score > melhor_pontuacao):
            melhor_matches = matches
            melhor_pontuacao = score
            melhor_coluna = str(col)

    if not melhor_coluna:
        # Fallback final: tenta inferir pela densidade de números por coluna
        melhor_ratio = 0.0
        for col in df.columns:
            if str(col).startswith("__"):
                continue
            amostra = df[col].head(800)
            norm = amostra.apply(_normalizar_numero_nota).astype(str)
            digitos_longos = norm.str.fullmatch(r"\d+") & norm.str.len().ge(4)
            validos = norm.str.len().gt(0)
            qtd_validos = int(validos.sum())
            qtd_unicos = len({n for n in norm[validos].tolist() if n})
            diversidade = (qtd_unicos / qtd_validos) if qtd_validos else 0.0
            ratio = (float(digitos_longos.mean()) * 0.6 + diversidade * 0.4) if len(norm) else 0.0
            if ratio > melhor_ratio and ratio > 0:
                melhor_ratio = ratio
                melhor_coluna = str(col)

    if not melhor_coluna:
        raise ValueError(
            "Não foi possível identificar a coluna de número da nota fiscal na planilha selecionada."
        )
    return melhor_coluna


def _escolher_coluna_periodo(df: pd.DataFrame) -> str | None:
    candidatas: list[tuple[float, str]] = []
    for col in df.columns:
        if str(col).startswith("__"):
            continue
        nome = _token(col)
        score = 0.0
        if "periodo" in nome:
            score += 5
        if "competencia" in nome:
            score += 5
        if "mes" in nome:
            score += 4
        if "referencia" in nome or "ref" in nome:
            score += 2
        if "data" in nome:
            score += 1
        if score > 0:
            # Reforça somente colunas que realmente contenham períodos parseáveis.
            amostra = df[col].head(800)
            periodos = amostra.apply(_periodo_de_data).astype(str)
            taxa_valida = float(periodos.str.len().gt(0).mean()) if len(periodos) else 0.0
            if taxa_valida < 0.05:
                continue
            score += taxa_valida * 6
            candidatas.append((score, str(col)))

    if not candidatas:
        return None

    candidatas.sort(key=lambda x: x[0], reverse=True)
    return candidatas[0][1]


@dataclass
class ResultadoComparacaoNotas:
    periodo: str
    coluna_nota_excel: str
    coluna_periodo_excel: str | None
    total_nossa_base: int
    total_conta_grafica: int
    qtd_em_ambas: int
    notas_apenas_nossa: list[dict[str, Any]]
    notas_apenas_conta_grafica: list[dict[str, Any]]
    linhas_sem_numero_excel: list[dict[str, Any]]
    avisos: list[str]
    sheets_excel: list[str]           # todas as abas na planilha carregada
    sheets_periodo_match: list[str]   # abas que corresponderam ao período
    total_linhas_periodo: int         # linhas encontradas para o período


class ComparadorContaGrafica:
    @staticmethod
    def comparar(
        resultados: list[XMLItem],
        df_excel: pd.DataFrame,
        periodo: str,
    ) -> ResultadoComparacaoNotas:
        if not isinstance(df_excel, pd.DataFrame) or df_excel.empty:
            raise ValueError("A planilha de Conta Gráfica está vazia ou inválida.")

        periodo_norm = normalizar_periodo(periodo)
        if not periodo_norm:
            raise ValueError("Período inválido. Use formato como Jan/2026 ou 01/2026.")

        nossa_por_nota: dict[str, dict[str, Any]] = {}
        for item in resultados:
            nota_norm = _normalizar_numero_nota(item.numero)
            if not nota_norm:
                continue
            if nota_norm in nossa_por_nota:
                continue
            nossa_por_nota[nota_norm] = {
                "empresa": item.empresa,
                "tipo": item.tipo,
                "numero": item.numero,
                "numero_normalizado": nota_norm,
                "valor_total": float(item.valor_total),
                "icms": float(item.icms),
                "cgr_liquido": float(RegrasAuditoria.calcular_s_tributos(item.valor_total, item.icms_taxa)),
            }

        notas_referencia = set(nossa_por_nota.keys())
        if not notas_referencia:
            raise ValueError("A auditoria não retornou números de nota válidos para comparação.")

        usar_sheet_periodo = "__sheet_name__" in df_excel.columns

        # ── Diagnóstico de abas ──────────────────────────────────────────────
        sheets_excel: list[str] = []
        sheets_periodo_match: list[str] = []
        if usar_sheet_periodo:
            sheets_excel = sorted(
                {str(n) for n in df_excel["__sheet_name__"].tolist() if n is not None and str(n) != "nan"}
            )
            sheets_periodo_match = [s for s in sheets_excel if _sheet_corresponde_periodo(s, periodo_norm)]

        mask_sheet_periodo = (
            df_excel["__sheet_name__"].apply(lambda n: _sheet_corresponde_periodo(n, periodo_norm))
            if usar_sheet_periodo
            else pd.Series(False, index=df_excel.index)
        )
        qtd_linhas_sheet = int(mask_sheet_periodo.sum()) if usar_sheet_periodo else 0

        df_candidata = df_excel.loc[mask_sheet_periodo].copy() if qtd_linhas_sheet > 0 else df_excel

        col_nota = _escolher_coluna_nota(df_candidata, notas_referencia=notas_referencia)
        col_periodo = _escolher_coluna_periodo(df_candidata)
        conjunto_variantes = set(variantes_periodo(periodo_norm)) or {periodo_norm}

        avisos: list[str] = []

        # Aviso principal: aba não encontrada
        if usar_sheet_periodo and not sheets_periodo_match:
            lista_abas = ", ".join(sheets_excel[:15])
            sufixo = " (...)" if len(sheets_excel) > 15 else ""
            avisos.append(
                f"ATENÇÃO: Nenhuma aba correspondeu ao período '{periodo_norm}'. "
                f"Abas encontradas na planilha: {lista_abas}{sufixo}. "
                f"Verifique se o arquivo selecionado contém dados de '{periodo_norm}'."
            )
        elif not col_periodo and qtd_linhas_sheet == 0:
            avisos.append(
                "A planilha não possui coluna de período identificável e nenhuma aba correspondeu ao período. Comparação usou todas as linhas."
            )
        elif not col_periodo and qtd_linhas_sheet > 0:
            avisos.append(
                f"Período filtrado pelo nome da aba '{sheets_periodo_match[0]}'. Coluna de competência não identificada."
            )
        elif col_periodo and qtd_linhas_sheet > 0:
            avisos.append(
                f"Período filtrado pela aba '{sheets_periodo_match[0]}' + coluna '{col_periodo}'."
            )

        conta_por_nota: dict[str, dict[str, Any]] = {}
        linhas_sem_numero: list[dict[str, Any]] = []
        total_linhas_periodo = 0

        for idx, row in df_candidata.iterrows():
            valor_periodo = row.get(col_periodo) if col_periodo else None
            periodo_linha = _periodo_de_data(valor_periodo) if col_periodo else ""

            if col_periodo:
                if periodo_linha and periodo_linha not in conjunto_variantes:
                    continue
                if not periodo_linha and qtd_linhas_sheet == 0:
                    continue

            total_linhas_periodo += 1
            valor_nota = row.get(col_nota)
            nota_norm = _normalizar_numero_nota(valor_nota)
            if not nota_norm:
                linhas_sem_numero.append(
                    {
                        "linha_excel": int(idx) + 2,
                        "coluna_nota": col_nota,
                        "valor_original": "" if pd.isna(valor_nota) else str(valor_nota),
                    }
                )
                continue

            if nota_norm in conta_por_nota:
                continue

            # Captura dados completos da linha para exibição na aba "Diferenças"
            dados_linha: dict[str, Any] = {}
            for col_name, val in row.items():
                if str(col_name).startswith("__"):
                    continue
                dados_linha[str(col_name)] = None if (isinstance(val, float) and pd.isna(val)) else val

            conta_por_nota[nota_norm] = {
                "linha_excel": int(idx) + 2,
                "numero": "" if pd.isna(valor_nota) else str(valor_nota),
                "numero_normalizado": nota_norm,
                "periodo_linha": periodo_linha or ("via_aba" if qtd_linhas_sheet > 0 else ""),
                "dados_linha": dados_linha,
            }

        notas_nossa = set(nossa_por_nota.keys())
        notas_conta = set(conta_por_nota.keys())

        em_ambas = notas_nossa & notas_conta
        apenas_nossa = sorted(notas_nossa - notas_conta)
        apenas_conta = sorted(notas_conta - notas_nossa)

        # Diagnóstico: quando período selecionado não cruza nada, tenta indicar a aba
        # mais provável com base no número da nota fiscal.
        if usar_sheet_periodo and notas_nossa and not em_ambas and col_nota in df_excel.columns:
            ranking_abas: list[tuple[int, int, str]] = []
            for nome_aba, grupo in df_excel.groupby("__sheet_name__", dropna=True):
                serie_notas = grupo[col_nota]
                notas_aba = {
                    _normalizar_numero_nota(v)
                    for v in serie_notas.tolist()
                }
                notas_aba = {n for n in notas_aba if n}
                if not notas_aba:
                    continue
                qtd_match = len(notas_aba & notas_nossa)
                ranking_abas.append((qtd_match, len(notas_aba), str(nome_aba)))

            ranking_abas.sort(key=lambda x: (x[0], x[1]), reverse=True)
            if ranking_abas:
                melhor_match, total_notas_aba, melhor_aba = ranking_abas[0]
                if melhor_match > 0 and melhor_aba not in sheets_periodo_match:
                    avisos.append(
                        f"Dica: maior interseção por número de nota foi na aba '{melhor_aba}' "
                        f"({melhor_match} nota(s) em comum de {total_notas_aba} na aba). "
                        "Revise o período informado para comparar com a competência correta."
                    )

        if not notas_conta and not sheets_periodo_match:
            avisos.append(
                "Resultado: nenhuma nota da planilha foi carregada para o período. "
                "Provavelmente o arquivo selecionado não tem dados deste mês/ano."
            )
        elif not notas_conta:
            avisos.append(
                "Nenhuma nota válida encontrada na planilha para o período. Verifique a coluna de número de nota."
            )
        elif notas_nossa and not em_ambas:
            avisos.append(
                "Notas foram encontradas na planilha mas nenhuma coincidiu com a auditoria. "
                "Verifique se as notas do período correto estão no arquivo."
            )

        return ResultadoComparacaoNotas(
            periodo=periodo_norm,
            coluna_nota_excel=col_nota,
            coluna_periodo_excel=col_periodo,
            total_nossa_base=len(notas_nossa),
            total_conta_grafica=len(notas_conta),
            qtd_em_ambas=len(em_ambas),
            notas_apenas_nossa=[nossa_por_nota[n] for n in apenas_nossa],
            notas_apenas_conta_grafica=[conta_por_nota[n] for n in apenas_conta],
            linhas_sem_numero_excel=linhas_sem_numero,
            avisos=avisos,
            sheets_excel=sheets_excel,
            sheets_periodo_match=sheets_periodo_match,
            total_linhas_periodo=total_linhas_periodo,
        )