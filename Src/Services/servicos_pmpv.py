import pandas as pd

from Src.common.periodos import _MESES, _EN_TO_PT

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
    def ler_dados_memoria_calculo(caminho_arquivo, mes_escolhido):
        _ABAS_CANDIDATAS = ["PMPV", "Custo médio ponderado", "Custo medio ponderado"]
        df = None
        
        try:
            xl_tmp = pd.ExcelFile(caminho_arquivo)
            for candidata in _ABAS_CANDIDATAS:
                if candidata in xl_tmp.sheet_names:
                    df = pd.read_excel(xl_tmp, sheet_name=candidata, header=None)
                    break
            if df is None:
                df = pd.read_excel(xl_tmp, sheet_name=xl_tmp.sheet_names[0], header=None)
        except Exception as exc:
            raise ValueError(f"Não foi possível ler o arquivo:\n{exc}")

        meses_cols = {}
        first_header_row = None

        for ri in range(min(15, len(df))):
            for ci in range(2, len(df.columns)):
                cell = df.iloc[ri, ci]
                if pd.notna(cell) and hasattr(cell, "strftime"):
                    first_header_row = ri
                    for ci2 in range(2, len(df.columns)):
                        c2 = df.iloc[ri, ci2]
                        if pd.notna(c2) and hasattr(c2, "strftime"):
                            eng = c2.strftime("%b/%y")
                            p = eng.split("/")
                            lbl = en_para_pt(p[0]) + "/" + p[1]
                            meses_cols[ci2] = lbl
                    break
            if first_header_row is not None:
                break

        if not meses_cols:
            raise ValueError("Nenhuma coluna de mês encontrada.")

        mes_input_norm = ExcelPMPV._normalizar_mes(mes_escolhido)
        col_dados = next(
            (
                ci
                for ci, lbl in meses_cols.items()
                if ExcelPMPV._normalizar_mes(lbl) == mes_input_norm
                or mes_input_norm in ExcelPMPV._normalizar_mes(lbl)
            ),
            None,
        )
        
        if col_dados is None:
            raise ValueError(f"Mês '{mes_escolhido}' não encontrado.")

        first_month_col = min(meses_cols.keys())
        empresas = {}
        empresa_atual = None

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

            if empresa_atual is None: continue

            val_raw = df.iloc[ri, col_dados]
            val = float(val_raw) if pd.notna(val_raw) and str(val_raw).strip() not in ("", "nan") else 0.0

            if col1_str == "A": empresas[empresa_atual]["mol"] = val
            elif col1_str == "B": empresas[empresa_atual]["trans"] = val
            elif col1_str == "C" and val: empresas[empresa_atual]["log"] = val
            elif col1_str == "E": empresas[empresa_atual]["volume"] = val

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
            raise ValueError("Volume Zero — nenhuma linha com volume preenchido.")

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