import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path

from Src.Services.servicos_cgf import ServicosCGF
from Src.Database.database import DatabasePMPV
from Src.common.excel_final_destino import registrar_execucao_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

APP_TITLE = "CGF - Somatório de Volume Faturado"
APP_SIZE  = "1050x700"

# Paleta de Cores Moderna
BG_APP     = "#0f172a"
BG_CARD    = "#1e293b"
BG_INPUT   = "#334155"
FG_TEXT    = "#f8fafc"
FG_MUTED   = "#94a3b8"
ACCENT_BLUE  = "#3b82f6"
ACCENT_BLUE_HOVER = "#2563eb"
ACCENT_GREEN = "#10b981"
ACCENT_GREEN_HOVER = "#059669"
ACCENT_RED   = "#ef4444"
ACCENT_RED_HOVER = "#dc2626"

class TelaCGF(ctk.CTkFrame):
    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG_APP)

        self.servicos = ServicosCGF()

        # Variáveis
        self.selected_files = []
        self.col_fat_volume  = ctk.StringVar(value="Volume Faturado")
        self.col_fat_consumo = ctk.StringVar(value="Produto")
        self.val_fat_consumo = ctk.StringVar(value="consumo proprio")
        self.col_fat_cfop    = ctk.StringVar(value="CFOP")

        self.col_canc_volume = ctk.StringVar(value="Volume Devolução")
        self.col_dev_volume  = ctk.StringVar(value="Volume Devolução")

        self.periodo_cgf  = ctk.StringVar(value="")
        self.pmpv_manual  = ctk.StringVar(value="")
        self.volume_final_cgf = 0.0
        self.cgf_rs           = 0.0

        self._build_ui()
        self._refresh_files_listbox()
        self._log("Sistema iniciado. Design moderno carregado com sucesso.\nAguardando arquivos...")

    # -----------------------------------------
    # Layout principal
    # -----------------------------------------
    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=30)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header, text="Dashboard de Volumes CGF", font=("Segoe UI", 24, "bold"), text_color=FG_TEXT).pack(anchor="w")
        ctk.CTkLabel(header, text="Fluxo: Faturada - Canceladas - Devoluções - Consumo próprio.", 
                     font=("Segoe UI", 12), text_color=FG_MUTED).pack(anchor="w", pady=(2, 0))

        main = ctk.CTkFrame(container, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1, uniform="col")
        main.columnconfigure(1, weight=1, uniform="col")
        main.rowconfigure(0, weight=1)

        left  = ctk.CTkFrame(main, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        self._build_files_card(left)
        self._build_config_tabs(left)
        self._build_result_card(right)

    def _build_files_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 20))
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content, text="Arquivos do Mês", font=("Segoe UI", 16, "bold"), text_color=FG_TEXT).pack(anchor="w")
        ctk.CTkLabel(content, text="Gerencie as planilhas base para o cálculo.", font=("Segoe UI", 12), text_color=FG_MUTED).pack(anchor="w", pady=(0, 15))

        btns = ctk.CTkFrame(content, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(btns, text="Selecionar...", fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_HOVER, command=self.select_files, width=120).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btns, text="Limpar", fg_color=ACCENT_RED, hover_color=ACCENT_RED_HOVER, command=self.clear_files, width=80).pack(side="right")

        self.files_listbox = ctk.CTkTextbox(content, fg_color=BG_INPUT, text_color=FG_TEXT, font=("Segoe UI", 11), height=80, corner_radius=8)
        self.files_listbox.pack(fill="both", expand=True)

    def _build_config_tabs(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="both", expand=True)
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content, text="Mapeamento de Colunas", font=("Segoe UI", 16, "bold"), text_color=FG_TEXT).pack(anchor="w", pady=(0, 10))

        self.tabview = ctk.CTkTabview(content, fg_color=BG_INPUT, segmented_button_fg_color=BG_APP, 
                                      segmented_button_selected_color=ACCENT_BLUE, segmented_button_selected_hover_color=ACCENT_BLUE_HOVER)
        self.tabview.pack(fill="both", expand=True)

        tab_fat  = self.tabview.add("NF Faturada")
        tab_canc = self.tabview.add("Canceladas")
        tab_dev  = self.tabview.add("Devolução")

        self._add_form_row(tab_fat, "Volume faturado:",      self.col_fat_volume)
        self._add_form_row(tab_fat, "Coluna cons. próprio:", self.col_fat_consumo)
        self._add_form_row(tab_fat, "Valor cons. próprio:",  self.val_fat_consumo)
        self._add_form_row(tab_fat, "Coluna CFOP (Opc):",    self.col_fat_cfop)

        self._add_form_row(tab_canc, "Volume canceladas:", self.col_canc_volume)
        self._add_form_row(tab_dev, "Volume devoluções:", self.col_dev_volume)

    def _add_form_row(self, parent, label_text, variable):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6, padx=10)
        ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 12), text_color=FG_TEXT, width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=variable, font=("Segoe UI", 12), fg_color=BG_APP, border_width=0, corner_radius=6).pack(side="left", fill="x", expand=True)

    def _build_result_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="both", expand=True)
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=25, pady=25)

        ctk.CTkLabel(content, text="Resultado e Processamento", font=("Segoe UI", 18, "bold"), text_color=FG_TEXT).pack(anchor="w", pady=(0, 15))

        # Seletor de Período
        per_card = ctk.CTkFrame(content, fg_color="#0f2744", corner_radius=8)
        per_card.pack(fill="x", pady=(0, 15), ipady=5)
        
        top_per = ctk.CTkFrame(per_card, fg_color="transparent")
        top_per.pack(fill="x", padx=15, pady=(10, 5))
        ctk.CTkLabel(top_per, text="📅  Período de Referência", font=("Segoe UI", 12, "bold"), text_color=ACCENT_BLUE).pack(side="left")
        
        per_row = ctk.CTkFrame(per_card, fg_color="transparent")
        per_row.pack(fill="x", padx=15, pady=(0, 10))
        
        self.combo_periodo = ctk.CTkComboBox(per_row, variable=self.periodo_cgf, font=("Segoe UI", 12), fg_color=BG_APP, border_width=0, command=lambda _e: self._carregar_pmpv_banco(silencioso=True))
        self.combo_periodo.pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(per_row, text="🔄 Atualizar", fg_color="#1e3a5f", hover_color="#334155", font=("Segoe UI", 11), width=80, command=self._atualizar_combo_periodos).pack(side="left")

        # Botões de Ação Principais
        btn_row = ctk.CTkFrame(content, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 15))
        
        ctk.CTkButton(btn_row, text="▶ INICIAR CÁLCULO", fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_HOVER, font=("Segoe UI", 12, "bold"), command=self.calculate_total).pack(side="right")
        self.btn_salvar_scg = ctk.CTkButton(btn_row, text="💾 Salvar CGF no SCG", fg_color=BG_INPUT, hover_color="#475569", text_color=FG_TEXT, state="disabled", command=self._salvar_cgf_scg)
        self.btn_salvar_scg.pack(side="right", padx=(0, 10))
        self.btn_excel_final = ctk.CTkButton(btn_row, text="➕ Excel Final (Módulo 9)", fg_color="#6c3483", hover_color="#884ea0", text_color=FG_TEXT, state="disabled", command=self._adicionar_excel_final)
        self.btn_excel_final.pack(side="right", padx=(0, 10))

        # Painel de Resumo
        res_box = ctk.CTkFrame(content, fg_color=BG_INPUT, corner_radius=8)
        res_box.pack(fill="x", pady=(0, 15), ipady=5)
        self.result_label = ctk.CTkLabel(res_box, text="Volume Final CGF: ---", font=("Segoe UI", 18, "bold"), text_color=ACCENT_GREEN)
        self.result_label.pack(side="left", padx=15, pady=10)

        pmpv_box = ctk.CTkFrame(content, fg_color="#1e3a5f", corner_radius=8)
        pmpv_box.pack(fill="x", pady=(0, 15), ipady=5)
        
        ctk.CTkLabel(pmpv_box, text="💱  Volume × PMPV  =  CGF em R$", font=("Segoe UI", 14, "bold"), text_color=ACCENT_BLUE).pack(anchor="w", padx=15, pady=(10, 5))
        
        row_pmpv = ctk.CTkFrame(pmpv_box, fg_color="transparent")
        row_pmpv.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row_pmpv, text="PMPV (R$/m³):", font=("Segoe UI", 12), text_color=FG_MUTED, width=100, anchor="w").pack(side="left")
        
        self.pmpv_entry = ctk.CTkEntry(row_pmpv, textvariable=self.pmpv_manual, font=("Segoe UI", 12), fg_color=BG_APP, border_width=0, width=120)
        self.pmpv_entry.pack(side="left", padx=(0, 10))
        self.pmpv_entry.bind("<KeyRelease>", lambda _e: self._atualizar_cgf_rs())
        
        ctk.CTkButton(row_pmpv, text="⚡ Carregar do banco", fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_HOVER, font=("Segoe UI", 11, "bold"), width=130, command=lambda: self._carregar_pmpv_banco(silencioso=False)).pack(side="left")

        row_rs = ctk.CTkFrame(pmpv_box, fg_color="transparent")
        row_rs.pack(fill="x", padx=15, pady=(5, 10))
        self.lbl_cgf_rs = ctk.CTkLabel(row_rs, text="CGF em R$:  ---", font=("Segoe UI", 16, "bold"), text_color=ACCENT_GREEN)
        self.lbl_cgf_rs.pack(side="left")

        # Console Log
        ctk.CTkLabel(content, text="Console de Execução:", font=("Segoe UI", 12), text_color=FG_MUTED).pack(anchor="w", pady=(5, 5))
        self.log_text = ctk.CTkTextbox(content, fg_color=BG_APP, text_color=FG_MUTED, font=("Consolas", 12), corner_radius=8)
        self.log_text.pack(fill="both", expand=True)

        self.after(300, self._atualizar_combo_periodos)

    # -----------------------------------------
    # Ações e Eventos
    # -----------------------------------------
    def select_files(self):
        paths = filedialog.askopenfilenames(title="Selecione as planilhas de NF", filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")])
        if paths:
            self.selected_files = list(paths)
            self._refresh_files_listbox()
            self._log(f"{len(self.selected_files)} arquivo(s) selecionado(s).")

    def clear_files(self):
        self.selected_files = []
        self._refresh_files_listbox()
        self.result_label.configure(text="Volume Final CGF: ---")
        self._log("Lista de arquivos limpa.")

    def _refresh_files_listbox(self):
        self.files_listbox.configure(state="normal")
        self.files_listbox.delete("0.0", "end")
        for p in self.selected_files:
            self.files_listbox.insert("end", f" 📄 {Path(p).name}\n")
        self.files_listbox.configure(state="disabled")

    def _log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def calculate_total(self):
        if not self.selected_files:
            messagebox.showwarning("Aviso", "Selecione ao menos um arquivo.")
            return

        fat_vol_col  = self.col_fat_volume.get().strip()
        fat_cons_col = self.col_fat_consumo.get().strip()
        fat_cons_val = self.val_fat_consumo.get().strip()
        canc_vol_col = self.col_canc_volume.get().strip()
        dev_vol_col  = self.col_dev_volume.get().strip()

        if not fat_vol_col:
            messagebox.showerror("Erro", "Informe a coluna de volume da NF Faturada.")
            return

        self.log_text.configure(state="normal")
        self.log_text.delete("0.0", "end")
        self.log_text.configure(state="disabled")
        self._log("⚡ INICIANDO PROCESSAMENTO...\n" + "-" * 40)

        # Chama a inteligência do Serviço Pandas!
        resultado = self.servicos.processar_arquivos(
            self.selected_files, fat_vol_col, fat_cons_col, 
            fat_cons_val, canc_vol_col, dev_vol_col
        )
        self._ultimo_resultado_cgf = resultado

        for linha in resultado["logs"]:
            self._log(linha)

        self.volume_final_cgf = resultado["volume_final"]
        self.result_label.configure(text=f"Volume Final CGF: {self.volume_final_cgf:,.2f} m³")
        self._atualizar_cgf_rs()          
        self.btn_salvar_scg.configure(state="normal", fg_color=ACCENT_BLUE)
        self.btn_excel_final.configure(state="normal", fg_color="#6c3483")

    def _atualizar_cgf_rs(self):
        try:
            pmpv = float(self.pmpv_manual.get().replace(",", ".").strip())
        except ValueError:
            pmpv = 0.0

        vol = getattr(self, "volume_final_cgf", 0.0)
        self.cgf_rs = vol * pmpv

        if vol > 0 and pmpv > 0:
            self.lbl_cgf_rs.configure(text=f"CGF em R$:  R$ {self.cgf_rs:,.2f}", text_color=ACCENT_GREEN)
        else:
            self.lbl_cgf_rs.configure(
                text="CGF em R$:  --- (informe o PMPV)" if vol > 0 else "CGF em R$:  ---",
                text_color=FG_MUTED,
            )

    def _atualizar_combo_periodos(self):
        todos = self.servicos.obter_periodos()
        self.combo_periodo.configure(values=todos)

    def _carregar_pmpv_banco(self, silencioso: bool = False):
        periodo = self.periodo_cgf.get().strip()
        if not periodo:
            if not silencioso: messagebox.showwarning("Aviso", "Selecione o período de referência.")
            return

        try:
            pmpv = self.servicos.buscar_pmpv(periodo)
            if pmpv is None:
                if not silencioso: messagebox.showwarning("Não encontrado", f"Nenhum PMPV salvo para '{periodo}'.")
                return

            self.pmpv_manual.set(f"{pmpv:.4f}")
            self._atualizar_cgf_rs()
        except Exception as e:
            if not silencioso: messagebox.showerror("Erro", f"Erro ao acessar BD: {e}")

    def _salvar_cgf_scg(self):
        if self.volume_final_cgf == 0.0:
            messagebox.showwarning("Aviso", "Execute o cálculo de volume antes de salvar.")
            return

        if self.cgf_rs == 0.0:
            resp = messagebox.askyesno("PMPV não informado", "Deseja salvar apenas o volume (sem multiplicar pelo PMPV)?")
            if not resp: return
            valor_salvar = self.volume_final_cgf
        else:
            valor_salvar = self.cgf_rs

        periodo = self.periodo_cgf.get().strip()
        if not periodo:
            from tkinter import simpledialog
            periodo = simpledialog.askstring("Salvar CGF", "Digite o período (ex: Dez/2025):", initialvalue="Dez/2025")
            if not periodo: return

        try:
            rpv = self.servicos.salvar_cgf(periodo, valor_salvar)
            resumo = getattr(self, "_ultimo_resultado_cgf", {})
            db = DatabasePMPV()
            try:
                db.salvar_cgf_resumo(
                    periodo,
                    resumo.get("volume_faturado", 0.0),
                    resumo.get("volume_canceladas", 0.0),
                    resumo.get("volume_devolucoes", 0.0),
                    resumo.get("volume_consumo_proprio", 0.0),
                    resumo.get("volume_final", self.volume_final_cgf),
                )
            finally:
                db.fechar()
            tipo = "R$ (Volume × PMPV)" if self.cgf_rs > 0 else "volume bruto (sem PMPV)"
            messagebox.showinfo("CGF Salvo ✅", f"Período: {periodo}\nCGF ({tipo}): {valor_salvar:,.2f}\nRPV = R$ {rpv:,.2f}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gravar no BD: {e}")

    def _adicionar_excel_final(self):
        if self.volume_final_cgf == 0.0:
            messagebox.showwarning("Aviso", "Execute o cálculo de volume antes de adicionar ao Excel final.")
            return

        if self.cgf_rs == 0.0:
            resp = messagebox.askyesno("PMPV não informado", "Deseja usar apenas o volume (sem PMPV) para salvar no módulo 9?")
            if not resp:
                return
            valor_salvar = self.volume_final_cgf
        else:
            valor_salvar = self.cgf_rs

        periodo = self.periodo_cgf.get().strip()
        if not periodo:
            periodo = simpledialog.askstring(
                "Excel Final (Módulo 9)",
                "Período para salvar e gerar o Excel final (ex: Dez/2025):\nDeixe em branco para gerar com todos os períodos.",
                parent=self,
            )
            if periodo is None:
                return

        periodo_salvar = periodo.strip() if periodo and periodo.strip() else "Geral"
        self.servicos.salvar_cgf(periodo_salvar, valor_salvar)

        resumo = getattr(self, "_ultimo_resultado_cgf", {})
        db = DatabasePMPV()
        try:
            db.salvar_cgf_resumo(
                periodo_salvar,
                resumo.get("volume_faturado", 0.0),
                resumo.get("volume_canceladas", 0.0),
                resumo.get("volume_devolucoes", 0.0),
                resumo.get("volume_consumo_proprio", 0.0),
                resumo.get("volume_final", self.volume_final_cgf),
            )
        finally:
            db.fechar()

        meta_execucao = registrar_execucao_excel_final(etapa="CGF", periodo=periodo_salvar, parent=self)
        if not meta_execucao:
            return
        destino, _, _, execucao = meta_execucao
        arquivo = ExcelConsolidado.exportar(periodo=None, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅", f"Arquivo criado com sucesso:\n{arquivo}\n\nEtapa CGF registrada (execução #{execucao}).")