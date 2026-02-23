import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image
import os

# Importando os módulos
try:
    from modulo_pmpv import CalculadoraTrimestralPMPV
    from modulo_concilia_RP import AppConciliador
    from modulo_ret import SistemaRET
    from modulo_auditoria_CGR import AppAuditoriaXML
    from modulo_scg import ModuloSCG
    from modulo_cgf import CGFApp
    from modulo_rpv import ModuloRPV
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
        self.sidebar_frame.grid_rowconfigure(9, weight=1)  # Linha APÓS os botões expande

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

        self.btn_ocr = ctk.CTkButton(self.sidebar_frame, text="📄 Conciliação RP", 
                                   command=self.abrir_ocr)
        self.btn_ocr.grid(row=3, column=0, padx=20, pady=10)

        self.btn_ret = ctk.CTkButton(self.sidebar_frame, text="⚡ Sistema RET", 
                                    command=self.abrir_ret)
        self.btn_ret.grid(row=4, column=0, padx=20, pady=10)

        self.btn_auditoria = ctk.CTkButton(self.sidebar_frame, text="🔍 Auditoria XML", 
                                    command=self.abrir_auditoria)
        self.btn_auditoria.grid(row=5, column=0, padx=20, pady=10)

        self.btn_cgf = ctk.CTkButton(self.sidebar_frame, text="📋 Volume CGF",
                                     command=self.abrir_cgf)
        self.btn_cgf.grid(row=6, column=0, padx=20, pady=10)

        self.btn_rpv = ctk.CTkButton(self.sidebar_frame, text="🧾 RPV (CGR − CGF)",
                                     command=self.abrir_rpv,
                                     fg_color="#f59e0b", hover_color="#d97706",
                                     text_color="black")
        self.btn_rpv.grid(row=7, column=0, padx=20, pady=10)

        self.btn_scg = ctk.CTkButton(self.sidebar_frame, text="💼 Consolidação SCG",
                                     command=self.abrir_scg,
                                     fg_color="#8b5cf6", hover_color="#7c3aed")
        self.btn_scg.grid(row=8, column=0, padx=20, pady=10)

        # === 2. ÁREA PRINCIPAL (DIREITA) ===
        self.main_area = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.mostrar_inicio()

    def mostrar_inicio(self):
        self._limpar_area_principal()
        
        # Título (mantém no topo)
        lbl_titulo = ctk.CTkLabel(self.main_area, text="Bem-vindo ao Sistema", 
                                font=ctk.CTkFont(size=32, weight="bold"))
        lbl_titulo.pack(pady=(30, 20))  # Mantém pack para ficar no topo
        
        # FRAME GRID (aqui vai o grid 3x3)
        frame_cards = ctk.CTkFrame(self.main_area, fg_color="transparent")
        frame_cards.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Configurar grid 3x3 (cada célula com peso igual)
        for i in range(3):  # 3 linhas
            frame_cards.grid_rowconfigure(i, weight=1)
        for j in range(3):  # 3 colunas
            frame_cards.grid_columnconfigure(j, weight=1)
        
        # Criar 9 cards (3x3)
        # Linha 0
        self._criar_card_grid(frame_cards, "📊 Gestão PMPV", 
                            "Cálculo trimestral\nde contratos de gás", 
                            self.abrir_pmpv, 0, 0)
        
        self._criar_card_grid(frame_cards, "📄 Conciliação RP", 
                            "Subrtação entre  \n  Recceita - Dispesa das penalalidades \nde PDFs via OCR", 
                            self.abrir_ocr, 0, 1)
        
        self._criar_card_grid(frame_cards, "⚡ Sistema RET", 
                            "Processamento\nde encargos e NFs \n Soma de encargos ", 
                            self.abrir_ret, 0, 2)
        
        # Linha 1
        self._criar_card_grid(frame_cards, "🔍 Auditoria XML e soma  CGR", 
                            "NF-e e CT-e\ncomparação com Excel", 
                            self.abrir_auditoria, 1, 0)
        
        self._criar_card_grid(frame_cards, "💼 Consolidação SCG", 
                            "Cálculo final\nSCG = RPV(CGR+CGF)+RET+RP", 
                            self.abrir_scg, 1, 1)
        
        self._criar_card_grid(frame_cards, "📋 Volume CGF",
                            "Somatório de volume\nFaturada - Canceladas\n- Devoluções",
                            self.abrir_cgf, 1, 2)
        
        # Linha 2
        self._criar_card_grid(frame_cards, "🧾 RPV",
                            "Requisição de\nPequeno Valor\nCGR − CGF",
                            self.abrir_rpv, 2, 0)
        
        self._criar_card_grid(frame_cards, "⚙️ Módulo 8", 
                            "Descrição do\noitavo módulo", 
                            None, 2, 1)
        
        self._criar_card_grid(frame_cards, "📁 Módulo 9", 
                            "Descrição do\nnono módulo", 
                            None, 2, 2)

    def _criar_card(self, parent, titulo, desc, comando, lado):
        card = ctk.CTkFrame(parent, width=300, height=150)
        card.pack(side=lado, padx=10, expand=True, fill="both")
        
        ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20,5))
        ctk.CTkLabel(card, text=desc).pack(pady=5)
        ctk.CTkButton(card, text="Acessar", command=comando).pack(pady=15)
 
 
    def _criar_card_grid(self, parent, titulo, desc, comando, linha, coluna):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=linha, column=coluna, padx=10, pady=10, sticky="nsew")
        
        #Conteudo card
        
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

    # --- INTEGRAÇÃO COM SEUS CÓDIGOS ANTIGOS ---
    
    def abrir_pmpv(self):
        try:
            self._janela_pmpv = CalculadoraTrimestralPMPV(self)
            self._janela_pmpv.geometry("1300x800")
            self._janela_pmpv.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Módulo PMPV não encontrado/importado.\n{e}")

    def abrir_ocr(self):
        try:
            self._janela_ocr = AppConciliador(self)
            self._janela_ocr.lift()
        except Exception as e:
            messagebox.showerror("Erro", f"Módulo Conciliação não encontrado/importado.\n{e}")

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

if __name__ == "__main__":
    app = PlataformaFinanceira()
    app.mainloop()