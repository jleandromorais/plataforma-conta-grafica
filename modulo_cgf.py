import tkinter as tk
from tkinter import filedialog, messagebox
import pandas as pd
from pathlib import Path
import customtkinter as ctk

# ---------------------------------------------
# Configurações gerais CustomTkinter
# ---------------------------------------------
ctk.set_appearance_mode("dark")  # Força o dark mode
ctk.set_default_color_theme("blue")

APP_TITLE = "CGF - Somatório de Volume Faturado"
APP_SIZE  = "1050x700"

# Paleta de Cores Moderna (Estilo Tailwind Slate Dark Mode)
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

# Caminhos padrão
DEFAULT_FILES = [
    r"z:\COPERGAS\VENDAS_TARIFAS_ MARGEM_ MÉDIA\2025\total mensal 12-2025\NF Faturada e complementar.xlsx",
    r"z:\COPERGAS\VENDAS_TARIFAS_ MARGEM_ MÉDIA\2025\total mensal 12-2025\NF canceladas e denegadas.xlsx",
    r"z:\COPERGAS\VENDAS_TARIFAS_ MARGEM_ MÉDIA\2025\total mensal 12-2025\NF devolução dez.25.xlsx",
]

class CGFApp(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        self.minsize(1000, 700)
        self.configure(fg_color=BG_APP)

        # ===== VARIÁVEIS =====
        self.selected_files = list(DEFAULT_FILES)

        self.col_fat_volume  = ctk.StringVar(value="Volume Faturado")
        self.col_fat_consumo = ctk.StringVar(value="Produto")
        self.val_fat_consumo = ctk.StringVar(value="consumo proprio")
        self.col_fat_cfop    = ctk.StringVar(value="CFOP")
        self.extra_fat_columns = []

        self.col_canc_volume = ctk.StringVar(value="Volume Devolução")
        self.extra_canc_columns = []

        self.col_dev_volume  = ctk.StringVar(value="Volume Devolução")
        self.extra_dev_columns = []

        self.periodo_cgf  = ctk.StringVar(value="")
        self.pmpv_manual  = ctk.StringVar(value="")
        self.volume_final_cgf = 0.0
        self.cgf_rs           = 0.0

        self._build_ui()
        self._refresh_files_listbox()
        self._log("Sistema iniciado. Design moderno carregado com sucesso.")
        self._log("Caminhos padrão carregados automaticamente.")
        self._log(f"{len(self.selected_files)} arquivo(s) listado(s) inicialmente.\n")

    # -----------------------------------------
    # Layout principal
    # -----------------------------------------
    def _build_ui(self):
        # Container principal
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=30)

        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header, text="Dashboard de Volumes CGF", font=("Segoe UI", 24, "bold"), text_color=FG_TEXT).pack(anchor="w")
        ctk.CTkLabel(header, text="Fluxo: Faturada - Canceladas - Devoluções - Consumo próprio.", 
                     font=("Segoe UI", 12), text_color=FG_MUTED).pack(anchor="w", pady=(2, 0))

        # Divisão Esquerda / Direita
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

    # -----------------------------------------
    # UI: Painel Esquerdo (Arquivos e Configs)
    # -----------------------------------------
    def _build_files_card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 20))
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content, text="Arquivos do Mês", font=("Segoe UI", 16, "bold"), text_color=FG_TEXT).pack(anchor="w")
        ctk.CTkLabel(content, text="Gerencie as planilhas base para o cálculo.", font=("Segoe UI", 12), text_color=FG_MUTED).pack(anchor="w", pady=(0, 15))

        btns = ctk.CTkFrame(content, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(btns, text="Carregar Padrões", fg_color=BG_INPUT, hover_color="#475569", text_color=FG_TEXT, command=self.load_default_files, width=120).pack(side="left", padx=(0, 5))
        ctk.CTkButton(btns, text="Selecionar...", fg_color=ACCENT_BLUE, hover_color=ACCENT_BLUE_HOVER, command=self.select_files, width=100).pack(side="left", padx=5)
        ctk.CTkButton(btns, text="Limpar", fg_color=ACCENT_RED, hover_color=ACCENT_RED_HOVER, command=self.clear_files, width=80).pack(side="right")

        self.files_listbox = ctk.CTkTextbox(content, fg_color=BG_INPUT, text_color=FG_TEXT, font=("Segoe UI", 11), height=80, corner_radius=8)
        self.files_listbox.pack(fill="both", expand=True)

    def _build_config_tabs(self, parent):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=12)
        card.pack(fill="both", expand=True)
        
        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content, text="Mapeamento de Colunas", font=("Segoe UI", 16, "bold"), text_color=FG_TEXT).pack(anchor="w", pady=(0, 10))

        # Novo componente de Tabs nativo do CustomTkinter
        self.tabview = ctk.CTkTabview(content, fg_color=BG_INPUT, segmented_button_fg_color=BG_APP, 
                                      segmented_button_selected_color=ACCENT_BLUE, segmented_button_selected_hover_color=ACCENT_BLUE_HOVER)
        self.tabview.pack(fill="both", expand=True)

        tab_fat  = self.tabview.add("NF Faturada")
        tab_canc = self.tabview.add("Canceladas")
        tab_dev  = self.tabview.add("Devolução")

        self._build_tab_faturada(tab_fat)
        self._build_tab_canceladas(tab_canc)
        self._build_tab_devolucoes(tab_dev)

    def _build_tab_faturada(self, tab):
        self._add_form_row(tab, "Volume faturado:",      self.col_fat_volume)
        self._add_form_row(tab, "Coluna cons. próprio:", self.col_fat_consumo)
        self._add_form_row(tab, "Valor cons. próprio:",  self.val_fat_consumo)
        self._add_form_row(tab, "Coluna CFOP (Opc):",    self.col_fat_cfop)

    def _build_tab_canceladas(self, tab):
        self._add_form_row(tab, "Volume canceladas:", self.col_canc_volume)

    def _build_tab_devolucoes(self, tab):
        self._add_form_row(tab, "Volume devoluções:", self.col_dev_volume)

    def _add_form_row(self, parent, label_text, variable):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=6, padx=10)
        ctk.CTkLabel(row, text=label_text, font=("Segoe UI", 12), text_color=FG_TEXT, width=140, anchor="w").pack(side="left")
        ctk.CTkEntry(row, textvariable=variable, font=("Segoe UI", 12), fg_color=BG_APP, border_width=0, corner_radius=6).pack(side="left", fill="x", expand=True)

    # -----------------------------------------
    # UI: Painel Direito (Resultado e Log)
    # -----------------------------------------
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

        # Painel de Resumo Moderno
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
    # Handlers arquivos e Log
    # -----------------------------------------
    def load_default_files(self):
        self.selected_files = list(DEFAULT_FILES)
        self._refresh_files_listbox()
        self._log("Caminhos padrão recarregados.")

    def select_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecione as planilhas de NF",
            filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")],
        )
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

    # -----------------------------------------
    # Lógica de Cálculo (Mantida a Original)
    # -----------------------------------------
    def _read_table(self, path: str):
        try:
            ext = Path(path).suffix.lower()
            if ext in [".xlsx", ".xls"]:
                return pd.read_excel(path)
            elif ext == ".csv":
                return pd.read_csv(path, sep=";", engine="python")
            return None
        except Exception as e:
            self._log(f"[ERRO] {e}\n")
            return None

    @staticmethod
    def _mask_consumo(df: "pd.DataFrame", col_configurada: str, val_configurado: str) -> "pd.Series":
        import pandas as pd
        mask = pd.Series([False] * len(df), index=df.index)

        if col_configurada and col_configurada in df.columns and val_configurado:
            serie = df[col_configurada].astype(str).str.upper().str.strip()
            mask |= (serie == val_configurado.upper())

        TERMOS = ["consumo", "proprio", "próprio", "consumo proprio", "consumo próprio", "cons. proprio", "cons proprio"]
        for col in df.columns:
            if df[col].dtype == object or str(df[col].dtype) == "string":
                serie_col = df[col].astype(str).str.lower().str.strip()
                for termo in TERMOS:
                    mask |= serie_col.str.contains(termo, na=False, regex=False)
        return mask

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

        total_faturado = total_canceladas = total_devolucoes = total_consumo_proprio = 0.0

        self.log_text.configure(state="normal")
        self.log_text.delete("0.0", "end")
        self.log_text.configure(state="disabled")
        self._log("⚡ INICIANDO PROCESSAMENTO...\n" + "-" * 40)

        for path in self.selected_files:
            nome     = Path(path).name
            nome_low = nome.lower()
            df = self._read_table(path)
            if df is None:
                continue

            if "faturada" in nome_low and "complementar" in nome_low:
                self._log(f"🟢 FATURADA: {nome}")
                if fat_vol_col not in df.columns:
                    self._log(f"   [!] Coluna '{fat_vol_col}' ausente. Ignorado.\n")
                    continue

                mask_cons = self._mask_consumo(df, fat_cons_col, fat_cons_val)
                qtd_cons  = mask_cons.sum()

                df_cons     = df[mask_cons].copy()
                df_sem_cons = df[~mask_cons].copy()

                df_sem_cons[fat_vol_col] = pd.to_numeric(df_sem_cons[fat_vol_col], errors="coerce")
                df_cons[fat_vol_col]     = pd.to_numeric(df_cons[fat_vol_col],     errors="coerce")

                vol_fat  = df_sem_cons[fat_vol_col].sum()
                vol_cons = df_cons[fat_vol_col].sum()
                total_faturado        += float(vol_fat)
                total_consumo_proprio += float(vol_cons)

                self._log(f"   + Faturado limpo:   {vol_fat:,.2f}")
                if qtd_cons > 0:
                    self._log(f"   - Consumo próprio:  {vol_cons:,.2f}  ({qtd_cons} linha(s) detectada(s))\n")
                else:
                    self._log(f"   (nenhum consumo próprio detectado)\n")

            elif "cancelad" in nome_low or "denegad" in nome_low:
                self._log(f"🔴 CANCELADAS: {nome}")
                if canc_vol_col in df.columns:
                    df[canc_vol_col] = pd.to_numeric(df[canc_vol_col], errors="coerce")
                    vol_canc = df[canc_vol_col].sum()
                    total_canceladas += float(vol_canc)
                    self._log(f"   - Canceladas: {vol_canc:,.2f}\n")

            elif "devolu" in nome_low:
                self._log(f"🟡 DEVOLUÇÃO: {nome}")
                if dev_vol_col in df.columns:
                    df[dev_vol_col] = pd.to_numeric(df[dev_vol_col], errors="coerce")
                    vol_dev = df[dev_vol_col].sum()
                    total_devolucoes += float(vol_dev)
                    self._log(f"   - Devoluções: {vol_dev:,.2f}\n")

        volume_final = total_faturado - total_canceladas - total_devolucoes - total_consumo_proprio

        self._log("-" * 40 + "\n📊 RESUMO GERAL:")
        self._log(f" (+) Faturado:          {total_faturado:,.2f}")
        self._log(f" (-) Canceladas:        {total_canceladas:,.2f}")
        self._log(f" (-) Devoluções:        {total_devolucoes:,.2f}")
        self._log(f" (-) Consumo Próprio:   {total_consumo_proprio:,.2f}")
        self._log(f"\n  => VOLUME FINAL CGF:  {volume_final:,.2f}")

        self.result_label.configure(text=f"Volume Final CGF: {volume_final:,.2f} m³")
        self.volume_final_cgf = volume_final
        self._atualizar_cgf_rs()          
        self.btn_salvar_scg.configure(state="normal", fg_color=ACCENT_BLUE)

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
        from database import DatabasePMPV
        try:
            db = DatabasePMPV()
            periodos_cons  = {r["periodo"] for r in db.listar_periodos()}
            periodos_pmpv  = {r["periodo"] for r in db.listar_pmpv_mensal()}
            db.fechar()
            todos = sorted(periodos_cons | periodos_pmpv, reverse=True)
            self.combo_periodo.configure(values=todos)
        except Exception:
            pass

    def _carregar_pmpv_banco(self, silencioso: bool = False):
        from database import DatabasePMPV
        periodo = self.periodo_cgf.get().strip()
        if not periodo:
            if not silencioso:
                messagebox.showwarning("Período vazio", "Selecione ou digite o período de referência.")
            return

        try:
            db = DatabasePMPV()
            pmpv = db.buscar_pmpv_mensal(periodo)
            db.fechar()

            if pmpv is None:
                if not silencioso:
                    messagebox.showwarning("PMPV não encontrado", f"Nenhum PMPV salvo para '{periodo}'.")
                return

            self.pmpv_manual.set(f"{pmpv:.4f}")
            self._atualizar_cgf_rs()
        except Exception as e:
            if not silencioso:
                messagebox.showerror("Erro", f"Erro ao acessar BD: {e}")

    def _salvar_cgf_scg(self):
        from database import DatabasePMPV
        if self.volume_final_cgf == 0.0:
            messagebox.showwarning("Aviso", "Execute o cálculo de volume antes de salvar.")
            return

        if self.cgf_rs == 0.0:
            resp = messagebox.askyesno("PMPV não informado", "Deseja salvar apenas o volume (sem multiplicar pelo PMPV)?")
            if not resp:
                return
            valor_salvar = self.volume_final_cgf
        else:
            valor_salvar = self.cgf_rs

        periodo = self.periodo_cgf.get().strip()
        if not periodo:
            from tkinter import simpledialog
            periodo = simpledialog.askstring("Salvar CGF", "Digite o período (ex: Dez/2025):", initialvalue="Dez/2025")
            if not periodo:
                return

        try:
            db = DatabasePMPV()
            db.atualizar_cgf(periodo, valor_salvar)
            rpv = db.calcular_e_salvar_rpv(periodo)
            db.fechar()

            tipo = "R$ (Volume × PMPV)" if self.cgf_rs > 0 else "volume bruto (sem PMPV)"
            messagebox.showinfo("CGF Salvo ✅", f"Período: {periodo}\nCGF ({tipo}): {valor_salvar:,.2f}\nRPV = R$ {rpv:,.2f}")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gravar no BD: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = CGFApp(root)
    root.mainloop()