# Importa o tema e a tela principal do seu dashboard
from Src.config.ui_theme import configure_theme
from Src.main_dashboard import PlataformaFinanceira

def iniciar_aplicacao():
    # 1. Configura o tema geral
    configure_theme()
    
    # 2. Inicializa a tela principal
    app = PlataformaFinanceira()
    
    # 3. Roda o loop da interface gráfica
    app.mainloop()

# Este bloco garante que o código só roda se o ficheiro for executado diretamente
if __name__ == "__main__":
    iniciar_aplicacao()