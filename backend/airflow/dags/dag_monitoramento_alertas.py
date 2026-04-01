"""
DAG: dag_monitoramento_alertas
Monitoriza o sistema e envia alertas quando necessário.
✅ CORRIGIDO: monitoring_script usa caminho absoluto /opt/airflow/backend/monitoring/
"""

import subprocess
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'conta-grafica',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def run_monitoring_check(**context):
    """
    Executa o script de monitorização via subprocess.
    ✅ CORRIGIDO: Caminho absoluto correto — sem FileNotFoundError.
    """
    # ✅ CORRIGIDO: Caminho absoluto dentro do contentor Docker
    monitoring_script = '/opt/airflow/backend/monitoring/run_monitoring.py'

    result = subprocess.run(
        ['python', monitoring_script],
        capture_output=True,
        text=True,
        check=True
    )

    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode


with DAG(
    dag_id='dag_monitoramento_alertas',
    default_args=default_args,
    description='Monitorização do sistema e alertas automáticos',
    schedule_interval='*/30 * * * *',  # A cada 30 minutos
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['monitoring', 'alertas'],
) as dag:

    task_monitoramento = PythonOperator(
        task_id='executar_monitoramento',
        python_callable=run_monitoring_check,
        provide_context=True,
    )

    task_monitoramento