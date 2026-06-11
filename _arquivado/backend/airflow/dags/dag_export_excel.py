"""
DAG: dag_export_excel
Exporta relatórios consolidados para formato Excel.
✅ CORRIGIDO: sys.path aponta para /opt/airflow
✅ CORRIGIDO: Import usa 'from backend.reporting.export_excel import main'
"""

import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

# ✅ CORRIGIDO: Raiz /opt/airflow adicionada ao path
# Com PYTHONPATH=/opt/airflow no docker-compose, isto é redundante mas garante robustez
if '/opt/airflow' not in sys.path:
    sys.path.insert(0, '/opt/airflow')

default_args = {
    'owner': 'conta-grafica',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def run_export_excel(**context):
    """
    Importa e executa a exportação para Excel.
    ✅ CORRIGIDO: Import absoluto 'from backend.reporting.export_excel import main'
    """
    # ✅ CORRIGIDO: Sem 'ModuleNotFoundError: No module named backend'
    from backend.reporting.export_excel import main as export_excel_main
    export_excel_main()


with DAG(
    dag_id='dag_export_excel',
    default_args=default_args,
    description='Exportação de relatórios consolidados para Excel',
    schedule_interval='@weekly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['export', 'excel', 'relatorios'],
) as dag:

    task_export = PythonOperator(
        task_id='exportar_para_excel',
        python_callable=run_export_excel,
        provide_context=True,
    )

    task_export