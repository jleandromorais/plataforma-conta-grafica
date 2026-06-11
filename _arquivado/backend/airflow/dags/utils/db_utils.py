import os
import logging
from sqlalchemy import create_engine
import pandas as pd

def obter_engine():
    try:
        host = os.getenv("PG_HOST", "postgres")
        port = os.getenv("PG_PORT", "5432")
        user = os.getenv("PG_USER", "postgres")
        password = os.getenv("PG_PASSWORD", "admin")
        db = os.getenv("PG_DB", "plataforma")
        
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
        engine = create_engine(url)
        return engine
    except Exception as e:
        logging.error(f"Erro ao obter engine do banco de dados: {str(e)}")
        raise

def ler_staging(tabela: str):
    try:
        engine = obter_engine()
        query = f"SELECT * FROM staging.{tabela}"
        df = pd.read_sql(query, engine)
        logging.info(f"Dados lidos com sucesso da tabela staging.{tabela}. Total: {len(df)} linhas.")
        return df.to_dict(orient='records')
    except Exception as e:
        logging.error(f"Erro ao ler tabela staging.{tabela}: {str(e)}")
        raise

def inserir_marts(tabela: str, dados: list[dict]):
    try:
        if not dados:
            logging.warning(f"Nenhum dado para inserir na tabela marts.{tabela}.")
            return
            
        engine = obter_engine()
        df = pd.DataFrame(dados)
        df.to_sql(tabela, engine, schema='marts', if_exists='append', index=False)
        logging.info(f"Inseridos {len(df)} registros na tabela marts.{tabela}.")
    except Exception as e:
        logging.error(f"Erro ao inserir dados na tabela marts.{tabela}: {str(e)}")
        raise