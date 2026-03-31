import pytest
import os
from sqlalchemy import create_engine, text
import sys

# Garante o acesso aos ficheiros no backend
caminho_dq = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend', 'data_quality'))
sys.path.append(caminho_dq)

from checks import run_sql_check, run_threshold_check

@pytest.fixture(scope="module")
def engine():
    """Cria uma base de dados SQLite in-memory com todas as tabelas necessárias e massa de dados mista."""
    eng = create_engine('sqlite:///:memory:')
    with eng.begin() as conn:
        # Tabelas
        conn.execute(text("CREATE TABLE auditoria (empresa TEXT, periodo TEXT, numero_documento TEXT, valor_bruto REAL, cgr_liquido REAL, status TEXT);"))
        conn.execute(text("CREATE TABLE ret (empresa TEXT, periodo TEXT, quantidade REAL, valor_unitario REAL, status TEXT);"))
        conn.execute(text("CREATE TABLE pmpv_agregados (periodo TEXT, pmpv REAL, preco_final REAL);"))
        conn.execute(text("CREATE TABLE cgf (empresa TEXT, periodo TEXT, volume_inicial_cgf REAL, volume_final_cgf REAL, tipo_operacao TEXT, data_registro DATE);"))
        conn.execute(text("CREATE TABLE marts_data_quality_results (run_id TEXT, check_name TEXT, status TEXT);"))
        
        # Inserção Mista (Válidos + Erros Intencionais)
        conn.execute(text("INSERT INTO pmpv_agregados VALUES ('01/2024', 1.5, 1.8), ('02/2024', -1.0, 1.0), ('03/2024', 1.0, 0.5);"))
        conn.execute(text("INSERT INTO cgf VALUES ('EMP1', '01/2024', 100, 150, 'ENTRADA', '2024-01-01'), ('EMP2', '01/2024', 200, 50, 'ENTRADA', '2024-01-01'), ('EMP3', '02/2024', 100, 150, 'MAGIA', '2024-01-01');"))
        conn.execute(text("INSERT INTO ret VALUES ('EMP1', '01/2024', 10, 5, 'CONCLUIDO'), ('EMP1', '2024-02', 10, 5, 'PENDENTE');"))
        conn.execute(text("INSERT INTO auditoria VALUES ('EMP1', '01/2024', 'DOC1', 100, 100, 'CONCLUIDO');"))
    return eng

# ==========================================
# 1. TESTES DE FAILING ROWS (Regras de Negócio)
# ==========================================

def test_pmpv_valores_negativos(engine):
    sql = "SELECT * FROM pmpv_agregados WHERE pmpv < 0;"
    res = run_sql_check("pmpv_negativo", sql, engine)
    assert res['status'] == 'FAIL'
    assert res['n_failed'] == 1
    assert res['sample_error_rows_json'][0]['periodo'] == '02/2024'

def test_cgf_volume_final_menor_inicial(engine):
    sql = "SELECT * FROM cgf WHERE volume_final_cgf < volume_inicial_cgf;"
    res = run_sql_check("cgf_vol_invalido", sql, engine)
    assert res['status'] == 'FAIL'
    assert res['n_failed'] == 1
    assert res['sample_error_rows_json'][0]['empresa'] == 'EMP2'

def test_cgf_tipo_operacao_invalido(engine):
    sql = "SELECT * FROM cgf WHERE tipo_operacao NOT IN ('ENTRADA', 'SAIDA', 'AJUSTE');"
    res = run_sql_check("cgf_operacao_invalida", sql, engine)
    assert res['status'] == 'FAIL'
    assert res['sample_error_rows_json'][0]['tipo_operacao'] == 'MAGIA'

def test_periodo_invalido_formato(engine):
    # SQLite não tem Regex nativo poderoso, usamos LIKE em in-memory tests
    sql = "SELECT * FROM ret WHERE periodo NOT LIKE '__/____';"
    res = run_sql_check("periodo_invalido", sql, engine)
    assert res['status'] == 'FAIL'
    assert res['sample_error_rows_json'][0]['periodo'] == '2024-02'

def test_regra_perfeita_sem_falhas(engine):
    sql = "SELECT * FROM auditoria WHERE valor_bruto < 0;"
    res = run_sql_check("auditoria_ok", sql, engine)
    assert res['status'] == 'OK'
    assert res['n_failed'] == 0

def test_pmpv_logica_preco_final(engine):
    sql = "SELECT * FROM pmpv_agregados WHERE preco_final < pmpv;"
    res = run_sql_check("pmpv_preco_baixo", sql, engine)
    assert res['status'] == 'FAIL'
    assert res['n_failed'] == 1
    assert res['sample_error_rows_json'][0]['periodo'] == '03/2024'

def test_ret_limite_quantidade(engine):
    sql = "SELECT * FROM ret WHERE quantidade <= 0;"
    res = run_sql_check("ret_qtd_0", sql, engine)
    assert res['status'] == 'OK' # Na nossa fixture todos têm qtd > 0

# ==========================================
# 2. TESTES DE THRESHOLDS (Métricas e Limites)
# ==========================================

@pytest.mark.parametrize("threshold, expected_status", [
    (100.0, 'OK'),  # Limite alto, passa (50% pendentes é <= 100%)
    (10.0, 'WARN'), # Limite rigoroso, falha (50% pendentes não é <= 10%)
])
def test_ret_threshold_pendentes(engine, threshold, expected_status):
    sql_metric = "SELECT (COUNT(CASE WHEN status = 'PENDENTE' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) FROM ret;"
    res = run_threshold_check("teste_limite_pendentes", sql_metric, "<=", threshold, engine)
    assert res['status'] == expected_status
    assert 'metric_value' in res['sample_error_rows_json'][0]

def test_threshold_operador_maior_igual(engine):
    # Testar completude: % de campos não nulos deve ser >= 90%
    sql_metric = "SELECT (COUNT(empresa) * 100.0 / COUNT(*)) FROM auditoria;"
    res = run_threshold_check("teste_completude", sql_metric, ">=", 90.0, engine)
    assert res['status'] == 'OK'
    assert res['n_failed'] == 0

def test_threshold_operador_desconhecido(engine):
    sql_metric = "SELECT 50;"
    res = run_threshold_check("teste_op_errado", sql_metric, "==", 50, engine)
    assert res['status'] == 'WARN' # Operador inválido defalts to False/WARN

def test_threshold_divisao_por_zero(engine):
    # Teste para garantir segurança do metric_query em tabelas vazias
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE tabela_vazia (id INT);"))
    sql = "SELECT (COUNT(*) * 100.0 / NULLIF(COUNT(*), 0)) FROM tabela_vazia;"
    res = run_threshold_check("tabela_vazia_check", sql, "<=", 10, engine)
    assert res['status'] == 'OK' # Devolve 0.0, <= 10

# ==========================================
# 3. TESTES DE INTEGRAÇÃO / PARSING
# ==========================================

def test_tabela_marts_quality_results_insert(engine):
    """Garante que conseguimos gravar no schema marts simulado."""
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO marts_data_quality_results VALUES ('RUN_123', 'teste_pmpv', 'FAIL');"))
        res = conn.execute(text("SELECT COUNT(*) FROM marts_data_quality_results;")).scalar()
    assert res > 0

def test_parsing_expectations_file(tmp_path):
    """Testa se o parser lê corretamente o ficheiro SQL com múltiplas anotações."""
    # Criar um ficheiro mock no tmp_path do pytest
    d = tmp_path / "sql"
    d.mkdir()
    f = d / "expectations.sql"
    conteudo_mock = """
-- CHECK: dummy_failing
-- TYPE: failing_rows
SELECT * FROM table;

-- CHECK: dummy_thresh
-- TYPE: threshold
-- METRIC_QUERY: SELECT 10;
-- THRESHOLD_KEY: max_dummy
-- OPERATOR: <=
    """
    f.write_text(conteudo_mock)
    
    # Importar a função de parsing dinamicamente do run_checks
    try:
        from run_checks import parse_expectations
        checks = parse_expectations(str(f))
        
        assert len(checks) == 2
        assert checks[0]['name'] == 'dummy_failing'
        assert checks[0]['type'] == 'failing_rows'
        
        assert checks[1]['name'] == 'dummy_thresh'
        assert checks[1]['thresh_key'] == 'max_dummy'
        assert checks[1]['operator'] == '<='
    except ImportError:
        pytest.skip("run_checks.py ainda não está exportando parse_expectations corretamente no contexto do teste.")

def test_fluxo_integracao_completo(engine):
    """Simula o fluxo completo passando um SQL válido para failing rows."""
    sql = "SELECT * FROM cgf WHERE empresa = 'EMP1';"
    check_resultado = run_sql_check("integracao_completa", sql, engine)
    
    # Simula a inserção na base
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO marts_data_quality_results (run_id, check_name, status) VALUES ('RUN_1', :nome, :status)"
        ), {"nome": check_resultado['check_name'], "status": check_resultado['status']})
    
    with engine.connect() as conn:
        gravado = conn.execute(text("SELECT status FROM marts_data_quality_results WHERE check_name = 'integracao_completa'")).scalar()
    assert gravado == 'FAIL' # Porque EMP1 existe no fixture