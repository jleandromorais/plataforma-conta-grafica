import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.append('/opt/airflow/backend')
from data_quality.run_checks import main as executar_dq

default_args = {
    'owner': 'engenharia_dados',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def executar_verificacoes(**kwargs):
    # Monta a URL do PostgreSQL direto das variáveis de ambiente (mesmo padrão dos outros DAGs)
    pg_user = os.getenv('PG_USER', 'postgres')
    pg_password = os.getenv('PG_PASSWORD', 'admin')
    pg_host = os.getenv('PG_HOST', 'postgres-plataforma')
    pg_port = os.getenv('PG_PORT', '5432')
    pg_db = os.getenv('PG_DB', 'plataforma')
    db_url = f"postgresql+psycopg2://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"

    dag_id = kwargs['dag'].dag_id

    exit_code = executar_dq(db_url=db_url, dag_id=dag_id)
    if exit_code != 0:
        raise ValueError("Falha crítica nos testes de Data Quality. Verifique a tabela marts.data_quality_results.")

with DAG(
    'dag_data_quality_diaria',
    default_args=default_args,
    description='Executa as validações de Qualidade de Dados após o ETL',
    schedule_interval='30 2 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['dq', 'auditoria'],
) as dag:

    tarefa_dq = PythonOperator(
        task_id='correr_testes_dq',
        python_callable=executar_verificacoes,
        provide_context=True,
    )