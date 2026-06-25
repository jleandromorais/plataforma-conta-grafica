import logging

def transformar_concilia(dados_brutos: dict, categoria: str) -> dict | None:
    """
    Analisa os dados brutos de conciliação e categoriza o status do ficheiro.
    """
    if not dados_brutos or "erro" in dados_brutos:
        return None

    try:
        arquivo_origem = str(dados_brutos.get("file_name", "Desconhecido")).strip()
        valor_detectado = float(dados_brutos.get("amount", 0.0))
        metodo = str(dados_brutos.get("method", "Desconhecido")).strip()

        # Regra de negócio: Se o valor é 0 ou anormalmente baixo/negativo, marca para revisão
        if valor_detectado <= 0:
            status = "REVISAO_MANUAL"
            valor_detectado = 0.0
        else:
            status = "VALIDADO"

        return {
            "arquivo_origem": arquivo_origem,
            "categoria_documento": categoria,
            "valor_conciliado": round(valor_detectado, 2),
            "metodo_leitura": metodo,
            "status_conciliacao": status
        }

    except Exception as e:
        logging.error(f"Erro ao transformar dados de Conciliação: {e}")
        return None