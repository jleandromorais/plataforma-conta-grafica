import pytest
from sqlalchemy import create_engine, text
import sys
import os

# 1. Ensinar ao Python onde está o ficheiro checks.py
caminho_dq = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data_quality'))
sys.path.append(caminho_dq)

# 2. Agora já podemos importar a função com sucesso
from checks import run_sql_check

@pytest.fixture
def test_engine():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE auditoria (empresa TEXT, periodo TEXT, numero_documento TEXT, valor_bruto REAL);"))
        conn.execute(text("INSERT INTO auditoria VALUES ('EMP1', '10/2023', 'DOC1', 100.0);"))
        conn.execute(text("INSERT INTO auditoria VALUES ('EMP1', '10/2023', 'DOC2', -50.0);")) # Falha esperada
    return engine

def test_auditoria_valores_negativos(test_engine):
    sql = "SELECT * FROM auditoria WHERE valor_bruto < 0"
    resultado = run_sql_check("teste_negativos", sql, test_engine)
    
    assert resultado['status'] == 'FAIL'
    assert resultado['n_failed'] == 1
    assert resultado['sample_error_rows_json'][0]['numero_documento'] == 'DOC2'

def test_auditoria_chaves_nulas(test_engine):
    sql = "SELECT * FROM auditoria WHERE empresa IS NULL"
    resultado = run_sql_check("teste_nulos", sql, test_engine)
    
    assert resultado['status'] == 'OK'
    assert resultado['n_failed'] == 0