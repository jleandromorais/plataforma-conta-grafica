import logging
import pandas as pd

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
                col_fat = configs_colunas.get("fat_col")
                if col_fat in df.columns:
                    # Isolar consumo próprio
                    mask_cons = _gerar_mascara_consumo(df, configs_colunas.get("fat_cons_col"), configs_colunas.get("fat_cons_val"))
                    
                    df_cons = df[mask_cons]
                    df_sem_cons = df[~mask_cons]

                    vol_fat = pd.to_numeric(df_sem_cons[col_fat], errors="coerce").sum()
                    vol_cons = pd.to_numeric(df_cons[col_fat], errors="coerce").sum()
                    
                    total_faturado += float(vol_fat)
                    total_consumo_proprio += float(vol_cons)
                    
            # Processamento: CANCELADAS / DENEGADAS
            elif "cancelada" in tipo_arquivo or "denegada" in tipo_arquivo:
                col_canc = configs_colunas.get("canc_col")
                if col_canc in df.columns:
                    vol_canc = pd.to_numeric(df[col_canc], errors="coerce").sum()
                    total_canceladas += float(vol_canc)
            
            # Processamento: DEVOLUÇÕES
            elif "devolucao" in tipo_arquivo:
                col_dev = configs_colunas.get("dev_col")
                if col_dev in df.columns:
                    vol_dev = pd.to_numeric(df[col_dev], errors="coerce").sum()
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
        serie = df[col_configurada].astype(str).str.upper().str.strip()
        mask |= (serie == str(val_configurado).upper())
    
    termos_consumo = ["consumo", "proprio", "próprio"]
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype) == "string":
            serie_col = df[col].astype(str).str.lower().str.strip()
            for termo in termos_consumo:
                mask |= serie_col.str.contains(termo, na=False, regex=False)
    return mask