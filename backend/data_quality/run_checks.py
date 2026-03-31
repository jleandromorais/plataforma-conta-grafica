import os
import json
import argparse
from datetime import datetime
from sqlalchemy import create_engine, text
from checks import run_sql_check, run_threshold_check, carregar_configuracao

def parse_expectations(filepath):
    """Lê o ficheiro SQL e separa os blocos de queries baseados em comentários."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    blocks = content.split('-- CHECK: ')[1:]
    checks = []
    for block in blocks:
        lines = block.strip().split('\n')
        name = lines[0].strip()
        chk_type = [l.split(':')[1].strip() for l in lines if l.startswith('-- TYPE:')][0]
        
        if chk_type == 'failing_rows':
            sql = '\n'.join([l for l in lines if not l.startswith('--')])
            checks.append({'name': name, 'type': chk_type, 'sql': sql})
        elif chk_type == 'threshold':
            metric_sql = [l.split('METRIC_QUERY:')[1].strip() for l in lines if l.startswith('-- METRIC_QUERY:')][0]
            thresh_key = [l.split('THRESHOLD_KEY:')[1].strip() for l in lines if l.startswith('-- THRESHOLD_KEY:')][0]
            operator = [l.split('OPERATOR:')[1].strip() for l in lines if l.startswith('-- OPERATOR:')][0]
            checks.append({'name': name, 'type': chk_type, 'sql': metric_sql, 'thresh_key': thresh_key, 'operator': operator})
            
    return checks

def garantir_tabela_marts(engine):
    """Garante que o schema e a tabela de resultados existem."""
    ddl = """
    CREATE SCHEMA IF NOT EXISTS marts;
    CREATE TABLE IF NOT EXISTS marts.data_quality_results (
        id SERIAL PRIMARY KEY,
        run_id VARCHAR(50),
        dag_id VARCHAR(100),
        check_name VARCHAR(100),
        status VARCHAR(20),
        n_failed INTEGER,
        sample_error_rows_json TEXT,
        run_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))

def main(db_url, dag_id='manual_run'):
    engine = create_engine(db_url)
    garantir_tabela_marts(engine)
    
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config = carregar_configuracao(os.path.join(dir_path, 'dq_config.yaml'))
    checks_def = parse_expectations(os.path.join(dir_path, 'expectations.sql'))
    
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    resultados = []
    
    for chk in checks_def:
        if chk['type'] == 'failing_rows':
            res = run_sql_check(chk['name'], chk['sql'], engine)
        elif chk['type'] == 'threshold':
            threshold_val = config['thresholds'].get(chk['thresh_key'], 0)
            res = run_threshold_check(chk['name'], chk['sql'], chk['operator'], threshold_val, engine)
        
        res['run_id'] = run_id
        res['dag_id'] = dag_id
        resultados.append(res)
    
    # Grava na base de dados
    with engine.begin() as conn:
        for r in resultados:
            stmt = text("""
                INSERT INTO marts.data_quality_results 
                (run_id, dag_id, check_name, status, n_failed, sample_error_rows_json) 
                VALUES (:run_id, :dag_id, :check_name, :status, :n_failed, :sample_error_rows_json)
            """)
            conn.execute(stmt, {
                'run_id': r['run_id'],
                'dag_id': r['dag_id'],
                'check_name': r['check_name'],
                'status': r['status'],
                'n_failed': r['n_failed'],
                'sample_error_rows_json': json.dumps(r['sample_error_rows_json'])
            })
            
    # Gera relatório JSON local
    relatorio = {
        'run_id': run_id,
        'dag_id': dag_id,
        'totals': {
            'n_checks': len(resultados),
            'n_failed_checks': sum(1 for r in resultados if r['status'] == 'FAIL'),
            'n_warning_checks': sum(1 for r in resultados if r['status'] == 'WARN')
        },
        'details': resultados
    }
    
    with open(f'dq_report_{run_id}.json', 'w') as f:
        json.dump(relatorio, f, indent=4)
        
    print(f"Data Quality Finalizado. {relatorio['totals']['n_failed_checks']} falhas críticas.")
    
    if relatorio['totals']['n_failed_checks'] > 0:
        return 1 # Código de erro para falhar a DAG no Airflow
    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db-url', required=True, help='Database SQLAlchemy URL')
    parser.add_argument('--dag-id', default='manual_run', help='ID of the DAG triggering the checks')
    args = parser.parse_args()
    
    exit_code = main(args.db_url, args.dag_id)
    exit(exit_code)