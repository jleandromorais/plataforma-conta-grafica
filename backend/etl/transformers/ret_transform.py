import logging


def transformar_dados_ret(dados_brutos:dict ,empresa:str ,periodo:str) -> dict | None:

    """
    Recebe os dados extraídos do PDF de RET, limpa e formata.
    """

    if not dados_brutos or "erro" in dados_brutos:
        return None

    
    try:
        