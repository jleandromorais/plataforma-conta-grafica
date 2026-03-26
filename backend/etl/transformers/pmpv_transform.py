import logging

def transformar_pmpv(dados_brutos_empresas: dict, valor_cg: float, dias_config: dict) -> dict | None:
    """
    Calcula o Volume Final (VF), Custo Total e PMPV a partir dos dados do Excel.
    """
    if not dados_brutos_empresas:
        return None

    custo_total = 0.0
    volume_total_vf = 0.0
    vp_total = 0.0
    registos_empresas = []

    try:
        for empresa, dados in dados_brutos_empresas.items():
            dias = dias_config.get(empresa, 30)
            
            mol = abs(float(dados.get('mol', 0.0)))
            trans = abs(float(dados.get('trans', 0.0)))
            log = abs(float(dados.get('log', 0.0)))
            vol = abs(float(dados.get('volume', 0.0)))

            if vol <= 0:
                continue

            # Regras de Negócio PMPV
            preco_referencia = mol + trans + log
            volume_faturado_dias = vol * dias
            custo_empresa = preco_referencia * volume_faturado_dias

            custo_total += custo_empresa
            volume_total_vf += volume_faturado_dias
            vp_total += vol

            registos_empresas.append({
                "empresa": empresa,
                "volume_informado": round(vol, 4),
                "dias_faturamento": dias,
                "preco_referencia": round(preco_referencia, 4),
                "custo_gerado": round(custo_empresa, 2)
            })

        if volume_total_vf == 0:
            logging.warning("PMPV: Volume Final resultou em zero. Cálculo abortado.")
            return None

        # Fórmulas finais
        pmpv = custo_total / volume_total_vf
        preco_final = pmpv + valor_cg

        return {
            "agregados": {
                "volume_total_vf": round(volume_total_vf, 4),
                "custo_total": round(custo_total, 2),
                "pmpv": round(pmpv, 4),
                "conta_grafica_inserida": round(valor_cg, 4),
                "preco_final": round(preco_final, 4),
                "volume_programado_mensal": round(vp_total, 4)
            },
            "detalhes_empresas": registos_empresas
        }

    except Exception as e:
        logging.error(f"Erro ao processar as regras matemáticas do PMPV: {e}")
        return None