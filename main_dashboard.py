import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import os

# Importando os teus módulos (vamos adaptar eles no passo 4)
# Nota: Estou assumindo que renomeaste os arquivos originais
try:
    from modulo_pmpv import CalculadoraTrimestralPMPV
    from modulo_concilia import AppConciliador
except ImportError as e:
    print(f"Erro de importação: {e}")

# Configuração Visual Global
ctk.set_appearance_mode("Dark")  # Modos: "System", "Dark", "Light"
ctk.set_default_color_theme("blue")  # Temas: "blue", "green", "dark-blue"

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
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        # Título do Menu
        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="FINANÇAS PRO", 
                                     font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Botões do Menu
        self.btn_dashboard = ctk.CTkButton(self.sidebar_frame, text="🏠 Início", 
                                         command=self.mostrar_inicio)
        self.btn_dashboard.grid(row=1, column=0, padx=20, pady=10)

        self.btn_pmpv = ctk.CTkButton(self.sidebar_frame, text="📊 Gestão PMPV", 
                                    command=self.abrir_pmpv)
        self.btn_pmpv.grid(row=2, column=0, padx=20, pady=10)

        self.btn_ocr = ctk.CTkButton(self.sidebar_frame, text="📄 Conciliação PDF", 
                                   command=self.abrir_ocr)
        self.btn_ocr.grid(row=3, column=0, padx=20, pady=10)

        # === 2. ÁREA PRINCIPAL (DIREITA) ===
        self.main_area = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.mostrar_inicio()

    def mostrar_inicio(self):
        self._limpar_area_principal()
        
        # Título de Boas-vindas
        lbl_titulo = ctk.CTkLabel(self.main_area, text="Bem-vindo ao Sistema", 
                                font=ctk.CTkFont(size=32, weight="bold"))
        lbl_titulo.pack(pady=(50, 20))
        
        # Cards de Atalho
        frame_cards = ctk.CTkFrame(self.main_area, fg_color="transparent")
        frame_cards.pack(fill="x", padx=50)
        
        # Card PMPV
        self._criar_card(frame_cards, "Cálculo PMPV", 
                        "Gestão trimestral de contratos de gás\ne cálculo de preço médio.", 
                        self.abrir_pmpv, "left")
        
        # Card OCR
        self._criar_card(frame_cards, "Leitor de PDF", 
                        "Extração automática de valores\nde faturas via OCR e IA.", 
                        self.abrir_ocr, "right")

    def _criar_card(self, parent, titulo, desc, comando, lado):
        card = ctk.CTkFrame(parent, width=300, height=150)
        card.pack(side=lado, padx=10, expand=True, fill="both")
        
        ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20,5))
        ctk.CTkLabel(card, text=desc).pack(pady=5)
        ctk.CTkButton(card, text="Acessar", command=comando).pack(pady=15)

    def _limpar_area_principal(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

    # --- INTEGRAÇÃO COM SEUS CÓDIGOS ANTIGOS ---
    
    def abrir_pmpv(self):
        """Abre o teu código de PMPV dentro de uma nova janela"""
        nova_janela = ctk.CTkToplevel(self)
        nova_janela.title("Gestão PMPV - Trimestral")
        nova_janela.geometry("1300x800")
        nova_janela.attributes('-topmost', True) # Mantém na frente
        
        # Aqui chamamos a TUA classe antiga, passando a nova janela como 'root'
        try:
            app = CalculadoraTrimestralPMPV(nova_janela)
        except NameError:
            messagebox.showerror("Erro", "Módulo PMPV não encontrado/importado.")

    def abrir_ocr(self):
        """Abre o teu código de Conciliação PDF"""
        try:
            # Instancia a tua classe de OCR (adaptada)
            app = AppConciliador()
            app.mainloop()
        except NameError:
            messagebox.showerror("Erro", "Módulo OCR não encontrado/importado.")

if __name__ == "__main__":
    app = PlataformaFinanceira()
    app.mainloop()