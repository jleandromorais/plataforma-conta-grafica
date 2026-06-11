import logging

def transformar_ret(dados_brutos: dict, empresa: str, periodo: str) -> dict | None:
    """
    Limpa e formata os dados extraídos de um PDF de Encargos (RET/EC/EAT).
    """
    if not dados_brutos or "erro" in dados_brutos:
        return None

    try:
        # Extração de strings com limpeza
        tipo_encargo = str(dados_brutos.get('tipo_encargo', 'Outros')).strip()
        nota_tipo = str(dados_brutos.get('nota_tipo', 'N/A')).strip()
        numero_nd = str(dados_brutos.get('numero_nd', '')).strip()
        moeda = str(dados_brutos.get('moeda_detectada', 'BRL')).strip()
        contrib_ec = str(dados_brutos.get('contrib_ec', 'OUTROS')).strip()
        arquivo_origem = str(dados_brutos.get('arquivo', 'Desconhecido')).strip()

        # Extração e validação de valores numéricos
        valor_total = abs(float(dados_brutos.get('valor_total', 0.0)))
        quantidade = abs(float(dados_brutos.get('quantidade', 0.0)))
        valor_unitario = abs(float(dados_brutos.get('valor_unitario', 0.0)))

        # Regra de fallback matemático se o unitário falhou no OCR
        if valor_unitario == 0.0 and quantidade > 0:
            valor_unitario = valor_total / quantidade

        return {
            "empresa": empresa,
            "periodo": periodo,
            "tipo_encargo": tipo_encargo,
            "tipo_nota": nota_tipo,
            "numero_nd": numero_nd,
            "moeda": moeda,
            "valor_total": round(valor_total, 2),
            "quantidade": round(quantidade, 4),
            "valor_unitario": round(valor_unitario, 4),
            "contribuicao_ec": contrib_ec,
            "arquivo_origem": arquivo_origem,
            "status": "PROCESSADO"
        }

    except Exception as e:
        nome_arquivo = dados_brutos.get('arquivo', 'Desconhecido')
        logging.error(f"Erro ao transformar dados do RET (Ficheiro: {nome_arquivo}): {e}")
        return None