CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.auditoria (
    empresa VARCHAR(50), periodo VARCHAR(10), tipo_documento VARCHAR(50), 
    numero_documento VARCHAR(50), valor_bruto NUMERIC, cgr_liquido NUMERIC, status VARCHAR(20)
);

-- Linhas Válidas
INSERT INTO staging.auditoria VALUES ('XPTO', '08/2023', 'Fatura', 'INV-001', 1500.00, 1200.00, 'Processado');
INSERT INTO staging.auditoria VALUES ('ACME', '08/2023', 'Fatura', 'INV-002', 200.00, 180.00, 'Processado');

-- Linha com erro: Valores Negativos
INSERT INTO staging.auditoria VALUES ('XPTO', '08/2023', 'Nota', 'INV-003', -50.00, -50.00, 'Processado');

-- Linha com erro: Chave Nula e Formato Período Inválido
INSERT INTO staging.auditoria VALUES (NULL, '2023-08', 'Nota', 'INV-004', 100.00, 100.00, NULL);

-- Linha com erro: Duplicado
INSERT INTO staging.auditoria VALUES ('ACME', '08/2023', 'Fatura', 'INV-002', 200.00, 180.00, 'Processado');