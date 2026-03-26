from pathlib import Path
from Src.Services.servicos_auditoria import RegrasAuditoria


def extrair_xml(caminho: Path) -> dict | None:
    """
    Extrai dados de um XML fiscal (NF-e ou CT-e).
    Retorna dict com os campos brutos, ou None se não for válido.
    """
    tipo = RegrasAuditoria.detectar_tipo_xml(caminho)

    if tipo == 'nfe':
        return RegrasAuditoria.parse_nfe(caminho)
    elif tipo == 'cte':
        return RegrasAuditoria.parse_cte(caminho)
    else:
        return None

 