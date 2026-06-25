import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Importar o loader do SQLite para servir de Fallback
from backend.etl.loaders.sqlite_loader import carregar_dados_sqlite

# Carrega as variáveis de ambiente do ficheiro .env
load_dotenv()

def obter_engine_postgres():
    """Cria a conexão com o PostgreSQL usando SQLAlchemy e variáveis de ambiente."""
    user = os.getenv("PG_USER", "postgres")
    password = os.getenv("PG_PASSWORD", "admin")
    host = os.getenv("PG_HOST", "localhost")
    port = os.getenv("PG_PORT", "5432")
    dbname = os.getenv("PG_DB", "plataforma")
    
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    return create_engine(url)

def carregar_dados_postgres(nome_tabela: str, dados_limpos: list[dict]) -> bool:
    """
    Loader genérico para PostgreSQL com Fallback para SQLite.
    """
    if not dados_limpos:
        logging.warning(f"Nenhum dado para carregar na tabela '{nome_tabela}'.")
        return False

    try:
        engine = obter_engine_postgres()
        
        # O 'begin()' garante que fazemos COMMIT automático no fim, ou ROLLBACK se der erro
        with engine.begin() as conn:
            # Extrair nomes das colunas (ex: ['empresa', 'valor_total'])
            colunas = list(dados_limpos[0].keys())
            colunas_str = ", ".join(colunas)
            
            # Criar os binds do SQLAlchemy (ex: :empresa, :valor_total)
            binds_str = ", ".join([f":{col}" for col in colunas])
            
            # Montar a Query
            query = text(f"INSERT INTO {nome_tabela} ({colunas_str}) VALUES ({binds_str})")
            
            # Inserção em lote (Bulk Insert)
            conn.execute(query, dados_limpos)
            
        logging.info(f"✅ [POSTGRES] Sucesso! {len(dados_limpos)} registos salvos em '{nome_tabela}'.")
        return True

    except Exception as e:
        logging.error(f"❌ [POSTGRES] Falha na conexão ou inserção: {e}")
        logging.info("🔄 [FALLBACK] Iniciando gravação de segurança no SQLite...")
        
        # Fallback Automático: Chama o Loader antigo
        return carregar_dados_sqlite(nome_tabela, dados_limpos)