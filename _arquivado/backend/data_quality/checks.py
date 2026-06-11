import pandas as pd
from sqlalchemy import text
import yaml

def carregar_configuracao(caminho_yaml='dq_config.yaml'):
    with open(caminho_yaml, 'r') as f:
        return yaml.safe_load(f)

def run_sql_check(name, sql, engine, sample_limit=20):
    """Executa uma query que devolve os registos que falharam a regra (failing rows)."""
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    
    n_failed = len(df)
    status = 'FAIL' if n_failed > 0 else 'OK'
    
    # Converte os timestamps/datas para string para evitar erros no JSON
    df = df.astype(str)
    sample = df.head(sample_limit).to_dict(orient='records')
    
    return {
        'check_name': name,
        'status': status,
        'n_failed': n_failed,
        'sample_error_rows_json': sample
    }

def run_threshold_check(name, sql, operator, threshold_val, engine):
    """Executa uma query que devolve um valor métrico e compara com o limite configurado."""
    with engine.connect() as conn:
        resultado = conn.execute(text(sql)).scalar()
    
    resultado = float(resultado) if resultado is not None else 0.0
    
    if operator == '<=':
        passou = resultado <= threshold_val
    elif operator == '>=':
        passou = resultado >= threshold_val
    else:
        passou = False

    status = 'OK' if passou else 'WARN' # Thresholds falhados geram WARN por padrão
    
    return {
        'check_name': name,
        'status': status,
        'n_failed': 1 if not passou else 0,
        'sample_error_rows_json': [{'metric_value': resultado, 'threshold_expected': threshold_val}]
    }