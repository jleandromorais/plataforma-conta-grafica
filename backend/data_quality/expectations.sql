-- CHECK: auditoria_valores_negativos
-- TYPE: failing_rows
SELECT empresa, periodo, numero_documento, valor_bruto, cgr_liquido 
FROM staging.auditoria 
WHERE valor_bruto < 0 OR cgr_liquido < 0;

-- CHECK: chaves_nulas_auditoria
-- TYPE: failing_rows
SELECT * FROM staging.auditoria 
WHERE empresa IS NULL OR periodo IS NULL OR numero_documento IS NULL;

-- CHECK: pmpv_valores_negativos
-- TYPE: failing_rows
SELECT periodo, pmpv, preco_final 
FROM staging.pmpv_agregados 
WHERE pmpv < 0 OR preco_final < 0;

-- CHECK: formato_periodo_invalido
-- TYPE: failing_rows
SELECT empresa, periodo, numero_documento 
FROM staging.auditoria 
WHERE periodo !~ '^(0[1-9]|1[0-2])/\d{4}$';

-- CHECK: consistencia_ret_quantidade_valor
-- TYPE: failing_rows
SELECT empresa, periodo, quantidade, valor_unitario 
FROM staging.ret 
WHERE quantidade > 0 AND (valor_unitario IS NULL OR valor_unitario <= 0);

-- CHECK: unicidade_auditoria
-- TYPE: failing_rows
SELECT empresa, periodo, numero_documento, COUNT(*) as qtd
FROM staging.auditoria 
GROUP BY empresa, periodo, numero_documento 
HAVING COUNT(*) > 1;

-- CHECK: completude_auditoria_status
-- TYPE: threshold
-- METRIC_QUERY: SELECT (COUNT(CASE WHEN status IS NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) AS metric_value FROM staging.auditoria;
-- THRESHOLD_KEY: max_null_percent_auditoria_status
-- OPERATOR: <=