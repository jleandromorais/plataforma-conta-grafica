import logging

import pandas as pd

from Src.common.periodos import _MESES, _EN_TO_PT, en_para_pt, normalizar_periodo

logger = logging.getLogger(__name__)

# Extensão do mapa PT com variantes EN e acentos ausentes em _MESES
_MAPA_MES = {
    **{k: v.lower() for k, v in _MESES.items()},
    "feb": "fev", "apr": "abr", "may": "mai",
    "aug": "ago", "sep": "set", "oct": "out", "dec": "dez",
    "março": "mar",
}


def _abrev_ano_curto(mes_raw: str, ano_raw: str) -> str:
    """Retorna 'mes_norm/aa' com ano de 2 dígitos a partir de strings brutas."""
    mes_norm = _MAPA_MES.get(mes_raw, mes_raw[:3])
    ano = "".join(c for c in ano_raw if c.isdigit())
    if len(ano) >= 4:
        ano = ano[-2:]
    return f"{mes_norm}/{ano}" if ano else mes_norm


# ==========================================
# 1. SERVIÇO DE EXCEL (O "Fornecedor")
# ==========================================
class ExcelPMPV:
    """Lê e interpreta dados de ficheiros Excel usando pandas."""

    @staticmethod
    def _normalizar_mes(texto: str) -> str:
        if texto is None:
            return ""

        txt = str(texto).strip().lower()
        txt = txt.replace(".", "").replace("-", "/")
        txt = " ".join(txt.split())

        if "/" in txt:
            partes = [p.strip() for p in txt.split("/") if p.strip()]
            if len(partes) >= 2:
                return _abrev_ano_curto(partes[0], partes[1])

        if " " in txt:
            partes = [p for p in txt.split(" ") if p]
            if len(partes) >= 2:
                return _abrev_ano_curto(partes[0], partes[1])

        return _MAPA_MES.get(txt, txt[:3])
    
    @staticmethod
    def ler_aba(caminho_arquivo) -> pd.DataFrame:
        """Aba de dados da Memória de Cálculo (PMPV / Custo médio ponderado / 1ª)."""
        _ABAS_CANDIDATAS = ["PMPV", "Custo médio ponderado", "Custo medio ponderado"]
        try:
            # `with` fecha a planilha ao terminar — sem isso o arquivo ficava
            # travado (não dava para apagar/mover) enquanto o app estivesse aberto.
            with pd.ExcelFile(caminho_arquivo) as xl_tmp:
                aba = next((a for a in _ABAS_CANDIDATAS if a in xl_tmp.sheet_names), xl_tmp.sheet_names[0])
                return pd.read_excel(xl_tmp, sheet_name=aba, header=None)
        except Exception:
            # O texto da exceção (zip, openpyxl...) não ajuda o usuário: fica só no log.
            logger.exception("Falha ao abrir a Memória de Cálculo")
            raise ValueError(
                "Não consegui abrir a planilha. Confira se é a Memória de Cálculo em Excel "
                "(.xlsx/.xls), sem senha e sem estar corrompida."
            ) from None

    @staticmethod
    def colunas_de_meses(df: pd.DataFrame) -> dict[int, str]:
        """{coluna: 'Fev/26'} da 1ª linha com datas (nas 15 primeiras).

        Datas fora de 2000–2099 (ex.: célula vazia que o Excel lê como 1900) são
        ignoradas: com ano de 2 dígitos virariam um mês errado."""
        for ri in range(min(15, len(df))):
            linha = [
                (ci, df.iloc[ri, ci]) for ci in range(2, len(df.columns))
                if pd.notna(df.iloc[ri, ci]) and hasattr(df.iloc[ri, ci], "strftime")
                and 2000 <= df.iloc[ri, ci].year <= 2099
            ]
            if linha:
                return {ci: en_para_pt(cel.strftime("%b")) + "/" + cel.strftime("%y") for ci, cel in linha}
        raise ValueError(
            "Não achei a linha de meses (datas) nas 15 primeiras linhas da aba de dados. "
            "Confira se o arquivo é a Memória de Cálculo."
        )

    @staticmethod
    def coluna_do_mes(meses_cols: dict[int, str], mes_escolhido) -> int | None:
        """Coluna do mês pedido ('Fev/2026', 'fev-26', 'Fev'...), ou None."""
        mes_input_norm = ExcelPMPV._normalizar_mes(mes_escolhido)
        return next(
            (
                ci
                for ci, lbl in meses_cols.items()
                if ExcelPMPV._normalizar_mes(lbl) == mes_input_norm
                or mes_input_norm in ExcelPMPV._normalizar_mes(lbl)
            ),
            None,
        )

    @staticmethod
    def rotulos(meses_cols: dict[int, str]) -> list[str]:
        """Meses da planilha no formato do sistema, ex.: ['Fev/2026', 'Mar/2026']."""
        return [normalizar_periodo(m) for m in meses_cols.values()]

    @staticmethod
    def ler_dados_memoria_calculo(caminho_arquivo, mes_escolhido, df: pd.DataFrame | None = None):
        """Empresas do mês. `df` (já lido com `ler_aba`) evita abrir a planilha de novo."""
        if df is None:
            df = ExcelPMPV.ler_aba(caminho_arquivo)
        meses_cols = ExcelPMPV.colunas_de_meses(df)
        col_dados = ExcelPMPV.coluna_do_mes(meses_cols, mes_escolhido)

        if col_dados is None:
            raise ValueError(
                f"{mes_escolhido} não está na planilha (ela tem {', '.join(ExcelPMPV.rotulos(meses_cols))})."
            )

        first_month_col = min(meses_cols.keys())
        empresas = {}
        empresa_atual = None
        _CAMPOS = {"A": "mol", "B": "trans", "C": "log", "E": "volume"}

        for ri in range(len(df)):
            col1 = df.iloc[ri, 1]
            col2 = df.iloc[ri, 2]
            first_m_cell = df.iloc[ri, first_month_col]

            col1_str = str(col1).strip() if pd.notna(col1) else ""
            col2_str = str(col2).strip() if pd.notna(col2) else ""
            is_date = pd.notna(first_m_cell) and hasattr(first_m_cell, "strftime")

            if (not col1_str or col1_str == "nan") and col2_str and col2_str != "nan" and is_date:
                empresa_atual = col2_str
                empresas.setdefault(empresa_atual, {"mol": 0.0, "trans": 0.0, "log": 0.0, "volume": 0.0})
                continue

            if empresa_atual is None or col1_str not in _CAMPOS: continue

            val_raw = df.iloc[ri, col_dados]
            try:
                val = float(val_raw) if pd.notna(val_raw) and str(val_raw).strip() not in ("", "nan") else 0.0
            except (TypeError, ValueError):
                raise ValueError(
                    f"a empresa {empresa_atual}, linha {col1_str}, tem '{val_raw}' "
                    "no lugar de um número. Corrija a célula na planilha e importe de novo."
                ) from None

            if col1_str == "C" and not val: continue
            empresas[empresa_atual][_CAMPOS[col1_str]] = val

        return {k: v for k, v in empresas.items() if v["volume"] > 0}


# ==========================================
# 2. LÓGICA DE NEGÓCIO (O "Cozinheiro")
# ==========================================
class RegrasPMPV:
    """Faz a matemática do sistema."""
    
    @staticmethod
    def calcular_resultados(dados_extraidos, valor_cg, dias_config, lista_meses, idx_start):
        c_tot = 0.0
        v_tot_vf = 0.0
        v_tot_calculo = 0.0   # volume "de cálculo" = Σ(volume × dias do mês)
        vp_total = 0.0
        vf_total = 0.0
        vp_por_mes = {} 
        vf_por_mes = {}
        vf_calculo_por_mes = {}
        avisos = []

        for i, (k, linhas) in enumerate(dados_extraidos.items()):
            dias = dias_config.get(k, 30)
            mes_nome = lista_meses[(idx_start + i) % 12]
            vp_mes = 0.0
            vf_mes = 0.0
            vf_calculo_mes = 0.0

            for l in linhas:
                vol = l['volume']
                if vol <= 0: continue

                pr = l['molecula'] + l['transporte'] + l['logistica']
                vf_calculo = vol * dias

                c_tot += pr * vol
                v_tot_vf += vol
                v_tot_calculo += vf_calculo
                vf_calculo_mes += vf_calculo
                vf_mes += vol
                vf_total += vol
                
                vp_mes += vol
                vp_total += vol

                campos_vazios = l['campos_vazios']
                if campos_vazios:
                    empresa = l['empresa'] or "(sem nome)"
                    avisos.append(f"  • {mes_nome} | {empresa}: {', '.join(campos_vazios)} → 0")

            if vp_mes > 0:
                vp_por_mes[mes_nome] = vp_mes
                vf_por_mes[mes_nome] = vf_mes
                vf_calculo_por_mes[mes_nome] = vf_calculo_mes

        if v_tot_vf == 0:
            raise ValueError("Volume Zero: nenhuma empresa tem volume preenchido neste mês da planilha. "
                             "Confira se escolheu o mês certo e se a Memória de Cálculo está completa.")

        pmpv = c_tot / v_tot_vf
        final = pmpv + valor_cg

        return {
            'volume_total': v_tot_calculo, 'custo_total': c_tot,
            'pmpv': pmpv, 'conta_grafica': valor_cg, 'preco_final': final,
            'vp_mensal': vp_total, 'vp_por_mes': vp_por_mes,
            'vf_total': vf_total,
            'vf_por_mes': vf_por_mes,
            'volume_total_calculo': v_tot_calculo,
            'vf_calculo_por_mes': vf_calculo_por_mes,
            'avisos': avisos
        }


TOL_PROVA_REAL_PMPV = 0.0001   # R$/m³: o PMPV é gravado com 4 casas
TOL_PROVA_REAL_RS = 1.0        # R$: custo total
TOL_PROVA_REAL_M3 = 1.0        # m³: volume prospectivo


def prova_real_sessao(sessao_id: int) -> dict:
    """A conta do PMPV de uma sessão salva, refeita com as linhas gravadas e comparada
    com o resultado gravado. Não grava nada.

    PMPV = Σ(preço × volume) ÷ Σ volume, com preço = molécula + transporte + logística de
    cada empresa (mesma regra de `RegrasPMPV.calcular_resultados`; os dias do mês só entram
    no "volume de cálculo", não no PMPV). Preço final = PMPV + Conta Gráfica (a gravada).
    Linhas com volume ≤ 0 não entram, como no cálculo.
    """
    from Src.Database.database import DatabasePMPV

    with DatabasePMPV() as db:
        sessao = next((x for x in db.listar_historico_pmpv() if x["id"] == sessao_id), None)
        if sessao is None:
            raise LookupError(f"Não encontrei a sessão {sessao_id} do PMPV.")
        res = db.buscar_resultado_sessao(sessao_id) or {}
        por_mes = {m: db.carregar_dados_mes(sessao_id, m) for m in (1, 2, 3)}

    custo_total = volume_total = 0.0
    meses = []
    for mes, linhas in por_mes.items():
        empresas, custo_mes, volume_mes = [], 0.0, 0.0
        for l in linhas:
            vol = float(l.get("volume") or 0.0)
            if vol <= 0:
                continue
            preco = float(l.get("molecula") or 0.0) + float(l.get("transporte") or 0.0) + float(l.get("logistica") or 0.0)
            empresas.append({"empresa": l.get("empresa") or "(sem nome)", "molecula": float(l.get("molecula") or 0.0),
                             "transporte": float(l.get("transporte") or 0.0), "logistica": float(l.get("logistica") or 0.0),
                             "preco": preco, "volume": vol, "custo": preco * vol})
            custo_mes += preco * vol
            volume_mes += vol
        if empresas:
            meses.append({"mes": mes, "empresas": empresas, "volume": volume_mes, "custo": custo_mes,
                          "pmpv_do_mes": custo_mes / volume_mes})
        custo_total += custo_mes
        volume_total += volume_mes

    tem_linhas = volume_total > 0
    tem_resultado = bool(res)
    pmpv_calc = custo_total / volume_total if tem_linhas else None
    pmpv_grav = float(res["pmpv_trimestral"]) if tem_resultado and res.get("pmpv_trimestral") is not None else None
    cg = float(res["conta_grafica"]) if tem_resultado and res.get("conta_grafica") is not None else None
    final_calc = pmpv_calc + cg if pmpv_calc is not None and cg is not None else None
    final_grav = float(res["preco_final"]) if tem_resultado and res.get("preco_final") is not None else None
    custo_grav = float(res["custo_total"]) if tem_resultado and res.get("custo_total") is not None else None
    vp_grav = float(res["vp_total"]) if tem_resultado and res.get("vp_total") is not None else None

    def dif(a, b):
        return a - b if a is not None and b is not None else None

    def ok(d, tol):
        return d is not None and abs(d) <= tol

    d_pmpv, d_final = dif(pmpv_calc, pmpv_grav), dif(final_calc, final_grav)
    d_custo, d_vp = dif(custo_total if tem_linhas else None, custo_grav), dif(volume_total if tem_linhas else None, vp_grav)
    return {
        "sessao_id": sessao_id,
        "nome": sessao["nome"],
        "data_criacao": sessao.get("data_criacao"),
        "tem_linhas": tem_linhas,
        "tem_resultado": tem_resultado,
        "meses": meses,
        "custo_total_calculado": custo_total if tem_linhas else None,
        "custo_total_gravado": custo_grav,
        "diferenca_custo": d_custo,
        "volume_total": volume_total if tem_linhas else None,
        "vp_gravado": vp_grav,
        "diferenca_vp": d_vp,
        "pmpv_calculado": pmpv_calc,
        "pmpv_gravado": pmpv_grav,
        "diferenca_pmpv": d_pmpv,
        "conta_grafica": cg,
        "preco_final_calculado": final_calc,
        "preco_final_gravado": final_grav,
        "diferenca_preco_final": d_final,
        "confere": ok(d_pmpv, TOL_PROVA_REAL_PMPV) and ok(d_final, TOL_PROVA_REAL_PMPV)
                   and ok(d_custo, TOL_PROVA_REAL_RS) and ok(d_vp, TOL_PROVA_REAL_M3),
    }
