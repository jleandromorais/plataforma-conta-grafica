"""
Script de Verificação Rápida
Verifica se o sistema está configurado corretamente
"""

import os
import sys
from pathlib import Path

def check_file(path, description):
    """Verifica se arquivo existe"""
    if Path(path).exists():
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - FALTANDO: {path}")
        return False

def check_env_var(var, description):
    """Verifica se variável de ambiente existe"""
    value = os.getenv(var)
    if value and value not in ['seu_email@gmail.com', 'seu_app_password_aqui']:
        print(f"✅ {description}: {var}={value[:20]}...")
        return True
    else:
        print(f"⚠️  {description}: {var} não configurado ou usando placeholder")
        return False

def main():
    print("""
    ╔════════════════════════════════════════════════╗
    ║   VERIFICAÇÃO DE CONFIGURAÇÃO DO SISTEMA       ║
    ╚════════════════════════════════════════════════╝
    """)
    
    issues = []
    
    print("\n📁 Verificando Arquivos Essenciais:")
    print("─" * 50)
    
    files_to_check = [
        ("docker-compose.yml", "Docker Compose"),
        ("backend/.env", "Variáveis de Ambiente"),
        ("backend/warehouse/create_schemas.sql", "Schema SQL"),
        ("backend/data_quality/example_data.sql", "Dados de Exemplo"),
        ("backend/reporting/export_excel.py", "Script Export Excel"),
        ("backend/monitoring/run_monitoring.py", "Script Monitoramento"),
        ("backend/airflow/dags/dag_auditoria.py", "DAG Auditoria"),
        ("backend/airflow/dags/dag_ret.py", "DAG RET"),
        ("backend/airflow/dags/dag_consolidacao.py", "DAG Consolidação"),
        ("backend/airflow/dags/dag_data_quality.py", "DAG Data Quality"),
        ("backend/airflow/dags/dag_export_excel.py", "DAG Export Excel"),
        ("backend/airflow/dags/dag_monitoramento_alertas.py", "DAG Monitoramento"),
    ]
    
    for file, desc in files_to_check:
        if not check_file(file, desc):
            issues.append(f"Arquivo faltando: {file}")
    
    print("\n🔐 Verificando Variáveis de Ambiente:")
    print("─" * 50)
    
    # Carregar .env
    env_path = Path("backend/.env")
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
    
    env_vars = [
        ("PG_USER", "PostgreSQL User"),
        ("PG_PASSWORD", "PostgreSQL Password"),
        ("PG_HOST", "PostgreSQL Host"),
        ("PG_PORT", "PostgreSQL Port"),
        ("PG_DB", "PostgreSQL Database"),
    ]
    
    for var, desc in env_vars:
        check_env_var(var, desc)
    
    print("\n📊 Resumo:")
    print("─" * 50)
    
    if not issues:
        print("✅ Todos os arquivos essenciais estão presentes!")
        print("\n🚀 Próximo passo: python start.py")
    else:
        print(f"⚠️  {len(issues)} problema(s) encontrado(s):")
        for issue in issues:
            print(f"   • {issue}")
        print("\n🔧 Corrija os problemas antes de prosseguir")
    
    print("\n" + "═" * 50)

if __name__ == "__main__":
    main()
