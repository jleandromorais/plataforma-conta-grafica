import os
import sys
import locale
from sqlalchemy import create_engine, text
from pathlib import Path

# Forçar UTF-8 em todo o script
if sys.platform == 'win32':
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def load_example_data():
    pg_user = os.getenv("PG_USER", "postgres")
    pg_password = os.getenv("PG_PASSWORD", "admin")
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_db = os.getenv("PG_DB", "plataforma")
    
    # URL com client_encoding explícito
    db_url = f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}?client_encoding=utf8"
    
    try:
        # Testar conexão
        print(f"🔍 Testando conexão com {pg_host}:{pg_port}...")
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Conexão bem-sucedida!")
        
        # Ler arquivo com detecção automática de encoding
        sql_path = Path(__file__).parent / "example_data.sql"
        print(f"📖 Lendo {sql_path}...")
        
        encodings = ['utf-8', 'cp1252', 'latin-1', 'iso-8859-1']
        sql_content = None
        
        for enc in encodings:
            try:
                with open(sql_path, 'r', encoding=enc) as f:
                    sql_content = f.read()
                print(f"✅ Arquivo lido com encoding: {enc}")
                break
            except UnicodeDecodeError:
                continue
        
        if sql_content is None:
            print("❌ Não foi possível ler o arquivo com nenhum encoding!")
            return 1
        
        # Dividir em statements
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        print(f"📝 {len(statements)} statements encontrados")
        
        # Executar
        with engine.begin() as conn:
            for i, stmt in enumerate(statements, 1):
                if stmt:
                    try:
                        print(f"  [{i}/{len(statements)}] {stmt[:50]}...")
                        conn.execute(text(stmt))
                    except Exception as e:
                        print(f"  ⚠️  Erro no statement {i}: {str(e)[:100]}")
        
        print("✅ Dados carregados com sucesso!")
        return 0
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    exit_code = load_example_data()
    exit(exit_code)