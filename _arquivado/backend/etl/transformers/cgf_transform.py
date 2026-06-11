import logging
import re
import unicodedata

import pandas as pd


def _normalizar_texto(valor: str) -> str:
    texto = "" if valor is None else str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())


def _converter_serie_numerica(serie: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    texto = serie.astype(str).str.strip()
    texto = texto.str.replace(r"[^0-9,.-]", "", regex=True)

    mascara_br = texto.str.contains(",", na=False) & texto.str.contains(r"\.", na=False)
    texto.loc[mascara_br] = texto.loc[mascara_br].str.replace(".", "", regex=False).str.replace(",", ".", regex=False)

    mascara_virgula = texto.str.contains(",", na=False) & ~texto.str.contains(r"\.", na=False)
    texto.loc[mascara_virgula] = texto.loc[mascara_virgula].str.replace(",", ".", regex=False)

    return pd.to_numeric(texto, errors="coerce")


def _resolver_coluna(df: pd.DataFrame, col_configurada: str, aliases: list[str]) -> str | None:
    mapa_colunas = {_normalizar_texto(col): col for col in df.columns}
    candidatos = [col_configurada, *aliases]

    for candidato in candidatos:
        chave = _normalizar_texto(candidato)
        if chave in mapa_colunas:
            return mapa_colunas[chave]

    for candidato in candidatos:
        chave = _normalizar_texto(candidato)
        if not chave:
            continue
        for col_norm, col_real in mapa_colunas.items():
            if chave in col_norm or col_norm in chave:
                return col_real

    return None

def transformar_cgf(lista_dfs_classificados: list[dict], configs_colunas: dict) -> dict | None:
    """
    Agrega DataFrames Excel e calcula o Volume Final CGF (VF = Faturado - Canceladas - Devoluções).
    """
    if not lista_dfs_classificados:
        return None

    total_faturado = 0.0
    total_canceladas = 0.0
    total_devolucoes = 0.0
    total_consumo_proprio = 0.0

    try:
        for item in lista_dfs_classificados:
            df: pd.DataFrame = item.get("dataframe")
            tipo_arquivo = str(item.get("tipo", "")).lower()
            
            if df is None or df.empty:
                continue

            # Processamento: FATURADA / COMPLEMENTAR
            if "faturada" in tipo_arquivo or "complementar" in tipo_arquivo:
                col_fat = _resolver_coluna(df, configs_colunas.get("fat_col"), ["Volume Faturado", "Volume"])
                if col_fat in df.columns:
                    # Isolar consumo próprio
                    mask_cons = _gerar_mascara_consumo(df, configs_colunas.get("fat_cons_col"), configs_colunas.get("fat_cons_val"))
                    
                    df_cons = df[mask_cons]
                    df_sem_cons = df[~mask_cons]

                    vol_fat = _converter_serie_numerica(df_sem_cons[col_fat]).sum()
                    vol_cons = _converter_serie_numerica(df_cons[col_fat]).sum()
                    
                    total_faturado += float(vol_fat)
                    total_consumo_proprio += float(vol_cons)
                    
            # Processamento: CANCELADAS / DENEGADAS
            elif "cancelada" in tipo_arquivo or "denegada" in tipo_arquivo:
                col_canc = _resolver_coluna(df, configs_colunas.get("canc_col"), ["Volume Canceladas", "Volume Denegadas", "Volume Cancelada"])
                if col_canc in df.columns:
                    vol_canc = _converter_serie_numerica(df[col_canc]).sum()
                    total_canceladas += float(vol_canc)
            
            # Processamento: DEVOLUÇÕES
            elif "devolucao" in tipo_arquivo:
                col_dev = _resolver_coluna(df, configs_colunas.get("dev_col"), ["Volume Devolução", "Volume Devolucao", "Volume de Devolução", "Volume de Devolucao"])
                if col_dev in df.columns:
                    vol_dev = _converter_serie_numerica(df[col_dev]).sum()
                    total_devolucoes += float(vol_dev)

        # Regra de Negócio: Volume Final CGF
        volume_final_cgf = total_faturado - total_canceladas - total_devolucoes

        return {
            "total_faturado_liquido": round(total_faturado, 4),
            "total_consumo_proprio": round(total_consumo_proprio, 4),
            "total_canceladas": round(total_canceladas, 4),
            "total_devolucoes": round(total_devolucoes, 4),
            "volume_final_cgf": round(volume_final_cgf, 4),
            "status": "PROCESSADO"
        }

    except Exception as e:
        logging.error(f"Erro no Transformer do CGF: {e}")
        return None


def _gerar_mascara_consumo(df: pd.DataFrame, col_configurada: str, val_configurado: str) -> pd.Series:
    """Função auxiliar isolada para gerar a máscara Booleana"""
    mask = pd.Series([False] * len(df), index=df.index)
    if col_configurada and col_configurada in df.columns and val_configurado:
        serie = df[col_configurada].map(_normalizar_texto)
        valor = _normalizar_texto(val_configurado)
        mask |= (serie == valor)
        if valor:
            mask |= serie.str.contains(valor, na=False, regex=False)
    
    termos_consumo = ["consumo", "proprio", "consumo proprio", "cons proprio", "cons prop", "uso consumo"]
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            serie_col = df[col].map(_normalizar_texto)
            for termo in termos_consumo:
                mask |= serie_col.str.contains(termo, na=False, regex=False)
    return mask