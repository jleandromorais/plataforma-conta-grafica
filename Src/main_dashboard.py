import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import os

from Src.config.ui_theme import configure_theme

try:
    from Src.Views.tela_pmpv import TelaPMPV
    from Src.Views.tela_concilia import TelaConciliador
    from Src.Modules.modulo_ret import SistemaRET
    from Src.Modules.modulo_auditoria_CGR import AppAuditoriaXML
    from Src.Modules.modulo_scg import ModuloSCG
    from Src.Modules.modulo_cgf import CGFApp
    from Src.Modules.modulo_rpv import ModuloRPV
except ImportError as e:
    print(f"Erro de importação dos módulos da aplicação: {e}")

class PlataformaFinanceira(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuração da Janela Principal
        self.title("Sistema Integrado de Gestão Financeira")
        self.geometry("1100x700")
        
        # Grid Layout (2 colunas)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 1. MENU LATERAL ESQUERDO ===
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        # Título do Menu
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="FINANÇAS PRO", 
                                     font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # --- LISTA DE DADOS PARA OS BOTÕES DO MENU LATERAL ---
        botoes_menu = [
            {"text": "🏠 Início", "command": self.mostrar_inicio},
            {"text": "📊 Gestão PMPV", "command": self.abrir_pmpv},
            {"text": "📄 Conciliação RP", "command": self.abrir_ocr},
            {"text": "⚡ Sistema RET", "command": self.abrir_ret},
            {"text": "🔍 Auditoria XML", "command": self.abrir_auditoria},
            {"text": "📋 Volume CGF", "command": self.abrir_cgf},
            {"text": "🧾 RPV (CGR − CGF)", "command": self.abrir_rpv, "fg_color": "#f59e0b", "hover_color": "#d97706", "text_color": "black"},
            {"text": "💼 Consolidação SCG", "command": self.abrir_scg, "fg_color": "#8b5cf6", "hover_color": "#7c3aed"}
        ]

        # --- LAÇO FOR: CRIANDO OS BOTÕES DO MENU ---
        # enumerate nos ajuda a obter o índice 'i' para gerir o número da linha (row) dinamicamente.
        for i, config in enumerate(botoes_menu, start=1):
            # Extraímos texto e comando obrigatórios
            texto = config.pop("text")
            comando = config.pop("command")
            
            # O restante de `config` (se tiver cores personalizadas) é passado usando **config
            btn = ctk.CTkButton(self.sidebar_frame, text=texto, command=comando, **config)
            btn.grid(row=i, column=0, padx=20, pady=10)

        # Configura a última linha do menu para expandir (empurrando elementos para cima)
        self.sidebar_frame.grid_rowconfigure(len(botoes_menu) + 1, weight=1)

        # === 2. ÁREA PRINCIPAL (DIREITA) ===
        self.main_area = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.mostrar_inicio()

    def mostrar_inicio(self):
        self._limpar_area_principal()
        
        # Título (mantém no topo)
        lbl_titulo = ctk.CTkLabel(self.main_area, text="Bem-vindo ao Sistema", 
                                font=ctk.CTkFont(size=32, weight="bold"))
        lbl_titulo.pack(pady=(30, 20))  
        
        # FRAME GRID
        frame_cards = ctk.CTkFrame(self.main_area, fg_color="transparent")
        frame_cards.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configurar grid 3x3
        for i in range(3):  
            frame_cards.grid_rowconfigure(i, weight=1)
            frame_cards.grid_columnconfigure(i, weight=1)
        
        # --- LISTA DE DADOS PARA OS CARDS DO MENU INICIAL ---
        dados_dos_cards = [
            {"linha": 0, "coluna": 0, "titulo": "📊 Gestão PMPV", "desc": "Cálculo trimestral\nde contratos de gás", "comando": self.abrir_pmpv},
            {"linha": 0, "coluna": 1, "titulo": "📄 Conciliação RP", "desc": "Subtração entre  \nReceita - Despesa das penalidades \nde PDFs via OCR", "comando": self.abrir_ocr},
            {"linha": 0, "coluna": 2, "titulo": "⚡ Sistema RET", "desc": "Processamento\nde encargos e NFs \nSoma de encargos", "comando": self.abrir_ret},
            {"linha": 1, "coluna": 0, "titulo": "🔍 Auditoria XML e soma CGR", "desc": "NF-e e CT-e\ncomparação com Excel", "comando": self.abrir_auditoria},
            {"linha": 1, "coluna": 1, "titulo": "💼 Consolidação SCG", "desc": "Cálculo final\nSCG = RPV(CGR+CGF)+RET+RP", "comando": self.abrir_scg},
            {"linha": 1, "coluna": 2, "titulo": "📋 Volume CGF", "desc": "Somatório de volume\nFaturada - Canceladas\n- Devoluções", "comando": self.abrir_cgf},
            {"linha": 2, "coluna": 0, "titulo": "🧾 RPV", "desc": "Requisição de\nPequeno Valor\nCGR − CGF", "comando": self.abrir_rpv},
            {"linha": 2, "coluna": 1, "titulo": "⚙️ Módulo 8", "desc": "Descrição do\noitavo módulo", "comando": None},
            {"linha": 2, "coluna": 2, "titulo": "📁 Módulo 9", "desc": "Descrição do\nnono módulo", "comando": None}
        ]

        # --- LAÇO FOR: CRIANDO OS CARDS ---
        for card in dados_dos_cards:
            self._criar_card_grid(
                parent=frame_cards,
                titulo=card["titulo"],
                desc=card["desc"],
                comando=card["comando"],
                linha=card["linha"],
                coluna=card["coluna"]
            )

    def _criar_card_grid(self, parent, titulo, desc, comando, linha, coluna):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=linha, column=coluna, padx=10, pady=10, sticky="nsew")
        
        # Conteúdo do card
        ctk.CTkLabel(card, text=titulo, 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 10))
        
        ctk.CTkLabel(card, text=desc, 
                    font=ctk.CTkFont(size=12), 
                    text_color="gray").pack(pady=5)
        
        # Botão (apenas se comando existir)
        if comando:
            ctk.CTkButton(card, text="Abrir", 
                        command=comando,
                        width=100).pack(pady=(10, 20))
        else:
            # Placeholder para módulos futuros
            ctk.CTkLabel(card, text="Em breve", 
                        text_color="gray50",
                        font=ctk.CTkFont(size=11, slant="italic")).pack(pady=(10, 20))
            
    def _limpar_area_principal(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

    # --- MÉTODOS DE INTEGRAÇÃO (Abertura de Janelas) ---
    def abrir_pmpv(self):
        try:
            self._janela_pmpv = TelaPMPV(self)
            self._janela_pmpv.geometry("1300x800")
            self._janela_pmpv.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Módulo PMPV não encontrado/importado.\n{e}")

    def abrir_ocr(self):
        try:
            # Mudamos de AppConciliador para TelaConciliador
            self._janela_ocr = TelaConciliador(self)
            self._janela_ocr.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir Conciliação: {e}")
    def abrir_ret(self):
        try:
            self._janela_ret = SistemaRET(self)
            self._janela_ret.geometry("1400x900")
            self._janela_ret.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Módulo RET não encontrado/importado.\n{e}")

    def abrir_auditoria(self):
        try:
            self._janela_auditoria = AppAuditoriaXML(self)
            self._janela_auditoria.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Módulo Auditoria não encontrado/importado.\n{e}")

    def abrir_scg(self):
        try:
            self._janela_scg = ModuloSCG(self)
            self._janela_scg.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir SCG: {e}")

    def abrir_cgf(self):
        try:
            self._janela_cgf = CGFApp(self)
            self._janela_cgf.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir CGF: {e}")

    def abrir_rpv(self):
        try:
            self._janela_rpv = ModuloRPV(self)
            self._janela_rpv.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir RPV: {e}")

