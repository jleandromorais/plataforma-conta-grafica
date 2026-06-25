-- Data Warehouse Schemas (Raw, Staging, Marts)
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Raw Layer: Auditoria
CREATE TABLE IF NOT EXISTS raw.auditoria (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255) NOT NULL,
    tipo_documento VARCHAR(50) NOT NULL,
    numero_documento VARCHAR(255) NOT NULL,
    valor_bruto NUMERIC(15,2) NOT NULL,
    icms NUMERIC(15,2) NOT NULL,
    pis NUMERIC(15,2) NOT NULL,
    cofins NUMERIC(15,2) NOT NULL,
    volume_total NUMERIC(15,4) NOT NULL,
    cgr_liquido NUMERIC(15,2) NOT NULL,
    status VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW()
);

-- Raw Layer: RET
CREATE TABLE IF NOT EXISTS raw.ret (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255),
    periodo VARCHAR(50),
    tipo_encargo VARCHAR(100),
    tipo_nota VARCHAR(50),
    numero_nd VARCHAR(100),
    moeda VARCHAR(10),
    valor_total NUMERIC(15,2),
    quantidade NUMERIC(15,4),
    valor_unitario NUMERIC(15,4),
    contribuicao_ec VARCHAR(50),
    arquivo_origem VARCHAR(500),
    status VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW()
);

-- Raw Layer: Conciliação
CREATE TABLE IF NOT EXISTS raw.concilia (
    id SERIAL PRIMARY KEY,
    arquivo_origem VARCHAR(500),
    categoria_documento VARCHAR(100),
    valor_conciliado NUMERIC(15,2),
    metodo_leitura VARCHAR(100),
    status_conciliacao VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW()
);

-- Raw Layer: PMPV Agregados
CREATE TABLE IF NOT EXISTS raw.pmpv_agregados (
    id SERIAL PRIMARY KEY,
    volume_total_vf NUMERIC(15,4),
    custo_total NUMERIC(15,2),
    pmpv NUMERIC(15,4),
    conta_grafica_inserida NUMERIC(15,4),
    preco_final NUMERIC(15,4),
    volume_programado_mensal NUMERIC(15,4),
    importado_em TIMESTAMP DEFAULT NOW()
);

-- Raw Layer: PMPV Empresas
CREATE TABLE IF NOT EXISTS raw.pmpv_empresas (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255),
    volume_informado NUMERIC(15,4),
    dias_faturamento INTEGER,
    preco_referencia NUMERIC(15,4),
    custo_gerado NUMERIC(15,2),
    importado_em TIMESTAMP DEFAULT NOW()
);

-- Raw Layer: CGF
CREATE TABLE IF NOT EXISTS raw.cgf (
    id SERIAL PRIMARY KEY,
    total_faturado_liquido NUMERIC(15,4),
    total_consumo_proprio NUMERIC(15,4),
    total_canceladas NUMERIC(15,4),
    total_devolucoes NUMERIC(15,4),
    volume_final_cgf NUMERIC(15,4),
    status VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW()
);

-- Staging Layer: Auditoria
CREATE TABLE IF NOT EXISTS staging.auditoria (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255),
    periodo VARCHAR(50),
    tipo_documento VARCHAR(50),
    numero_documento VARCHAR(100),
    valor_bruto NUMERIC(15,2),
    icms NUMERIC(15,2),
    pis NUMERIC(15,2),
    cofins NUMERIC(15,2),
    volume_total NUMERIC(15,4),
    cgr_liquido NUMERIC(15,2),
    status VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW(),
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Staging Layer: RET
CREATE TABLE IF NOT EXISTS staging.ret (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255),
    periodo VARCHAR(50),
    tipo_encargo VARCHAR(100),
    tipo_nota VARCHAR(50),
    numero_nd VARCHAR(100),
    moeda VARCHAR(10),
    valor_total NUMERIC(15,2),
    quantidade NUMERIC(15,4),
    valor_unitario NUMERIC(15,4),
    contribuicao_ec VARCHAR(50),
    arquivo_origem VARCHAR(500),
    status VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW(),
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Staging Layer: Conciliação
CREATE TABLE IF NOT EXISTS staging.concilia (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    arquivo_origem VARCHAR(500),
    categoria_documento VARCHAR(100),
    valor_conciliado NUMERIC(15,2),
    metodo_leitura VARCHAR(100),
    status_conciliacao VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW(),
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Staging Layer: PMPV Agregados
CREATE TABLE IF NOT EXISTS staging.pmpv_agregados (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    volume_total_vf NUMERIC(15,4),
    custo_total NUMERIC(15,2),
    pmpv NUMERIC(15,4),
    conta_grafica_inserida NUMERIC(15,4),
    preco_final NUMERIC(15,4),
    volume_programado_mensal NUMERIC(15,4),
    importado_em TIMESTAMP DEFAULT NOW(),
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Staging Layer: PMPV Empresas
CREATE TABLE IF NOT EXISTS staging.pmpv_empresas (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    empresa VARCHAR(255),
    volume_informado NUMERIC(15,4),
    dias_faturamento INTEGER,
    preco_referencia NUMERIC(15,4),
    custo_gerado NUMERIC(15,2),
    importado_em TIMESTAMP DEFAULT NOW(),
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Staging Layer: CGF
CREATE TABLE IF NOT EXISTS staging.cgf (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    total_faturado_liquido NUMERIC(15,4),
    total_consumo_proprio NUMERIC(15,4),
    total_canceladas NUMERIC(15,4),
    total_devolucoes NUMERIC(15,4),
    volume_final_cgf NUMERIC(15,4),
    status VARCHAR(50),
    importado_em TIMESTAMP DEFAULT NOW(),
    processado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Resumo Auditoria
CREATE TABLE IF NOT EXISTS marts.resumo_auditoria (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255),
    periodo VARCHAR(50),
    total_documentos INT,
    valor_bruto_total NUMERIC(15,2),
    cgr_liquido_total NUMERIC(15,2),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Resumo RET
CREATE TABLE IF NOT EXISTS marts.resumo_ret (
    id SERIAL PRIMARY KEY,
    empresa VARCHAR(255),
    periodo VARCHAR(50),
    total_encargos INT,
    valor_total_encargos NUMERIC(15,2),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Resumo Conciliação
CREATE TABLE IF NOT EXISTS marts.resumo_concilia (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    total_arquivos INT,
    total_validados INT,
    total_revisao INT,
    valor_total_conciliado NUMERIC(15,2),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Resumo PMPV
CREATE TABLE IF NOT EXISTS marts.resumo_pmpv (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    pmpv NUMERIC(15,4),
    preco_final NUMERIC(15,4),
    volume_total NUMERIC(15,4),
    custo_total NUMERIC(15,2),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Resumo CGF
CREATE TABLE IF NOT EXISTS marts.resumo_cgf (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    volume_final_cgf NUMERIC(15,4),
    total_faturado NUMERIC(15,4),
    total_canceladas NUMERIC(15,4),
    total_devolucoes NUMERIC(15,4),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Visão Geral
CREATE TABLE IF NOT EXISTS marts.visao_geral (
    id SERIAL PRIMARY KEY,
    periodo VARCHAR(50),
    pmpv NUMERIC(15,4),
    cgr_liquido_total NUMERIC(15,2),
    volume_cgf NUMERIC(15,4),
    valor_ret_total NUMERIC(15,2),
    atualizado_em TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Data Quality Results (criada pelo run_checks.py, definida aqui para garantia)
CREATE TABLE IF NOT EXISTS marts.data_quality_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50),
    dag_id VARCHAR(100),
    check_name VARCHAR(100),
    status VARCHAR(20),
    n_failed INTEGER,
    sample_error_rows_json TEXT,
    run_ts TIMESTAMP DEFAULT NOW()
);

-- Marts Layer: Monitoring Alerts (criada pelo run_monitoring.py)
CREATE TABLE IF NOT EXISTS marts.monitoring_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(100),
    severity VARCHAR(20),
    message TEXT,
    details_json TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

-- Audit: Log de importações (rastreabilidade de cada carga ETL)
CREATE TABLE IF NOT EXISTS marts.import_log (
    id SERIAL PRIMARY KEY,
    dag_id VARCHAR(100),
    tabela_destino VARCHAR(100),
    n_registros INTEGER,
    status VARCHAR(20),
    mensagem TEXT,
    executado_em TIMESTAMP DEFAULT NOW()
);
