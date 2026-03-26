import sqlite3
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.types import Numeric, String, Integer
from dotenv import load_dotenv
import os

load_dotenv()

def migrar_sqlite_para_postgres(caminho_sqlite: str = "plataforma_pmpv.db"):
    print("--- Iniciando Migração SQLite -> PostgreSQL ---")
    
    # 1. Conexões
    conn_sqlite = sqlite3.connect(caminho_sqlite)
    
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "admin")
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    dbname = os.getenv("PG_DB", "plataforma")
    engine_pg = create_engine(f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}")

    try:
        # 2. Descobrir todas as tabelas no SQLite
        query_tabelas = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        tabelas = pd.read_sql(query_tabelas, conn_sqlite)['name'].tolist()

        if not tabelas:
            print("Nenhuma tabela encontrada no SQLite.")
            return

        # Dicionário de tipos de dados rigorosos (Conforme os teus requisitos)
        tipos_postgres = {
            "empresa": String(255),
            "periodo": String(50),
            "status": String(50),
            "valor_total": Numeric(15, 2),
            "cgr_liquido": Numeric(15, 2),
            "volume_total": Numeric(15, 4),
            "quantidade": Numeric(15, 4),
            "valor_unitario": Numeric(15, 4)
        }

        # 3. Migrar cada tabela
        for tabela in tabelas:
            print(f"A migrar tabela: '{tabela}'...")
            df = pd.read_sql(f"SELECT * FROM {tabela}", conn_sqlite)
            
            # Se tiver uma coluna 'id' do SQLite, podemos ignorá-la para o Postgres gerar a sua
            if 'id' in df.columns:
                df = df.drop(columns=['id'])

            # Copiar para o Postgres
            # Usar apenas os tipos que existem nas colunas (evita erro se coluna não está em tipos_postgres)
            dtype_para_tabela = {col: tipos_postgres.get(col) for col in df.columns if col in tipos_postgres}
            
            df.to_sql(
                name=tabela,
                con=engine_pg,
                if_exists='replace', # Substitui se já existir na primeira migração
                index=False,
                dtype=dtype_para_tabela
            )
            print(f"  -> {len(df)} linhas migradas com sucesso.")

        print("--- Migração concluída com sucesso! ---")

    except Exception as e:
        print(f"Erro durante a migração: {e}")
    finally:
        conn_sqlite.close()

if __name__ == "__main__":
    migrar_sqlite_para_postgres()