import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import Image
import os

from Src.config.ui_theme import configure_theme

try:
    from Src.Views.tela_pmpv import TelaPMPV
    from Src.Views.tela_concilia import TelaConciliador
    from Src.Views.tela_ret import TelaRET
    from Src.Views.tela_auditoria import TelaAuditoria
    from Src.Views.tela_scg import TelaSCG
    from Src.Views.tela_cgf import TelaCGF
    from Src.Views.tela_rpv import TelaRPV
    from Src.Views.tela_sr import TelaSR
    from Src.Views.tela_pr import TelaPR
    from Src.Views.tela_pv import TelaPV
    from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado
    from Src.common.excel_final_destino import (
        obter_periodos_trimestre,
        EXCEL_FIXO_PATH,
        EXCEL_FIXO_NOME,
    )
    from Src.Database.database import DatabasePMPV

except ImportError as e:
    print(f"Erro de importação dos módulos da aplicação: {e}")

class PlataformaFinanceira(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configuração da Janela Principal
        self.title("Sistema Integrado de Gestão Financeira")
        self.geometry("1100x700")
        
        # ==================================================
        # 🌟 CÓDIGO DO ÍCONE (SOLUÇÃO DEFINITIVA WINDOWS 11)
        # ==================================================
        pasta_atual = os.path.dirname(os.path.abspath(__file__))
        try:
            # TRUQUE DE MESTRE: Força o Windows a reconhecer como App próprio e não como um script Python
            import ctypes
            myappid = 'minha.plataforma.financeira.1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            
            # Caminho do ficheiro .ico (Certifica-te que descarregaste do site e não foi o gerado pelo código anterior)
            caminho_ico = os.path.join(pasta_atual, 'assets', 'icone.ico')
            self.iconbitmap(caminho_ico)
        except Exception as e:
            print(f"Aviso: Ícone não encontrado -> {e}")
        # ==================================================

        # Grid Layout (2 colunas)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === 1. MENU LATERAL ESQUERDO ===
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        
        # ==================================================
        # 🌟 TÍTULO DO MENU COM A IMAGEM DO DINHEIRO (.PNG)
        # ==================================================
        try:
            caminho_png = os.path.join(pasta_atual, 'assets', 'icons8-cash-94.png')
            img_logo = ctk.CTkImage(light_image=Image.open(caminho_png), size=(35, 35))
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text=" FINANÇAS PRO", 
                                         image=img_logo, compound="left",
                                         font=ctk.CTkFont(size=20, weight="bold"))
        except Exception as e:
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="FINANÇAS PRO", 
                                         font=ctk.CTkFont(size=24, weight="bold"))
        
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))
        # ==================================================

        # --- LISTA DE DADOS PARA OS BOTÕES DO MENU LATERAL ---
        botoes_menu = [
            {"text": "🏠 Início", "command": self.mostrar_inicio},
            {"text": "1️⃣ Módulo PMPV", "command": self.abrir_pmpv},
            {"text": "📄 Conciliação RP", "command": self.abrir_ocr},
            {"text": "⚡ Sistema RET", "command": self.abrir_ret},
            {"text": "🔍 Auditoria XML", "command": self.abrir_auditoria},
            {"text": "📋 Volume CGF", "command": self.abrir_cgf},
            {"text": "🧾 RPV (CGR − CGF)", "command": self.abrir_rpv, "fg_color": "#f59e0b", "hover_color": "#d97706", "text_color": "black"},
            {"text": "📈 SR (Volume Prospectivo − VF) × PR", "command": self.abrir_sr},
            {"text": "💼 Consolidação SCG", "command": self.abrir_scg, "fg_color": "#8b5cf6", "hover_color": "#7c3aed"},
            {"text": "💡 PR Final (SGR+SR)/VP", "command": self.abrir_pr, "fg_color": "#0e7490", "hover_color": "#0891b2"},
            {"text": "💰 PV Final (PMPV+PR)", "command": self.abrir_pv, "fg_color": "#15803d", "hover_color": "#16a34a"},
            {"text": "9️⃣ Excel Final Consolidado", "command": self.exportar_relatorio_consolidado, "fg_color": "#16a085", "hover_color": "#1abc9c"},
        ]

        # --- LAÇO FOR: CRIANDO OS BOTÕES DO MENU ---
        for i, config in enumerate(botoes_menu, start=1):
            texto = config.pop("text")
            comando = config.pop("command")
            btn = ctk.CTkButton(self.sidebar_frame, text=texto, command=comando, **config)
            btn.grid(row=i, column=0, padx=20, pady=10)

        # Configura a última linha do menu para expandir
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
        
        # Configurar grid 4x3
        for i in range(4):
            frame_cards.grid_rowconfigure(i, weight=1)
        for i in range(3):
            frame_cards.grid_columnconfigure(i, weight=1)
        
        # --- LISTA DE DADOS PARA OS CARDS DO MENU INICIAL ---
        dados_dos_cards = [
            {"linha": 0, "coluna": 0, "titulo": "📊 Módulo PMPV", "desc": "Cálculo trimestral\ncom Volume Prospectivo", "comando": self.abrir_pmpv},
            {"linha": 0, "coluna": 1, "titulo": "📄 Conciliação RP", "desc": "Subtração entre  \nReceita - Despesa das penalidades \nde PDFs via OCR", "comando": self.abrir_ocr},
            {"linha": 0, "coluna": 2, "titulo": "⚡ Sistema RET", "desc": "Processamento\nde encargos e NFs \nSoma de encargos", "comando": self.abrir_ret},
            {"linha": 1, "coluna": 2, "titulo": "🔍 Auditoria CGR", "desc": "Notas fiscais \n dos supridores e auditoria \n de PDF via OCR", "comando": self.abrir_auditoria},
            {"linha": 1, "coluna": 1, "titulo": "📋 Volume CGF", "desc": "Somatório de volume\nFaturada - Canceladas\n- Devoluções", "comando": self.abrir_cgf},
            {"linha": 1, "coluna": 0, "titulo": "🧾 RPV", "desc": "Requisição de\nPequeno Valor\nCGR − CGF", "comando": self.abrir_rpv},
            {"linha": 2, "coluna": 0, "titulo": "💼 Consolidação SCG", "desc": "Cálculo final\nSCG = RPV+RET+RP", "comando": self.abrir_scg},
            {"linha": 2, "coluna": 1, "titulo": "📈 SR", "desc": "(Volume Prospectivo − VF) × PR\nSaldo regulatório", "comando": self.abrir_sr},
            {"linha": 2, "coluna": 2, "titulo": "9️⃣ Excel Final", "desc": "Exporta todos os módulos\nem um único Excel\nconsolidado", "comando": self.exportar_relatorio_consolidado},
            {"linha": 3, "coluna": 0, "titulo": "💡 PR Final", "desc": "Preço Regulatório Final\n(SGR + SR) / VP\npor período", "comando": self.abrir_pr},
            {"linha": 3, "coluna": 1, "titulo": "💰 PV Final", "desc": "Preço final da conta gráfica\nPMPV + PR\npor período", "comando": self.abrir_pv},
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
            self._limpar_area_principal()
            TelaPMPV(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Módulo PMPV não encontrado/importado.\n{e}")

    def abrir_ocr(self):
        try:
            self._limpar_area_principal()
            TelaConciliador(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir Conciliação: {e}")
            
    def abrir_ret(self):
        try:
            self._limpar_area_principal()
            TelaRET(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir RET: {e}")

    def abrir_auditoria(self):
        try:
            self._limpar_area_principal()
            TelaAuditoria(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir Auditoria: {e}")

    def abrir_scg(self):
        try:
            self._limpar_area_principal()
            TelaSCG(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir SCG: {e}")

    def abrir_cgf(self):
        try:
            self._limpar_area_principal()
            TelaCGF(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir CGF: {e}")

    def abrir_rpv(self):
        try:
            self._limpar_area_principal()
            TelaRPV(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir RPV: {e}")

    def abrir_sr(self):
        try:
            self._limpar_area_principal()
            TelaSR(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir SR: {e}")

    def abrir_pr(self):
        try:
            self._limpar_area_principal()
            TelaPR(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir PR: {e}")

    def abrir_pv(self):
        try:
            self._limpar_area_principal()
            TelaPV(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir PV: {e}")

    def exportar_relatorio_consolidado(self):
        """Gera/atualiza o Excel fixo consolidado. Sempre sobrescreve o mesmo arquivo."""
        periodo_resultado: list[str | None] = [None]
        cancelado: list[bool] = [False]

        modal = ctk.CTkToplevel(self)
        modal.title("Exportar Excel Final (Módulo 9)")
        modal.geometry("520x240")
        modal.resizable(False, False)
        modal.transient(self)
        modal.grab_set()

        ctk.CTkLabel(
            modal,
            text="Exportar Excel Final Consolidado",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(pady=(16, 6), padx=16, anchor="w")

        ctk.CTkLabel(
            modal,
            text="Período principal (ex: Abr/2026). Deixe vazio para incluir tudo:",
            font=ctk.CTkFont(size=12),
        ).pack(pady=(0, 6), padx=16, anchor="w")

        entry = ctk.CTkEntry(modal, placeholder_text="Ex.: Abr/2026")
        entry.pack(fill="x", padx=16, pady=(0, 4))
        entry.focus_set()

        info_lbl = ctk.CTkLabel(modal, text="", text_color="#ff6b6b", font=ctk.CTkFont(size=11))
        info_lbl.pack(fill="x", padx=16, pady=(0, 4), anchor="w")

        ctk.CTkLabel(
            modal,
            text=f"Arquivo: {Path(EXCEL_FIXO_PATH).name}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(padx=16, anchor="w")

        btn_frame = ctk.CTkFrame(modal)
        btn_frame.pack(side="bottom", fill="x", pady=12)

        def on_ok():
            texto = entry.get().strip()
            periodo_resultado[0] = texto if texto else None
            modal.destroy()

        def on_cancel():
            cancelado[0] = True
            modal.destroy()

        ctk.CTkButton(btn_frame, text="Cancelar", command=on_cancel, width=120).pack(side="right", padx=12)
        ctk.CTkButton(btn_frame, text="Exportar", command=on_ok, width=120, fg_color="#16a085").pack(side="right")

        modal.wait_window()

        if cancelado[0]:
            return

        try:
            periodo_filtro = periodo_resultado[0]

            periodos_trimestre = obter_periodos_trimestre(periodo_filtro) if periodo_filtro else None

            arquivo = ExcelConsolidado.exportar(
                periodo=periodo_filtro,
                nome_arquivo=EXCEL_FIXO_PATH,
                periodos_trimestre=periodos_trimestre,
            )
            messagebox.showinfo(
                "Excel Exportado ✅",
                f"Relatório atualizado com sucesso!\n\n📁 {Path(arquivo).name}\n\n"
                "O arquivo foi aberto automaticamente.",
            )
        except Exception as e:
            messagebox.showerror("Erro ao Exportar", f"Não foi possível gerar o relatório:\n{e}")

    