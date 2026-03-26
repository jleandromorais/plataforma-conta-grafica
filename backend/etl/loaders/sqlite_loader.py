import sqlite3
import logging
from pathlib import Path

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def carregar_dados_sqlite(nome_tabela: str, dados_limpos: list[dict], db_path: str = "pmpv_data.db") -> bool:
    """
    Loader Genérico: Recebe uma tabela de destino e uma lista de dicionários.
    Insere os dados de forma dinâmica e em lote (bulk insert).
    """
    if not dados_limpos:
        logging.warning(f"Nenhum dado para carregar na tabela '{nome_tabela}'.")
        return False

    db_file = Path(db_path)
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 1. Extrair dinamicamente os nomes das colunas a partir do primeiro dicionário
        # Ex: ['empresa', 'periodo', 'valor_total']
        colunas = list(dados_limpos[0].keys())
        colunas_str = ", ".join(colunas)
        
        # 2. Criar os "placeholders" (os pontos de interrogação) para a query SQL
        # Ex: "?, ?, ?"
        placeholders = ", ".join(["?"] * len(colunas))

        # 3. Montar a Query SQL genérica
        query_sql = f"INSERT INTO {nome_tabela} ({colunas_str}) VALUES ({placeholders})"

        # 4. Converter a lista de dicionários numa lista de tuplos com os valores ordenados
        valores_para_inserir = [tuple(item[coluna] for coluna in colunas) for item in dados_limpos]

        # 5. Executar a inserção em lote (MUITO mais rápido que inserir linha a linha)
        cursor.executemany(query_sql, valores_para_inserir)
        conn.commit()

        logging.info(f"Sucesso! {len(valores_para_inserir)} registos embalados e guardados na tabela '{nome_tabela}'.")
        return True

    except sqlite3.OperationalError as oe:
        logging.error(f"Erro de base de dados (A tabela '{nome_tabela}' existe? As colunas batem certo?): {oe}")
        return False
    except Exception as e:
        logging.error(f"Erro crítico ao carregar dados no SQLite: {e}")
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()