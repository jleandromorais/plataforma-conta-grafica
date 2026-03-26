import logging

PIS_COFINS_CGR_RATE = 0.0925  # PIS 1,65% + COFINS 7,60% = 9,25%

def transformar_auditoria(dados_brutos: dict, empresa: str) -> dict | None:
    """
    Transforma dados brutos de XML Fiscal e calcula o CGR Líquido.
    """
    if not dados_brutos or "erro" in dados_brutos:
        return None

    try:
        # Extração e garantia de tipo
        tipo = str(dados_brutos.get("tipo", "Desconhecido")).strip()
        numero = str(dados_brutos.get("numero", "N/A")).strip()
        
        valor_total = abs(float(dados_brutos.get("valor_total", 0.0)))
        icms = abs(float(dados_brutos.get("icms", 0.0)))
        pis = abs(float(dados_brutos.get("pis", 0.0)))
        cofins = abs(float(dados_brutos.get("cofins", 0.0)))
        
        # Consolidação do volume (lida com as duas chaves possíveis do extrator)
        volume_total = abs(float(dados_brutos.get("volume_total", dados_brutos.get("volume", 0.0))))

        # Aplicação da regra de negócio: G = (F - ICMS) * (1 - PIS_COFINS_CGR_RATE)
        cgr_liquido = (valor_total - icms) * (1.0 - PIS_COFINS_CGR_RATE)

        return {
            "empresa": empresa,
            "tipo_documento": tipo,
            "numero_documento": numero,
            "valor_bruto": round(valor_total, 2),
            "icms": round(icms, 2),
            "pis": round(pis, 2),
            "cofins": round(cofins, 2),
            "volume_total": round(volume_total, 4),
            "cgr_liquido": round(cgr_liquido, 2),
            "status": "PROCESSADO"
        }

    except Exception as e:
        logging.error(f"Erro ao transformar auditoria do documento {dados_brutos.get('numero')}: {e}")
        return None