from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import sys
import os

# Adiciona o caminho local ao sys.path para importar os scripts do repositório
sys.path.append('/opt/airflow/dags/repo/backend/data_quality')
from run_checks import main as executar_dq

default_args = {
    'owner': 'engenharia_dados',
    'depends_on_past': False,
    'email_on_failure': True, # Requer configuração SMTP no Airflow
    'email': ['teu_email@empresa.com'],
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def executar_verificacoes(**kwargs):
    # Vai buscar a URI do PostgreSQL configurado nas Connections do Airflow (conn_id: 'postgres_default')
    hook = PostgresHook(postgres_conn_id='postgres_default')
    db_url = hook.get_uri()
    
    dag_id = kwargs['dag'].dag_id
    
    # Executa a validação. Se o exit_code for 1, lança uma exceção para o Airflow marcar a Task como "Failed"
    exit_code = executar_dq(db_url=db_url, dag_id=dag_id)
    if exit_code != 0:
        raise ValueError("Falha crítica nos testes de Qualidade de Dados (Data Quality). Verifica a tabela marts.data_quality_results.")

with DAG(
    'dag_data_quality_diaria',
    default_args=default_args,
    description='Executa as validações de Qualidade de Dados após o ETL',
    schedule_interval='30 2 * * *', # Corre diariamente às 02h30 (após as tuas DAGs principais)
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['dq', 'auditoria'],
) as dag:

    tarefa_dq = PythonOperator(
        task_id='correr_testes_dq',
        python_callable=executar_verificacoes,
        provide_context=True
    )
    
    # Podes adicionar sensores aqui, ex: 
    # sensor_espera_etl >> tarefa_dq