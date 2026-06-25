# Importa o tema e a tela principal do seu dashboard
import logging

from Src.config.logging_config import configurar_logging
from Src.config.ui_theme import configure_theme
from Src.main_dashboard import PlataformaFinanceira

logger = logging.getLogger(__name__)

def iniciar_aplicacao():
    # 0. Configura o logging (arquivo logs/app.log) antes de tudo
    arquivo_log = configurar_logging()
    logger.info("Iniciando GraphAccount Pro — log em %s", arquivo_log)

    # 1. Configura o tema geral
    configure_theme()

    # 2. Inicializa a tela principal
    app = PlataformaFinanceira()

    # 3. Roda o loop da interface gráfica
    try:
        app.mainloop()
    except Exception:
        # Qualquer erro não tratado que derrube a UI fica registrado no log.
        logger.exception("Erro não tratado no loop principal da aplicação")
        raise

# Este bloco garante que o código só roda se o ficheiro for executado diretamente
if __name__ == "__main__":
    iniciar_aplicacao()
