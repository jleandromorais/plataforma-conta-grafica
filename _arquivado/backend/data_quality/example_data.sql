/* Script para popular base de dados de testes locais (PostgreSQL) */

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Criar Tabelas
CREATE TABLE IF NOT EXISTS staging.auditoria (empresa VARCHAR, periodo VARCHAR, numero_documento VARCHAR, valor_bruto NUMERIC, cgr_liquido NUMERIC, status VARCHAR);
CREATE TABLE IF NOT EXISTS staging.ret (empresa VARCHAR, periodo VARCHAR, quantidade NUMERIC, valor_unitario NUMERIC, valor_total NUMERIC, status VARCHAR);
CREATE TABLE IF NOT EXISTS staging.pmpv_agregados (periodo VARCHAR, pmpv NUMERIC, preco_final NUMERIC, volume_total_vf NUMERIC, custo_total NUMERIC);
CREATE TABLE IF NOT EXISTS staging.cgf (periodo VARCHAR, total_faturado_liquido NUMERIC, total_consumo_proprio NUMERIC, total_canceladas NUMERIC, total_devolucoes NUMERIC, volume_final_cgf NUMERIC, status VARCHAR);

TRUNCATE TABLE staging.auditoria, staging.ret, staging.pmpv_agregados, staging.cgf RESTART IDENTITY CASCADE;

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
('01/2024', 1.50, 1.80, 500000.0, 750000.00),
('02/2024', 1.55, 1.85, 520000.0, 806000.00),
('03/2024', 1.60, 1.90, 510000.0, 816000.00),
('04/2024', 1.58, 1.88, 530000.0, 837400.00),
('05/2024', 1.62, 1.95, 540000.0, 874800.00);
-- INVÁLIDO
INSERT INTO staging.pmpv_agregados VALUES
('06/2024', 1.70, 1.60, 500000.0, 850000.00); -- FALHA: preco_final < pmpv

-- =======================================================
-- 4. STAGING.CGF (5 válidos + 1 inválido)
-- =======================================================
INSERT INTO staging.cgf VALUES
('01/2024', 1500000.0, 5000.0, 50000.0, 10000.0, 1435000.0, 'OK'),
('02/2024', 1480000.0, 4800.0, 45000.0, 8000.0, 1427000.0, 'OK'),
('03/2024', 1520000.0, 5100.0, 60000.0, 12000.0, 1443000.0, 'OK'),
('04/2024', 1490000.0, 4900.0, 55000.0, 9500.0, 1425500.0, 'OK'),
('05/2024', 1510000.0, 5050.0, 52000.0, 11000.0, 1447000.0, 'OK');
-- INVÁLIDO
INSERT INTO staging.cgf VALUES
('06/2024', 1400000.0, 4700.0, 1500000.0, 9000.0, -109000.0, 'REVISAO_MANUAL'); -- FALHA: canceladas > faturado