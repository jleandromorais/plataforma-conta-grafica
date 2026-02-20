import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
from pathlib import Path
import customtkinter as ctk

# ---------------------------------------------
# Configurações gerais
# ---------------------------------------------
APP_TITLE = "CGF - Somatório de Volume Faturado"
APP_SIZE  = "1050x700"

# Paleta de Cores Moderna (Estilo Tailwind Slate Dark Mode)
BG_APP     = "#0f172a"
BG_CARD    = "#1e293b"
BG_INPUT   = "#334155"
FG_TEXT    = "#f8fafc"
FG_MUTED   = "#94a3b8"
ACCENT_BLUE  = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_RED   = "#ef4444"

# Caminhos padrão
DEFAULT_FILES = [
    r"z:\COPERGAS\VENDAS_TARIFAS_ MARGEM_ MÉDIA\2025\total mensal 12-2025\NF Faturada e complementar.xlsx",
    r"z:\COPERGAS\VENDAS_TARIFAS_ MARGEM_ MÉDIA\2025\total mensal 12-2025\NF canceladas e denegadas.xlsx",
    r"z:\COPERGAS\VENDAS_TARIFAS_ MARGEM_ MÉDIA\2025\total mensal 12-2025\NF devolução dez.25.xlsx",
]


class CGFApp(ctk.CTkToplevel):
    """Módulo CGF — integrado à plataforma como CTkToplevel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title(APP_TITLE)
        self.geometry(APP_SIZE)
        self.minsize(1000, 650)
        self.configure(bg=BG_APP)

        # ===== VARIÁVEIS =====
        self.selected_files = list(DEFAULT_FILES)

        self.col_fat_volume  = tk.StringVar(value="Volume Faturado")
        self.col_fat_consumo = tk.StringVar(value="Descricao")
        self.val_fat_consumo = tk.StringVar(value="CONSUMO PROPRIO")
        self.col_fat_cfop    = tk.StringVar(value="CFOP")
        self.extra_fat_columns = []

        self.col_canc_volume = tk.StringVar(value="Volume Devolução")
        self.extra_canc_columns = []

        self.col_dev_volume  = tk.StringVar(value="Volume")
        self.extra_dev_columns = []

        self._config_style()
        self._build_ui()

        self._refresh_files_listbox()
        self._log("Sistema iniciado. Design moderno carregado.")
        self._log("Caminhos padrão carregados automaticamente.")
        self._log(f"{len(self.selected_files)} arquivo(s) listado(s) inicialmente.\n")

    # -----------------------------------------
    # Estilo visual
    # -----------------------------------------
    def _config_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Main.TFrame",  background=BG_APP)
        style.configure("Card.TFrame",  background=BG_CARD)

        style.configure("Heading.TLabel",    font=("Segoe UI", 22, "bold"), foreground=FG_TEXT,  background=BG_APP)
        style.configure("SubHeading.TLabel", font=("Segoe UI", 11),         foreground=FG_MUTED, background=BG_APP)
        style.configure("CardTitle.TLabel",  font=("Segoe UI", 13, "bold"), foreground=FG_TEXT,  background=BG_CARD)
        style.configure("CardText.TLabel",   font=("Segoe UI", 10),         foreground=FG_MUTED, background=BG_CARD)
        style.configure("TLabel",            font=("Segoe UI", 10),         foreground=FG_TEXT,  background=BG_CARD)
        style.configure("Result.TLabel",     font=("Segoe UI", 16, "bold"), foreground=ACCENT_GREEN, background=BG_INPUT)

        style.configure("TEntry", fieldbackground=BG_INPUT, foreground=FG_TEXT, borderwidth=0, padding=6)

        style.configure("TButton",        font=("Segoe UI", 10, "bold"), padding=8,  foreground=FG_TEXT, background=ACCENT_BLUE,  borderwidth=0)
        style.map("TButton",              background=[("active", "#2563eb"), ("pressed", "#1d4ed8")])

        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=10, foreground=FG_TEXT, background=ACCENT_GREEN, borderwidth=0)
        style.map("Accent.TButton",       background=[("active", "#059669"), ("pressed", "#047857")])

        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), padding=8,  foreground=FG_TEXT, background=ACCENT_RED,   borderwidth=0)
        style.map("Danger.TButton",       background=[("active", "#dc2626"), ("pressed", "#b91c1c")])

        style.configure("TNotebook",     background=BG_CARD, borderwidth=0, tabmargins=[0, 0, 0, 0])
        style.configure("TNotebook.Tab", font=("Segoe UI", 10, "bold"), padding=[15, 8],
                         background=BG_INPUT, foreground=FG_MUTED, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", BG_APP)],
                  foreground=[("selected", ACCENT_BLUE)])

        style.configure("TSeparator", background=BG_INPUT)

    # -----------------------------------------
    # Layout principal
    # -----------------------------------------
    def _build_ui(self):
        container = ttk.Frame(self, style="Main.TFrame")
        container.pack(fill="both", expand=True, padx=30, pady=30)

        header = ttk.Frame(container, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 20))
        ttk.Label(header, text="Dashboard de Volumes CGF", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(header, text="Fluxo: Faturada - Canceladas - Devoluções - Consumo próprio.",
                  style="SubHeading.TLabel").pack(anchor="w", pady=(2, 0))

        main = ttk.Frame(container, style="Main.TFrame")
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1, uniform="col")
        main.columnconfigure(1, weight=1, uniform="col")
        main.rowconfigure(0, weight=1)

        left  = ttk.Frame(main, style="Main.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 15))

        right = ttk.Frame(main, style="Main.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(15, 0))

        self._build_files_card(left)
        self._build_config_tabs(left)
        self._build_result_card(right)

    # -----------------------------------------
    # Cards
    # -----------------------------------------
    def _create_card(self, parent):
        return ttk.Frame(parent, style="Card.TFrame")

    def _build_files_card(self, parent):
        card = self._create_card(parent)
        card.pack(fill="x", pady=(0, 20))
        content = ttk.Frame(card, style="Card.TFrame")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(content, text="Arquivos do Mês",                                style="CardTitle.TLabel").pack(anchor="w", pady=(0, 5))
        ttk.Label(content, text="Gerencie as planilhas base para o cálculo.",     style="CardText.TLabel").pack(anchor="w", pady=(0, 15))

        btns = ttk.Frame(content, style="Card.TFrame")
        btns.pack(fill="x", pady=(0, 10))
        btns.columnconfigure((0, 1, 2), weight=1)

        ttk.Button(btns, text="Carregar Padrões", command=self.load_default_files).grid(row=0, column=0, sticky="ew", padx=(0, 5))
        ttk.Button(btns, text="Selecionar...",    command=self.select_files).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(btns, text="Limpar", style="Danger.TButton", command=self.clear_files).grid(row=0, column=2, sticky="ew", padx=(5, 0))

        self.files_listbox = tk.Listbox(
            content, bg=BG_INPUT, fg=FG_TEXT,
            selectbackground=ACCENT_BLUE, selectforeground=FG_TEXT,
            highlightthickness=0, borderwidth=0,
            font=("Segoe UI", 10), height=5,
        )
        self.files_listbox.pack(fill="both", expand=True)

    def _build_config_tabs(self, parent):
        card = self._create_card(parent)
        card.pack(fill="both", expand=True)
        content = ttk.Frame(card, style="Card.TFrame")
        content.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(content, text="Mapeamento de Colunas", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 15))

        notebook = ttk.Notebook(content, style="TNotebook")
        notebook.pack(fill="both", expand=True)

        tab_fat  = ttk.Frame(notebook, style="Card.TFrame")
        tab_canc = ttk.Frame(notebook, style="Card.TFrame")
        tab_dev  = ttk.Frame(notebook, style="Card.TFrame")

        notebook.add(tab_fat,  text=" NF Faturada ")
        notebook.add(tab_canc, text=" Canceladas ")
        notebook.add(tab_dev,  text=" Devolução ")

        self._build_tab_faturada(tab_fat)
        self._build_tab_canceladas(tab_canc)
        self._build_tab_devolucoes(tab_dev)

    def _build_tab_faturada(self, tab):
        f = ttk.Frame(tab, style="Card.TFrame")
        f.pack(fill="both", expand=True, pady=15, padx=5)
        f.columnconfigure(1, weight=1)

        self._add_form_row(f, "Volume faturado:",      self.col_fat_volume,  0)
        self._add_form_row(f, "Coluna cons. próprio:", self.col_fat_consumo, 1)
        self._add_form_row(f, "Valor cons. próprio:",  self.val_fat_consumo, 2)
        self._add_form_row(f, "Coluna CFOP (Opc):",    self.col_fat_cfop,    3)

        ttk.Separator(f, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=15)
        self.entry_extra_fat, self.list_extra_fat = self._build_extra_cols_section(
            f, 5, "Faturada", self.add_extra_fat_column, self.remove_extra_fat_column)

    def _build_tab_canceladas(self, tab):
        f = ttk.Frame(tab, style="Card.TFrame")
        f.pack(fill="both", expand=True, pady=15, padx=5)
        f.columnconfigure(1, weight=1)

        self._add_form_row(f, "Volume canceladas:", self.col_canc_volume, 0)
        ttk.Separator(f, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew", pady=15)
        self.entry_extra_canc, self.list_extra_canc = self._build_extra_cols_section(
            f, 2, "Canceladas", self.add_extra_canc_column, self.remove_extra_canc_column)

    def _build_tab_devolucoes(self, tab):
        f = ttk.Frame(tab, style="Card.TFrame")
        f.pack(fill="both", expand=True, pady=15, padx=5)
        f.columnconfigure(1, weight=1)

        self._add_form_row(f, "Volume devoluções:", self.col_dev_volume, 0)
        ttk.Separator(f, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew", pady=15)
        self.entry_extra_dev, self.list_extra_dev = self._build_extra_cols_section(
            f, 2, "Devoluções", self.add_extra_dev_column, self.remove_extra_dev_column)

    def _add_form_row(self, parent, label_text, variable, row_idx):
        ttk.Label(parent, text=label_text, style="TLabel").grid(row=row_idx, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable, font=("Segoe UI", 10)).grid(
            row=row_idx, column=1, sticky="ew", pady=5, padx=(10, 0))

    def _build_extra_cols_section(self, parent, start_row, nome, cmd_add, cmd_rem):
        ttk.Label(parent, text="Colunas extras de rastreio (Opcional):",
                  style="CardText.TLabel").grid(row=start_row, column=0, columnspan=2, sticky="w", pady=(0, 5))

        box = ttk.Frame(parent, style="Card.TFrame")
        box.grid(row=start_row + 1, column=0, columnspan=2, sticky="ew")
        box.columnconfigure(0, weight=1)

        entry = ttk.Entry(box, font=("Segoe UI", 10))
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ttk.Button(box, text="+ Adicionar", command=cmd_add).grid(row=0, column=1)

        lst = tk.Listbox(
            parent, bg=BG_INPUT, fg=FG_TEXT,
            selectbackground=ACCENT_RED,
            highlightthickness=0, borderwidth=0,
            font=("Segoe UI", 9), height=3,
        )
        lst.grid(row=start_row + 2, column=0, columnspan=2, sticky="nsew", pady=10)

        ttk.Button(parent, text="Remover Selecionada", style="Danger.TButton",
                   command=cmd_rem).grid(row=start_row + 3, column=0, columnspan=2, sticky="ew")
        return entry, lst

    # -----------------------------------------
    # Card Resultado / Log
    # -----------------------------------------
    def _build_result_card(self, parent):
        card = self._create_card(parent)
        card.pack(fill="both", expand=True)
        content = ttk.Frame(card, style="Card.TFrame")
        content.pack(fill="both", expand=True, padx=25, pady=25)

        header_box = ttk.Frame(content, style="Card.TFrame")
        header_box.pack(fill="x", pady=(0, 15))
        ttk.Label(header_box, text="Resultado e Processamento", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(header_box, text="▶ INICIAR CÁLCULO", style="Accent.TButton",
                   command=self.calculate_total).pack(side="right")

        res_box = tk.Frame(content, bg=BG_INPUT, padx=15, pady=15)
        res_box.pack(fill="x", pady=(0, 15))
        self.result_label = ttk.Label(res_box, text="Volume Final CGF: ---",
                                      style="Result.TLabel", background=BG_INPUT)
        self.result_label.pack()

        ttk.Label(content, text="Console de Execução:", style="CardText.TLabel").pack(anchor="w", pady=(5, 5))

        self.log_text = tk.Text(
            content, bg=BG_APP, fg=FG_MUTED, insertbackground=FG_TEXT,
            highlightthickness=0, borderwidth=0,
            font=("Consolas", 10), wrap="word",
        )
        self.log_text.pack(fill="both", expand=True)

    # -----------------------------------------
    # Handlers arquivos
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
        self.result_label.config(text="Volume Final CGF: ---")
        self._log("Lista de arquivos limpa.")

    def _refresh_files_listbox(self):
        self.files_listbox.delete(0, tk.END)
        for p in self.selected_files:
            self.files_listbox.insert(tk.END, f" 📄 {Path(p).name}")

    def _log(self, message: str):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    # -----------------------------------------
    # Handlers colunas extras
    # -----------------------------------------
    def _add_extra_column(self, entry, storage_list, listbox, origem_desc):
        nome = entry.get().strip()
        if nome and nome not in storage_list:
            storage_list.append(nome)
            entry.delete(0, tk.END)
            listbox.delete(0, tk.END)
            for n in storage_list:
                listbox.insert(tk.END, f" • {n}")
            self._log(f"[{origem_desc}] coluna monitorada: {nome}")

    def _remove_extra_column(self, storage_list, listbox, origem_desc):
        sel = listbox.curselection()
        if sel:
            idx  = sel[0]
            nome = storage_list[idx]
            del storage_list[idx]
            listbox.delete(0, tk.END)
            for n in storage_list:
                listbox.insert(tk.END, f" • {n}")
            self._log(f"[{origem_desc}] coluna removida: {nome}")

    def add_extra_fat_column(self):  self._add_extra_column(self.entry_extra_fat,  self.extra_fat_columns,  self.list_extra_fat,  "Faturada")
    def remove_extra_fat_column(self): self._remove_extra_column(self.extra_fat_columns,  self.list_extra_fat,  "Faturada")

    def add_extra_canc_column(self): self._add_extra_column(self.entry_extra_canc, self.extra_canc_columns, self.list_extra_canc, "Canceladas")
    def remove_extra_canc_column(self): self._remove_extra_column(self.extra_canc_columns, self.list_extra_canc, "Canceladas")

    def add_extra_dev_column(self):  self._add_extra_column(self.entry_extra_dev,  self.extra_dev_columns,  self.list_extra_dev,  "Devolução")
    def remove_extra_dev_column(self): self._remove_extra_column(self.extra_dev_columns,  self.list_extra_dev,  "Devolução")

    # -----------------------------------------
    # Lógica de Cálculo
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

    def calculate_total(self):
        if not self.selected_files:
            messagebox.showwarning("Aviso", "Selecione ao menos um arquivo.")
            return

        fat_vol_col  = self.col_fat_volume.get().strip()
        fat_cons_col = self.col_fat_consumo.get().strip()
        fat_cons_val = self.val_fat_consumo.get().strip()
        fat_cfop_col = self.col_fat_cfop.get().strip()  # noqa: F841 (reservado para uso futuro)
        canc_vol_col = self.col_canc_volume.get().strip()
        dev_vol_col  = self.col_dev_volume.get().strip()

        if not fat_vol_col:
            messagebox.showerror("Erro", "Informe a coluna de volume da NF Faturada.")
            return

        total_faturado = total_canceladas = total_devolucoes = total_consumo_proprio = 0.0

        self.log_text.delete("1.0", tk.END)
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

                if fat_cons_col and fat_cons_col in df.columns and fat_cons_val:
                    serie     = df[fat_cons_col].astype(str).str.upper().str.strip()
                    mask_cons = serie == fat_cons_val.upper()

                    df_cons     = df[mask_cons].copy()
                    df_sem_cons = df[~mask_cons].copy()
                    df_sem_cons[fat_vol_col] = pd.to_numeric(df_sem_cons[fat_vol_col], errors="coerce")
                    df_cons[fat_vol_col]     = pd.to_numeric(df_cons[fat_vol_col],     errors="coerce")

                    vol_fat  = df_sem_cons[fat_vol_col].sum()
                    vol_cons = df_cons[fat_vol_col].sum()
                    total_faturado          += float(vol_fat)
                    total_consumo_proprio   += float(vol_cons)
                    self._log(f"   + Faturado limpo:   {vol_fat:,.2f}")
                    self._log(f"   - Consumo próprio:  {vol_cons:,.2f}\n")
                else:
                    df[fat_vol_col] = pd.to_numeric(df[fat_vol_col], errors="coerce")
                    vol_fat = df[fat_vol_col].sum()
                    total_faturado += float(vol_fat)
                    self._log(f"   + Faturado bruto: {vol_fat:,.2f} (Sem consumo próprio)\n")

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

        self.result_label.config(text=f"Volume Final CGF: {volume_final:,.2f}")
        self.volume_final_cgf = volume_final  # disponível para outros módulos (ex: SCG)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = CGFApp(root)
    root.mainloop()
