"""
Configuração central de logging do GraphAccount Pro.

Antes, dezenas de blocos `except` engoliam o erro silenciosamente — quando
algo falhava na máquina do usuário, não havia rastro nenhum. Aqui criamos um
arquivo de log rotativo (`logs/app.log`) para registrar o que acontece e,
principalmente, o que dá errado.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from Src.common.app_paths import raiz_aplicacao


def configurar_logging(nivel: int = logging.INFO) -> Path:
    """Configura o logging global (console + arquivo rotativo).

    Deve ser chamada uma única vez, no ponto de entrada da aplicação.
    Retorna o caminho do arquivo de log.
    """
    pasta_logs = raiz_aplicacao() / "logs"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    arquivo_log = pasta_logs / "app.log"

    formato = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(nivel)

    # Evita handlers duplicados se a função for chamada mais de uma vez.
    if root.handlers:
        return arquivo_log

    # Arquivo rotativo: 1 MB por arquivo, mantém 5 backups.
    file_handler = RotatingFileHandler(
        arquivo_log, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formato)
    root.addHandler(file_handler)

    # Console (útil em desenvolvimento).
    console = logging.StreamHandler()
    console.setFormatter(formato)
    root.addHandler(console)

    return arquivo_log
