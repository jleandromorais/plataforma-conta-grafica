"""
DAG Airflow: Monitoramento e Alertas
Plataforma Conta Gráfica

Responsabilidades:
- Schedule: Diariamente às 03h00 (antes do export_excel)
- Executa: backend/monitoring/run_monitoring.py
- Aguarda: dag_data_quality_diaria
- Registra alertas e envia emails SMTP

DAG ID: dag_monitoramento_alertas
Tags: monitoring, alertas
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
from airflow.utils.decorators import apply_defaults
import logging
import subprocess
import sys
import os

# Configuração de logging
logger = logging.getLogger(__name__)

# ============================================================================
# ARGUMENTOS PADRÃO
# ============================================================================

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email': ['data-engineering@empresa.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# ============================================================================
# DEFINIÇÃO DA DAG
# ============================================================================

dag = DAG(
    'dag_monitoramento_alertas',
    default_args=default_args,
    description='Monitoramento e alertas da Plataforma Conta Gráfica',
    schedule_interval='0 3 * * *',  # Diariamente às 03h00
    tags=['monitoring', 'alertas'],
    catchup=False,
    max_active_runs=1,
)

# ============================================================================
# TASKS
# ============================================================================

def run_monitoring_check():
    """
    Task principal que executa o script de monitoramento
    
    Executa:
    - python backend/monitoring/run_monitoring.py
    
    Captura saída e status de execução
    """
    
    logger.info("=" * 80)
    logger.info("INICIANDO TASK: run_monitoring_check")
    logger.info("=" * 80)
    
    try:
        # Caminho para o script de monitoramento
        monitoring_script = os.path.join(
            os.getenv('AIRFLOW_HOME', '/home/airflow'),
            'backend/monitoring/run_monitoring.py'
        )
        
        logger.info(f"Script: {monitoring_script}")
        logger.info(f"Working directory: {os.getcwd()}")
        
        # Executar script
        result = subprocess.run(
            [sys.executable, monitoring_script],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos timeout
        )
        
        logger.info(f"Exit code: {result.returncode}")
        
        # Log stdout
        if result.stdout:
            logger.info("STDOUT:")
            for line in result.stdout.split('\n'):
                if line.strip():
                    logger.info(f"  {line}")
        
        # Log stderr
        if result.stderr:
            logger.error("STDERR:")
            for line in result.stderr.split('\n'):
                if line.strip():
                    logger.error(f"  {line}")
        
        # Retornar exit code
        if result.returncode != 0:
            raise Exception(f"Monitoring script falhou com exit code {result.returncode}")
        
        logger.info("✅ TASK CONCLUÍDA COM SUCESSO")
        logger.info("=" * 80)
        
        return {
            'exit_code': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
    except subprocess.TimeoutExpired:
        logger.error("❌ Timeout ao executar script de monitoramento")
        raise Exception("Monitoring script timeout após 5 minutos")
    
    except FileNotFoundError:
        logger.error(f"❌ Script não encontrado: {monitoring_script}")
        raise Exception(f"Arquivo não encontrado: {monitoring_script}")
    
    except Exception as e:
        logger.error(f"❌ Erro ao executar monitoramento: {str(e)}")
        raise


def validate_environment():
    """
    Task para validar variáveis de ambiente necessárias
    """
    
    logger.info("Validando configuração de ambiente...")
    
    required_vars = [
        'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
        'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD',
        'ALERT_FROM', 'ALERT_TO'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            logger.warning(f"  ⚠ {var} não configurada")
        else:
            # Mascarar valores sensíveis
            if 'PASSWORD' in var:
                logger.info(f"  ✓ {var} configurada (***)")
            else:
                logger.info(f"  ✓ {var} = {value}")
    
    if missing:
        raise Exception(f"Variáveis obrigatórias faltando: {', '.join(missing)}")
    
    logger.info("✓ Todas as variáveis de ambiente estão configuradas")


def log_start_message():
    """
    Task inicial para log
    """
    logger.info("=" * 80)
    logger.info("DAG: dag_monitoramento_alertas")
    logger.info(f"Execução iniciada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 80)


def log_end_message():
    """
    Task final para log
    """
    logger.info("=" * 80)
    logger.info("DAG: dag_monitoramento_alertas")
    logger.info(f"Execução finalizada em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info("=" * 80)


# ============================================================================
# INSTANCIAR TASKS
# ============================================================================

task_log_start = PythonOperator(
    task_id='log_start_message',
    python_callable=log_start_message,
    dag=dag,
)

task_validate_env = PythonOperator(
    task_id='validate_environment',
    python_callable=validate_environment,
    retries=0,  # Não fazer retry em validação
    dag=dag,
)

task_run_monitoring = PythonOperator(
    task_id='run_monitoring_check',
    python_callable=run_monitoring_check,
    pool='monitoring_pool',  # Pool com limite de 1 execução paralela
    trigger_rule='all_success',
    dag=dag,
)

task_log_end = PythonOperator(
    task_id='log_end_message',
    python_callable=log_end_message,
    trigger_rule='all_done',  # Executar mesmo se houver falha
    dag=dag,
)

# ============================================================================
# DEPENDÊNCIAS E PIPELINE
# ============================================================================

# Pipeline local
task_log_start >> task_validate_env >> task_run_monitoring >> task_log_end

# Dependência externa: Aguardar conclusão de dag_data_quality_diaria
# (Descomentar quando a DAG existir)
# from airflow.sensors.external_task import ExternalTaskSensor
#
# wait_for_data_quality = ExternalTaskSensor(
#     task_id='wait_for_data_quality',
#     external_dag_id='dag_data_quality_diaria',
#     external_task_id='task_end_of_day_quality_check',
#     poke_interval=300,  # Verificar a cada 5 minutos
#     timeout=3600,  # Timeout de 1 hora
#     mode='poke',
#     dag=dag,
# )
#
# task_validate_env >> wait_for_data_quality >> task_run_monitoring

# ============================================================================
# DOCUMENTAÇÃO DA DAG
# ============================================================================

dag.doc_md = """
## DAG: Monitoramento e Alertas - Plataforma Conta Gráfica

### Descrição
DAG para executar o sistema de monitoramento automático da plataforma CGF.
Detecta anomalias em dados (data quality, delays, volumes zerados, duplicatas)
e envia alertas via email.

### Schedule
- **Frequência**: Diariamente
- **Horário**: 03:00 (UTC)
- **Timezone**: America/Recife

### Dependências
- PostgreSQL 16+
- Python 3.10+
- Airflow 2.9+

### Variáveis de Ambiente Obrigatórias
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cgf_database
DB_USER=cgf_user
DB_PASSWORD=***

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@empresa.com
SMTP_PASSWORD=***
ALERT_FROM=monitoring@empresa.com
ALERT_TO=dba@empresa.com,deng@empresa.com
SMTP_USE_TLS=true
```

### Tasks
1. **log_start_message**: Log de início
2. **validate_environment**: Validação de variáveis obrigatórias
3. **run_monitoring_check**: Executa script de monitoramento
4. **log_end_message**: Log de conclusão

### Saída
- **Logs**: `/logs/alerts_YYYYMMDD.log`
- **Banco de Dados**: Tabela `marts.monitoring_alerts`
- **Email**: Para destinatários configurados em `ALERT_TO`

### Alertas Monitorados
1. **Data Quality Failures** (últimas 24h) - CRÍTICO
2. **Import Delay** (> 3 dias) - AVISO
3. **Zero Volume** (zerado ou NULL) - CRÍTICO
4. **Duplicate Periods** - AVISO
5. **Abnormal Rejection Rate** (> 5%) - AVISO

### Exit Codes
- `0`: Sem alertas
- `1`: Alertas foram detectados e processados

### Contato
Data Engineering Team: data-engineering@empresa.com

### Links Úteis
- [Documentação CGF](https://wiki.empresa.com/cgf)
- [Runbooks](https://wiki.empresa.com/runbooks)
- [Status Page](https://status.empresa.com)
"""

# ============================================================================
# POOL CONFIGURATION (adicionar ao airflow.cfg ou via UI)
# ============================================================================
"""
[core]
pools = 
    monitoring_pool:1:Pool para monitoramento (max 1 execução paralela)
"""