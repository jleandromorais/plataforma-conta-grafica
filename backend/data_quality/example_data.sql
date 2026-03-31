/* Script para popular base de dados de testes locais (PostgreSQL) */

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Criar Tabelas
CREATE TABLE IF NOT EXISTS staging.auditoria (empresa VARCHAR, periodo VARCHAR, numero_documento VARCHAR, valor_bruto NUMERIC, cgr_liquido NUMERIC, status VARCHAR);
CREATE TABLE IF NOT EXISTS staging.ret (empresa VARCHAR, periodo VARCHAR, quantidade NUMERIC, valor_unitario NUMERIC, valor_total NUMERIC, status VARCHAR);
CREATE TABLE IF NOT EXISTS staging.pmpv_agregados (periodo VARCHAR, pmpv NUMERIC, preco_final NUMERIC, data_atualizacao DATE, fonte VARCHAR);
CREATE TABLE IF NOT EXISTS staging.cgf (empresa VARCHAR, periodo VARCHAR, volume_inicial_cgf NUMERIC, volume_final_cgf NUMERIC, tipo_operacao VARCHAR, data_registro DATE);

TRUNCATE TABLE staging.auditoria, staging.ret, staging.pmpv_agregados, staging.cgf;

-- =======================================================
-- 1. STAGING.AUDITORIA (10 registos válidos)
-- =======================================================
INSERT INTO staging.auditoria VALUES 
('EMP1', '01/2024', 'DOC001', 1500.00, 1200.00, 'CONCLUIDO'),
('EMP1', '01/2024', 'DOC002', 2000.00, 1800.00, 'CONCLUIDO'),
('EMP2', '01/2024', 'DOC003', 500.00, 450.00, 'CONCLUIDO'),
('EMP2', '02/2024', 'DOC004', 300.00, 250.00, 'CONCLUIDO'),
('EMP3', '02/2024', 'DOC005', 1000.00, 900.00, 'CONCLUIDO'),
('EMP3', '03/2024', 'DOC006', 750.00, 700.00, 'CONCLUIDO'),
('EMP4', '03/2024', 'DOC007', 400.00, 350.00, 'CONCLUIDO'),
('EMP4', '04/2024', 'DOC008', 600.00, 550.00, 'CONCLUIDO'),
('EMP5', '04/2024', 'DOC009', 1100.00, 1000.00, 'CONCLUIDO'),
('EMP5', '05/2024', 'DOC010', 800.00, 750.00, 'CONCLUIDO');

-- =======================================================
-- 2. STAGING.RET (5 válidos + 2 inválidos)
-- =======================================================
INSERT INTO staging.ret VALUES 
('EMP1', '01/2024', 10, 50.0, 500.0, 'CONCLUIDO'),
('EMP2', '01/2024', 20, 100.0, 2000.0, 'CONCLUIDO'),
('EMP3', '02/2024', 5, 20.0, 100.0, 'CONCLUIDO'),
('EMP4', '03/2024', 15, 60.0, 900.0, 'CONCLUIDO'),
('EMP5', '04/2024', 50, 10.0, 500.0, 'CONCLUIDO');
-- INVÁLIDOS
INSERT INTO staging.ret VALUES 
('EMP6', '05/2024', 0, 15.0, 0.0, 'FALHA'),       -- FALHA: Quantidade <= 0
('EMP7', '06/2024', 10, NULL, NULL, 'PENDENTE');  -- FALHA: valor_unitario NULL com qtd > 0

-- =======================================================
-- 3. STAGING.PMPV_AGREGADOS (5 válidos + 1 inválido)
-- =======================================================
INSERT INTO staging.pmpv_agregados VALUES 
('01/2024', 1.50, 1.80, CURRENT_DATE, 'OFICIAL'),
('02/2024', 1.55, 1.85, CURRENT_DATE, 'OFICIAL'),
('03/2024', 1.60, 1.90, CURRENT_DATE, 'OFICIAL'),
('04/2024', 1.58, 1.88, CURRENT_DATE, 'OFICIAL'),
('05/2024', 1.62, 1.95, CURRENT_DATE, 'OFICIAL');
-- INVÁLIDO
INSERT INTO staging.pmpv_agregados VALUES 
('06/2024', 1.70, 1.60, CURRENT_DATE, 'OFICIAL'); -- FALHA: preco_final < pmpv

-- =======================================================
-- 4. STAGING.CGF (5 válidos + 2 inválidos)
-- =======================================================
INSERT INTO staging.cgf VALUES 
('EMP1', '01/2024', 1000.0, 1500.0, 'ENTRADA', CURRENT_DATE),
('EMP2', '01/2024', 500.0, 800.0, 'ENTRADA', CURRENT_DATE),
('EMP3', '02/2024', 2000.0, 1800.0, 'SAIDA', CURRENT_DATE),
('EMP4', '03/2024', 300.0, 300.0, 'AJUSTE', CURRENT_DATE),
('EMP5', '04/2024', 100.0, 150.0, 'ENTRADA', CURRENT_DATE);
-- INVÁLIDOS
INSERT INTO staging.cgf VALUES 
('EMP6', '05/2024', 500.0, 200.0, 'ENTRADA', CURRENT_DATE),    -- FALHA: logica volume (final < inicial sendo ENTRADA não faz sentido na nossa lógica geral validada)
('EMP7', '06/2024', 100.0, 150.0, 'DESCONHECIDO', CURRENT_DATE); -- FALHA: tipo_operacao fora da lista permitida