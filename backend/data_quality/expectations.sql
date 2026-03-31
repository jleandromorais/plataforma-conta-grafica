/* =========================================================================
   EXPECTATIONS - DATA QUALITY
   Tabelas: auditoria, ret, pmpv_agregados, cgf
========================================================================= */

-- CHECK: auditoria_valores_negativos
-- TYPE: failing_rows
SELECT empresa, periodo, numero_documento, valor_bruto, cgr_liquido 
FROM staging.auditoria 
WHERE valor_bruto < 0 OR cgr_liquido < 0;

-- CHECK: auditoria_chaves_nulas
-- TYPE: failing_rows
SELECT * FROM staging.auditoria 
WHERE empresa IS NULL OR periodo IS NULL OR numero_documento IS NULL;

-- CHECK: formato_periodo_invalido_auditoria
-- TYPE: failing_rows
SELECT empresa, periodo, numero_documento 
FROM staging.auditoria 
WHERE periodo NOT LIKE '__/____';

-- CHECK: unicidade_auditoria
-- TYPE: failing_rows
SELECT empresa, periodo, numero_documento, COUNT(*) as qtd
FROM staging.auditoria 
GROUP BY empresa, periodo, numero_documento 
HAVING COUNT(*) > 1;

-- CHECK: completude_auditoria_status
-- TYPE: threshold
-- METRIC_QUERY: SELECT (COUNT(CASE WHEN status IS NULL THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) FROM staging.auditoria;
-- THRESHOLD_KEY: max_null_percent_auditoria_status
-- OPERATOR: <=

/* --- STAGING.RET --- */

-- CHECK: ret_quantidade_invalida
-- TYPE: failing_rows
SELECT empresa, periodo, quantidade, status 
FROM staging.ret 
WHERE quantidade <= 0 OR quantidade IS NULL;

-- CHECK: ret_valor_unitario_nulo_com_quantidade
-- TYPE: failing_rows
SELECT empresa, periodo, quantidade, valor_unitario 
FROM staging.ret 
WHERE quantidade > 0 AND valor_unitario IS NULL;

-- CHECK: ret_duplicatas
-- TYPE: failing_rows
SELECT empresa, periodo, quantidade, COUNT(*) as qtd 
FROM staging.ret 
GROUP BY empresa, periodo, quantidade 
HAVING COUNT(*) > 1;

-- CHECK: ret_status_pendente_limite
-- TYPE: threshold
-- METRIC_QUERY: SELECT (COUNT(CASE WHEN status = 'PENDENTE' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) FROM staging.ret;
-- THRESHOLD_KEY: max_percent_ret_pendente
-- OPERATOR: <=

/* --- STAGING.PMPV_AGREGADOS --- */

-- CHECK: pmpv_valores_negativos
-- TYPE: failing_rows
SELECT periodo, pmpv, preco_final 
FROM staging.pmpv_agregados 
WHERE pmpv < 0 OR preco_final < 0;

-- CHECK: pmpv_logica_preco_final
-- TYPE: failing_rows
SELECT periodo, pmpv, preco_final 
FROM staging.pmpv_agregados 
WHERE preco_final < pmpv;

-- CHECK: pmpv_periodos_duplicados
-- TYPE: failing_rows
SELECT periodo, COUNT(*) as qtd 
FROM staging.pmpv_agregados 
GROUP BY periodo 
HAVING COUNT(*) > 1;

-- CHECK: pmpv_variacao_mensal_extrema
-- TYPE: threshold
-- METRIC_QUERY: SELECT COALESCE(MAX(abs_var), 0) FROM (SELECT ABS(pmpv - LAG(pmpv) OVER (ORDER BY periodo)) / NULLIF(LAG(pmpv) OVER (ORDER BY periodo), 0) * 100 AS abs_var FROM staging.pmpv_agregados) sub;
-- THRESHOLD_KEY: max_volume_variance_percent
-- OPERATOR: <=

/* --- STAGING.CGF --- */

-- CHECK: cgf_volume_logica
-- TYPE: failing_rows
SELECT empresa, periodo, volume_inicial_cgf, volume_final_cgf 
FROM staging.cgf 
WHERE volume_final_cgf < volume_inicial_cgf;

-- CHECK: cgf_tipo_operacao_invalido
-- TYPE: failing_rows
SELECT empresa, periodo, tipo_operacao 
FROM staging.cgf 
WHERE tipo_operacao NOT IN ('ENTRADA', 'SAIDA', 'AJUSTE');

-- CHECK: cgf_data_futura
-- TYPE: failing_rows
SELECT empresa, periodo, data_registro 
FROM staging.cgf 
WHERE data_registro > CURRENT_DATE;

-- CHECK: cgf_gaps_volume_final
-- TYPE: threshold
-- METRIC_QUERY: SELECT (COUNT(CASE WHEN volume_final_cgf IS NULL OR volume_final_cgf = 0 THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)) FROM staging.cgf;
-- THRESHOLD_KEY: max_percent_cgf_gaps
-- OPERATOR: <=

/* --- CROSS-TABELAS (CONSISTENCY CHECKS) --- */

-- CHECK: cross_empresa_auditoria_em_cgf
-- TYPE: failing_rows
SELECT DISTINCT a.empresa 
FROM staging.auditoria a 
LEFT JOIN staging.cgf c ON a.empresa = c.empresa 
WHERE c.empresa IS NULL;

-- CHECK: cross_periodos_invalidos
-- TYPE: failing_rows
SELECT periodo FROM staging.ret WHERE periodo NOT LIKE '__/____'
UNION
SELECT periodo FROM staging.cgf WHERE periodo NOT LIKE '__/____';