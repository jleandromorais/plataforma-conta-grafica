
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import Image
import os

from Src.config.ui_theme import configure_theme
from Src.config import ui_theme as ui

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
    from Src.Views.dashboard_resumo import PainelResumo
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
        self.title("GraphAccount Pro - Gestão de Conta Gráfica")
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
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text=" GraphAccount Pro",
                                         image=img_logo, compound="left",
                                         font=ctk.CTkFont(size=18, weight="bold"))
        except Exception as e:
            self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="GraphAccount Pro",
                                         font=ctk.CTkFont(size=20, weight="bold"))
        
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))
        # ==================================================

        # --- SIDEBAR: agrupado por módulo com cores distintas ---
        # Cada módulo tem uma cor própria para facilitar a orientação visual.
        COR_MOD1 = "#2980b9"       # azul — Módulo 1 PMPV
        COR_MOD1_H = "#1a6fa8"
        COR_MOD2 = "#16a085"       # verde-azulado — Módulo 2 Cálculos Mensais
        COR_MOD2_H = "#0e7060"
        COR_MOD3 = "#8e44ad"       # roxo — Módulo 3 Consolidação Trimestral
        COR_MOD3_H = "#703688"
        COR_EXPORT = "#27ae60"     # verde — Exportação
        COR_EXPORT_H = "#1e8449"

        row = 1

        # Botão Início
        btn_inicio = ctk.CTkButton(
            self.sidebar_frame, text="🏠 Início", command=self.mostrar_inicio,
            fg_color=ui.COR_PRIMARIA, hover_color=ui.COR_PRIMARIA_HOVER, anchor="w",
        )
        btn_inicio.grid(row=row, column=0, padx=ui.ESP_MD, pady=(ui.ESP_SM, 4), sticky="ew")
        row += 1

        def _separador(texto: str, cor: str):
            nonlocal row
            ctk.CTkLabel(
                self.sidebar_frame, text=texto,
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=cor, anchor="w",
            ).grid(row=row, column=0, padx=(ui.ESP_MD + 4, ui.ESP_MD), pady=(10, 2), sticky="ew")
            row += 1

        def _botao(texto: str, comando, cor: str, cor_h: str):
            nonlocal row
            ctk.CTkButton(
                self.sidebar_frame, text=texto, command=comando,
                fg_color=cor, hover_color=cor_h, anchor="w",
            ).grid(row=row, column=0, padx=ui.ESP_MD, pady=2, sticky="ew")
            row += 1

        # ── MÓDULO 1 — PMPV ───────────────────────────
        _separador("── MÓDULO 1  PMPV ──────────────", COR_MOD1)
        _botao("📊 PMPV", self.abrir_pmpv, COR_MOD1, COR_MOD1_H)

        # ── CONTA GRÁFICA ─────────────────────────────
        _separador("── CONTA GRÁFICA ───────────────", COR_MOD2)
        _botao("🔍 Auditoria CGR", self.abrir_auditoria, COR_MOD2, COR_MOD2_H)
        _botao("📋 CGF — Volume Faturado", self.abrir_cgf, COR_MOD2, COR_MOD2_H)
        _botao("🧾 RPV", self.abrir_rpv, COR_MOD2, COR_MOD2_H)
        _botao("📄 RET — Encargos", self.abrir_ret, COR_MOD2, COR_MOD2_H)
        _botao("📑 RP — Conciliação", self.abrir_ocr, COR_MOD2, COR_MOD2_H)
        _botao("💼 SCG — Consolidação", self.abrir_scg, COR_MOD2, COR_MOD2_H)
        _botao("📈 SR — Saldo Regulatório", self.abrir_sr, COR_MOD2, COR_MOD2_H)

        # ── MÓDULO 3 — CONSOLIDAÇÃO ───────────────────
        _separador("── MÓDULO 3  CONSOLIDAÇÃO ──────", COR_MOD3)
        _botao("💡 PR — Preço Regulatório", self.abrir_pr, COR_MOD3, COR_MOD3_H)
        _botao("💰 PV Final", self.abrir_pv, COR_MOD3, COR_MOD3_H)

        # ── EXPORTAÇÃO ────────────────────────────────
        _separador("── EXPORTAÇÃO ──────────────────", COR_EXPORT)
        _botao("📊 Excel Final Consolidado", self.exportar_relatorio_consolidado, COR_EXPORT, COR_EXPORT_H)

        self.sidebar_frame.grid_columnconfigure(0, weight=1)
        linha_espacador = row
        self.sidebar_frame.grid_rowconfigure(linha_espacador, weight=1)

        # Botão de alternar tema claro/escuro (fica no rodapé do menu)
        self.btn_tema = ctk.CTkButton(
            self.sidebar_frame,
            text="☀️ Tema claro" if ui.tema_atual() == "Dark" else "🌙 Tema escuro",
            command=self._alternar_tema,
            fg_color=ui.COR_NEUTRA, hover_color=ui.COR_NEUTRA_HOVER,
        )
        self.btn_tema.grid(row=linha_espacador + 1, column=0, padx=ui.ESP_MD, pady=ui.ESP_MD, sticky="ew")

        # === 2. ÁREA PRINCIPAL (DIREITA) ===
        self.main_area = ctk.CTkFrame(self, corner_radius=10, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        self.mostrar_inicio()

    def _alternar_tema(self):
        """Alterna entre tema claro e escuro e atualiza o rótulo do botão."""
        novo = ui.alternar_tema()
        self.btn_tema.configure(
            text="☀️ Tema claro" if novo == "Dark" else "🌙 Tema escuro"
        )

    def mostrar_inicio(self):
        self._limpar_area_principal()

        # Título (mantém no topo)
        lbl_titulo = ctk.CTkLabel(self.main_area, text="Bem-vindo ao GraphAccount Pro",
                                font=ctk.CTkFont(size=30, weight="bold"))
        lbl_titulo.pack(pady=(24, 4))

        ctk.CTkLabel(
            self.main_area,
            text="Siga os 3 módulos em ordem para montar a conta gráfica trimestral.",
            font=ctk.CTkFont(size=13),
            text_color="gray",
        ).pack(pady=(0, 10))

        # Área rolável para caber todos os módulos em telas menores
        container = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- DASHBOARD: resumo do período + evolução do PMPV ---
        try:
            PainelResumo(container).pack(fill="x", pady=(0, 14))
        except Exception as e:
            print(f"Aviso: não foi possível carregar o resumo do dashboard -> {e}")

        # --- 3 MÓDULOS (mesmas cores do sidebar) ---
        etapas = [
            {
                "num": "1", "cor": "#2980b9",
                "titulo": "PMPV — Precificação Mensal por Volume",
                "subtitulo": "Entrada de dados mensais por empresa. Fonte primária de todos os cálculos.",
                "cards": [
                    {"titulo": "📊 PMPV", "desc": "Volume Prospectivo\nmensal por empresa", "comando": self.abrir_pmpv},
                ],
            },
            {
                "num": "2", "cor": "#16a085",
                "titulo": "Conta Gráfica",
                "subtitulo": "Execute na ordem: CGR → CGF → RPV → RET → RP → SCG → SR",
                "cards": [
                    {"titulo": "🔍 Auditoria CGR", "desc": "Notas fiscais\nvia XML/OCR", "comando": self.abrir_auditoria},
                    {"titulo": "📋 CGF", "desc": "Volume Faturado\n× PMPV", "comando": self.abrir_cgf},
                    {"titulo": "🧾 RPV", "desc": "CGR − CGF", "comando": self.abrir_rpv},
                    {"titulo": "📄 RET", "desc": "Encargos\nEAT + EC", "comando": self.abrir_ret},
                    {"titulo": "📑 RP", "desc": "Conciliação de\npenalidades (PDFs)", "comando": self.abrir_ocr},
                    {"titulo": "💼 SCG", "desc": "RPV + RET + RP", "comando": self.abrir_scg},
                    {"titulo": "📈 SR", "desc": "(VP − VF) × PR", "comando": self.abrir_sr},
                ],
            },
            {
                "num": "3", "cor": "#8e44ad",
                "titulo": "Consolidação — Parcela de Recuperação",
                "subtitulo": "Agrega os 3 meses e calcula o Preço Regulatório e PV final.",
                "cards": [
                    {"titulo": "💡 PR", "desc": "Preço Regulatório\n(SCG + SR) ÷ VP", "comando": self.abrir_pr},
                    {"titulo": "💰 PV Final", "desc": "PMPV + PR\npor período", "comando": self.abrir_pv},
                    {"titulo": "📊 Excel Final", "desc": "Exporta todos os módulos\nconsolidados", "comando": self.exportar_relatorio_consolidado},
                ],
            },
        ]

        for etapa in etapas:
            self._criar_etapa(container, etapa)

    def _criar_etapa(self, parent, etapa: dict):
        """Cria um bloco de módulo: cabeçalho colorido + subtítulo + cards."""
        bloco = ctk.CTkFrame(parent, fg_color="transparent")
        bloco.pack(fill="x", pady=(6, 14))

        # Faixa de cabeçalho colorida com badge de número + título + subtítulo
        faixa = ctk.CTkFrame(bloco, fg_color=etapa["cor"], corner_radius=8)
        faixa.pack(fill="x", pady=(0, 8))

        num_badge = ctk.CTkLabel(
            faixa, text=f" {etapa['num']} ",
            font=ctk.CTkFont(size=22, weight="bold"),
            fg_color="white", text_color=etapa["cor"],
            corner_radius=6, width=40, height=40,
        )
        num_badge.pack(side="left", padx=(10, 14), pady=10)

        info = ctk.CTkFrame(faixa, fg_color="transparent")
        info.pack(side="left", pady=8)
        ctk.CTkLabel(
            info, text=f"Módulo {etapa['num']} — {etapa['titulo']}",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="white",
        ).pack(anchor="w")
        if etapa.get("subtitulo"):
            ctk.CTkLabel(
                info, text=etapa["subtitulo"],
                font=ctk.CTkFont(size=11),
                text_color="#d0e8ff",
            ).pack(anchor="w")

        # Cards do módulo, distribuídos em grade
        grade = ctk.CTkFrame(bloco, fg_color="transparent")
        grade.pack(fill="x", padx=4)
        for col in range(3):
            grade.grid_columnconfigure(col, weight=1, uniform="cards")

        for i, card in enumerate(etapa["cards"]):
            self._criar_card_grid(
                parent=grade,
                titulo=card["titulo"],
                desc=card["desc"],
                comando=card["comando"],
                linha=i // 3,
                coluna=i % 3,
                cor_modulo=etapa["cor"],
            )

    def _criar_card_grid(self, parent, titulo, desc, comando, linha, coluna, cor_modulo="#334155"):
        card = ctk.CTkFrame(parent, corner_radius=10, border_width=2, border_color=cor_modulo)
        card.grid(row=linha, column=coluna, padx=8, pady=8, sticky="nsew")

        # Tarja colorida no topo do card
        tarja = ctk.CTkFrame(card, fg_color=cor_modulo, corner_radius=0, height=4)
        tarja.pack(fill="x")

        ctk.CTkLabel(card, text=titulo,
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(12, 4))

        ctk.CTkLabel(card, text=desc,
                    font=ctk.CTkFont(size=11),
                    text_color="gray").pack(pady=4)

        if comando:
            ctk.CTkButton(
                card, text="Abrir", command=comando, width=100,
                fg_color=cor_modulo,
                hover_color=cor_modulo,
            ).pack(pady=(8, 14))
        else:
            ctk.CTkLabel(card, text="Em breve",
                        text_color="gray50",
                        font=ctk.CTkFont(size=11, slant="italic")).pack(pady=(8, 14))
            
    def _limpar_area_principal(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

    # --- MÉTODOS DE INTEGRAÇÃO (Abertura de Janelas) ---
    def _abrir_modulo(self, classe_tela, nome_amigavel: str, dica: str):
        """Abre uma tela de módulo com tratamento de erro amigável ao usuário.

        Em caso de falha, mostra uma mensagem em linguagem simples com uma
        dica do que fazer, e guarda o detalhe técnico ao final (para o suporte).
        """
        try:
            self._limpar_area_principal()
            classe_tela(self.main_area).pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror(
                f"Não foi possível abrir: {nome_amigavel}",
                f"Ocorreu um problema ao abrir o módulo \"{nome_amigavel}\".\n\n"
                f"O que fazer:\n{dica}\n\n"
                "Se o problema continuar, anote o código abaixo e avise o suporte:\n"
                f"[{type(e).__name__}] {e}",
            )

    def abrir_pmpv(self):
        self._abrir_modulo(
            TelaPMPV, "Módulo PMPV",
            "Verifique se o sistema foi aberto pela tela inicial. Tente novamente.",
        )

    def abrir_ocr(self):
        self._abrir_modulo(
            TelaConciliador, "Conciliação RP",
            "Confira se você tem os PDFs prontos para conciliar e tente novamente.",
        )

    def abrir_ret(self):
        self._abrir_modulo(
            TelaRET, "Sistema RET",
            "Verifique se os arquivos de encargos/NFs estão acessíveis e tente novamente.",
        )

    def abrir_auditoria(self):
        self._abrir_modulo(
            TelaAuditoria, "Auditoria CGR",
            "Confira se os PDFs das notas fiscais estão disponíveis e tente novamente.",
        )

    def abrir_scg(self):
        self._abrir_modulo(
            TelaSCG, "Consolidação SCG",
            "Esta etapa depende de RPV, RET e RP. Verifique se já foram calculados.",
        )

    def abrir_cgf(self):
        self._abrir_modulo(
            TelaCGF, "Volume CGF",
            "Verifique se os dados de volume faturado estão disponíveis e tente novamente.",
        )

    def abrir_rpv(self):
        self._abrir_modulo(
            TelaRPV, "RPV",
            "Esta etapa usa os valores de CGR e CGF. Verifique se já foram calculados.",
        )

    def abrir_sr(self):
        self._abrir_modulo(
            TelaSR, "SR (Saldo Regulatório)",
            "Esta etapa depende do Volume Prospectivo e do VF. Calcule o PMPV e o CGF antes.",
        )

    def abrir_pr(self):
        self._abrir_modulo(
            TelaPR, "PR Final",
            "Esta etapa depende de SGR e SR. Verifique se foram calculados antes.",
        )

    def abrir_pv(self):
        self._abrir_modulo(
            TelaPV, "PV Final",
            "Esta etapa usa o PMPV e o PR. Calcule esses módulos antes de continuar.",
        )

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
            messagebox.showerror(
                "Não foi possível gerar o relatório",
                "Houve um problema ao montar o Excel Final consolidado.\n\n"
                "O que fazer:\n"
                "• Confira se o período digitado está no formato Mês/Ano (ex.: Abr/2026).\n"
                "• Feche o arquivo Excel caso ele esteja aberto e tente de novo.\n\n"
                "Se o problema continuar, anote o código abaixo e avise o suporte:\n"
                f"[{type(e).__name__}] {e}",
            )

    