# Importa o tema e a tela principal do seu dashboard
import logging
import sys

TITULO_JANELA = "GraphAccount Pro - Gestão de Conta Gráfica"
_MUTEX_NOME = "Local\\GraphAccountPro_InstanciaUnica"
_mutex_handle = None  # mantido vivo enquanto o app roda

logger = logging.getLogger(__name__)


def _fechar_splash():
    """Fecha a tela de abertura do .exe (PyInstaller); no-op rodando via python."""
    try:
        import pyi_splash  # type: ignore[import-not-found]
        pyi_splash.close()
    except Exception:
        pass


def _ja_esta_aberto() -> bool:
    """Garante uma única cópia do app por usuário.

    Várias cópias abertas gravam no mesmo banco ao mesmo tempo. Se já houver
    uma aberta, traz a janela dela para a frente e retorna True.
    """
    global _mutex_handle
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        kernel32, user32 = ctypes.windll.kernel32, ctypes.windll.user32
        ERROR_ALREADY_EXISTS = 183
        _mutex_handle = kernel32.CreateMutexW(None, False, _MUTEX_NOME)
        if kernel32.GetLastError() != ERROR_ALREADY_EXISTS:
            return False
        hwnd = user32.FindWindowW(None, TITULO_JANELA)
        if hwnd:
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False  # na dúvida, deixa abrir


def _banco_acessivel() -> bool:
    from Src.common.app_paths import caminho_banco
    try:
        caminho = caminho_banco()
        logger.info("Banco de dados: %s", caminho)
        return True
    except FileNotFoundError as e:
        logger.error("Banco não encontrado: %s", e)
        _fechar_splash()
        from tkinter import Tk, messagebox
        raiz = Tk(); raiz.withdraw()
        messagebox.showerror("GraphAccount Pro — banco de dados", str(e), parent=raiz)
        raiz.destroy()
        return False


def iniciar_aplicacao():
    if _ja_esta_aberto():
        _fechar_splash()
        return

    from Src.config.logging_config import configurar_logging
    from Src.config.ui_theme import configure_theme

    # 0. Configura o logging (arquivo logs/app.log) antes de tudo
    arquivo_log = configurar_logging()
    logger.info("Iniciando GraphAccount Pro — log em %s", arquivo_log)

    if not _banco_acessivel():
        return

    from Src.main_dashboard import PlataformaFinanceira

    # 1. Configura o tema geral
    configure_theme()

    # 2. Inicializa a tela principal
    app = PlataformaFinanceira()
    app.after(0, _fechar_splash)

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
