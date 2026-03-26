from pathlib import Path
from Src.Services.servicos_ret import RegrasRET

def extrair_pdf(caminho: Path) -> dict | None:
    



    try:
        resultado = RegrasRET.extrair_dados_pdf(str(caminho))

        if resultado and "erro" not in resultado:
            return resultado

    except Exception:
        pass

    return None


