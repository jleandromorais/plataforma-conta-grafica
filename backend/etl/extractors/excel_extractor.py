import logging
import pandas as pd
from pathlib import Path

def extrair_dados_excel(caminho: Path, nome_aba: str | int | None = 0) -> pd.DataFrame | None:
    """
    Lê um ficheiro Excel e retorna um DataFrame do Pandas.
    
    Parâmetros:
    - caminho (Path): O caminho completo para o ficheiro .xlsx ou .xls
    - nome_aba (str | int): Nome da aba ou o índice (0 para a primeira aba)
    """
    try:
        # O engine 'openpyxl' é o mais estável para ficheiros modernos (.xlsx)
        df = pd.read_excel(caminho, sheet_name=nome_aba, engine='openpyxl')
        
        logging.info(f"Ficheiro Excel '{caminho.name}' lido com sucesso. Total de linhas: {len(df)}")
        return df
        
    except FileNotFoundError:
        logging.error(f"Ficheiro Excel não encontrado no caminho fornecido: {caminho}")
    except ValueError as ve:
        logging.error(f"Erro de valor ao ler {caminho.name} (Aba '{nome_aba}' pode não existir): {ve}")
    except Exception as e:
        logging.error(f"Erro inesperado ao extrair Excel de {caminho.name}: {e}")
        
    return None