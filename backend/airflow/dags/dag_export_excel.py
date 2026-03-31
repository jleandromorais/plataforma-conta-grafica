import os
import sys
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

# Adicionar a diretoria backend ao sys.path para conseguir importar os módulos corretamente
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from backend.reporting.export_excel import main as export_excel_main

default_args = {
    'owner': 'data_team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='dag_export_excel',
    default_args=default_args,
    description='Exporta dados consolidados, Auditoria, RET e Data Quality para Excel formatado.',
    schedule_interval='0 3 * * *', # Diariamente às 03:00
    catchup=False,
    tags=['reporting', 'excel'],
) as dag:

    # Sensor para aguardar a conclusão da DAG de Data Quality do dia atual
    wait_for_data_quality = ExternalTaskSensor(
        task_id='wait_for_data_quality',
        external_dag_id='dag_data_quality_diaria',
        external_task_id=None, # Aguarda a DAG inteira
        allowed_states=['success'],
        failed_states=['failed', 'skipped'],
        mode='poke',
        poke_interval=300,
        timeout=3600,
    )

    # Tarefa de execução do script Python
    export_task = PythonOperator(
        task_id='export_to_excel',
        python_callable=export_excel_main,
    )

    # Ordem de execução
    wait_for_data_quality >> export_task