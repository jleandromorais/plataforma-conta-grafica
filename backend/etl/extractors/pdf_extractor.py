import logging
from pathlib import Path

# Correção das importações: agora importamos as classes corretas dos seus respetivos ficheiros
from Src.Services.servicos_ret import RegrasRET
from Src.Services.servicos_concilia import RegrasConcilia

# Configuração básica de logging (num projeto maior, isto fica num ficheiro config.py)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def extrair_pdf_ret(caminho: Path) -> dict | None:
    """
    Extrai dados de encargos (RET) de um ficheiro PDF.
    """
    try:
        resultado = RegrasRET.extrair_dados_pdf(str(caminho))
        
        if resultado and "erro" not in resultado:
            return resultado
        elif resultado and "erro" in resultado:
            logging.warning(f"Aviso ao processar RET {caminho.name}: {resultado['erro']}")
            
    except Exception as e:
        # Em vez de 'pass', registamos o erro exato
        logging.error(f"Erro inesperado ao extrair RET de {caminho.name}: {e}")
        
    return None

def extrair_pdf_concilia(caminho: Path) -> dict | None:
    """
    Extrai dados de conciliação de um ficheiro PDF.
    """
    try:
        # Corrigido: Estava 'RegrasRET', agora chama corretamente a 'RegrasConcilia'
        resultado = RegrasConcilia.extrair_dados_pdf(str(caminho))
        
        if resultado and "erro" not in resultado:
            return resultado
        elif resultado and "erro" in resultado:
            logging.warning(f"Aviso ao processar Conciliação {caminho.name}: {resultado['erro']}")
            
    except Exception as e:
        logging.error(f"Erro inesperado ao extrair Conciliação de {caminho.name}: {e}")
        
    return None