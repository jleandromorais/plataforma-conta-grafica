import customtkinter as ctk
from tkinter import messagebox, simpledialog
from Src.Services.servicos_rpv import ServicosRPV
from Src.common.excel_final_destino import escolher_destino_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# ── Paleta ────────────────────────────────────────────────────────────────────
BG        = "#0f172a"
CARD      = "#1e293b"
INPUT_BG  = "#334155"
VERDE     = "#10b981"
AZUL      = "#3b82f6"
VERMELHO  = "#ef4444"
AMARELO   = "#f59e0b"
ROXO      = "#8b5cf6"
TEXTO     = "#f8fafc"
MUTED     = "#94a3b8"

class TelaRPV(ctk.CTkFrame):
    """RPV = CGR − CGF com entrada manual e/ou automática via banco de dados."""

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG)

        self.servicos = ServicosRPV()
        self._build_ui()
        self._carregar_periodos()

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── HEADER 
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🧾  RPV — Requisição de Pequeno Valor",
                     font=("Roboto", 20, "bold"), text_color=TEXTO).pack(side="left", padx=24, pady=20)
        ctk.CTkLabel(header, text="RPV = CGR  −  CGF",
                     font=("Roboto", 13, "bold"), text_color=ROXO).pack(side="right", padx=24)

        # ── PERÍODO
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=50)
        bar.pack(fill="x", pady=(2, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="Período:", font=("Roboto", 12), text_color=MUTED).pack(side="left", padx=(20, 6), pady=12)

        self.combo_periodo = ctk.CTkComboBox(bar, width=180, font=("Roboto", 12), command=self._ao_mudar_periodo)
        self.combo_periodo.pack(side="left", pady=12)

        ctk.CTkButton(bar, text="➕ Novo período", width=120, height=30, fg_color=AZUL, font=("Roboto", 11, "bold"),
                      command=self._criar_periodo).pack(side="left", padx=10)

        # ── FONTE DOS VALORES
        fonte_frame = ctk.CTkFrame(self, fg_color="transparent")
        fonte_frame.pack(fill="x", padx=24, pady=(16, 0))

        ctk.CTkLabel(fonte_frame, text="Fonte dos valores:", font=("Roboto", 12), text_color=MUTED).pack(side="left")

        self.btn_auto = ctk.CTkButton(fonte_frame, text="⚡ Carregar do Banco de Dados", width=220, height=34, 
                                      font=("Roboto", 12, "bold"), fg_color=VERDE, hover_color="#059669",
                                      command=self._carregar_do_banco)
        self.btn_auto.pack(side="left", padx=(10, 8))

        self.btn_limpar = ctk.CTkButton(fonte_frame, text="🗑 Limpar", width=80, height=34, font=("Roboto", 11),
                                        fg_color=INPUT_BG, hover_color=VERMELHO, command=self._limpar_campos)
        self.btn_limpar.pack(side="left")

        # ── CARTÕES CGR e CGF
        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", padx=24, pady=16)
        cards_row.columnconfigure(0, weight=1, uniform="c")
        cards_row.columnconfigure(1, weight=1, uniform="c")

        # Card CGR
        card_cgr = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_cgr.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(card_cgr, text="📄  CGR", font=("Roboto", 16, "bold"), text_color=AZUL).pack(pady=(18, 2))
        ctk.CTkLabel(card_cgr, text="Conta Gráfica de Receita\n(Auditoria XML)", font=("Roboto", 11), text_color=MUTED).pack()
        ctk.CTkFrame(card_cgr, height=1, fg_color=INPUT_BG).pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(card_cgr, text="Valor (R$):", font=("Roboto", 11), text_color=MUTED).pack(anchor="w", padx=16)

        self.entry_cgr = ctk.CTkEntry(card_cgr, placeholder_text="0,00", font=("Roboto", 18, "bold"), height=48, 
                                      justify="right", fg_color=INPUT_BG, text_color=TEXTO, border_color=AZUL, border_width=2)
        self.entry_cgr.pack(fill="x", padx=16, pady=(4, 18))
        self.entry_cgr.bind("<KeyRelease>", lambda e: self._recalcular())

        # Símbolo "−" central
        ctk.CTkLabel(cards_row, text="−", font=("Roboto", 40, "bold"), text_color=VERMELHO, width=32).grid(row=0, column=0, sticky="e", padx=(0, 4))

        # Card CGF
        card_cgf = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_cgf.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(card_cgf, text="📋  CGF", font=("Roboto", 16, "bold"), text_color=VERDE).pack(pady=(18, 2))
        ctk.CTkLabel(card_cgf, text="Conta Gráfica de Faturamento\n(Volume Faturado)", font=("Roboto", 11), text_color=MUTED).pack()
        ctk.CTkFrame(card_cgf, height=1, fg_color=INPUT_BG).pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(card_cgf, text="Valor (R$):", font=("Roboto", 11), text_color=MUTED).pack(anchor="w", padx=16)

        self.entry_cgf = ctk.CTkEntry(card_cgf, placeholder_text="0,00", font=("Roboto", 18, "bold"), height=48, 
                                      justify="right", fg_color=INPUT_BG, text_color=TEXTO, border_color=VERDE, border_width=2)
        self.entry_cgf.pack(fill="x", padx=16, pady=(4, 18))
        self.entry_cgf.bind("<KeyRelease>", lambda e: self._recalcular())

        # ── RESULTADO RPV
        res_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=14)
        res_card.pack(fill="x", padx=24, pady=(0, 16))

        row_res = ctk.CTkFrame(res_card, fg_color="transparent")
        row_res.pack(fill="x", padx=24, pady=20)

        ctk.CTkLabel(row_res, text="RPV  =  CGR  −  CGF  =", font=("Roboto", 14), text_color=MUTED).pack(side="left")
        self.lbl_rpv = ctk.CTkLabel(row_res, text="R$ 0,00", font=("Roboto", 28, "bold"), text_color=AMARELO)
        self.lbl_rpv.pack(side="left", padx=16)
        
        self.lbl_sinal = ctk.CTkLabel(row_res, text="", font=("Roboto", 13, "bold"), text_color=VERDE, width=120)
        self.lbl_sinal.pack(side="left")

        # ── BOTÕES DE AÇÃO
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 16))

        ctk.CTkButton(btn_row, text="💾  Salvar RPV no banco", font=("Roboto", 13, "bold"), height=44, width=220,
                      fg_color=ROXO, hover_color="#7c3aed", command=self._salvar_rpv).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_row, text="➕  Excel Final (Módulo 9)", font=("Roboto", 12, "bold"), height=44, width=220,
                  fg_color="#6c3483", hover_color="#884ea0", command=self._adicionar_excel_final).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_row, text="🔄  Atualizar histórico", font=("Roboto", 12), height=44, width=170,
                      fg_color=INPUT_BG, hover_color=AZUL, command=self._atualizar_historico).pack(side="left")

        # ── HISTÓRICO
        hist = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        hist.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        ctk.CTkLabel(hist, text="📅  Histórico de RPV por período", font=("Roboto", 13, "bold"), text_color=MUTED).pack(anchor="w", padx=20, pady=(14, 4))
        self.hist_box = ctk.CTkTextbox(hist, font=("Consolas", 11), fg_color=BG, text_color=MUTED, height=140)
        self.hist_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ── EVENTOS E LÓGICA ──────────────────────────────────────────────────────
    def _carregar_periodos(self):
        periodos = self.servicos.obter_periodos()
        nomes = [p["periodo"] for p in periodos]
        self.combo_periodo.configure(values=nomes if nomes else [""])
        if nomes:
            self.combo_periodo.set(nomes[0])
            self._ao_mudar_periodo(nomes[0])
        self._atualizar_historico()

    def _criar_periodo(self):
        nome = simpledialog.askstring("Novo Período", "Nome do período (ex: Dez/2025 ou Jan/2026):", initialvalue="")
        if nome and nome.strip():
            self.servicos.criar_periodo(nome)
            self._carregar_periodos()
            self.combo_periodo.set(nome.strip())
            self._ao_mudar_periodo(nome.strip())

    def _ao_mudar_periodo(self, periodo: str):
        dados = self.servicos.buscar_dados_periodo(periodo)
        if dados:
            self._preencher_campos(dados["cgr"], dados["cgf"])

    def _preencher_campos(self, cgr: float, cgf: float):
        self.entry_cgr.delete(0, "end")
        self.entry_cgr.insert(0, f"{cgr:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        self.entry_cgf.delete(0, "end")
        self.entry_cgf.insert(0, f"{cgf:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

        self._recalcular()

    def _carregar_do_banco(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione um período primeiro.")
            return

        dados = self.servicos.buscar_dados_periodo(periodo)
        if not dados:
            messagebox.showinfo("Sem dados", f"Nenhum valor encontrado para '{periodo}'.\n\nExecute os módulos CGR e CGF e salve no banco.")
            return

        self._preencher_campos(dados["cgr"], dados["cgf"])
        messagebox.showinfo("Carregado ✅", f"Valores carregados do banco:\n\n  CGR = {ServicosRPV.formatar_brl(dados['cgr'])}\n  CGF = {ServicosRPV.formatar_brl(dados['cgf'])}\n  RPV = {ServicosRPV.formatar_brl(dados['rpv'])}")

    def _limpar_campos(self):
        self.entry_cgr.delete(0, "end")
        self.entry_cgf.delete(0, "end")
        self.lbl_rpv.configure(text="R$ 0,00", text_color=AMARELO)
        self.lbl_sinal.configure(text="")

    def _recalcular(self):
        cgr = ServicosRPV.parse_brl(self.entry_cgr.get())
        cgf = ServicosRPV.parse_brl(self.entry_cgf.get())
        rpv = cgr - cgf

        self.lbl_rpv.configure(text=ServicosRPV.formatar_brl(rpv))

        if rpv > 0:
            self.lbl_rpv.configure(text_color=VERDE)
            self.lbl_sinal.configure(text="▲ CGR > CGF", text_color=VERDE)
        elif rpv < 0:
            self.lbl_rpv.configure(text_color=VERMELHO)
            self.lbl_sinal.configure(text="▼ CGR < CGF", text_color=VERMELHO)
        else:
            self.lbl_rpv.configure(text_color=AMARELO)
            self.lbl_sinal.configure(text="= Equilíbrio", text_color=AMARELO)

    def _salvar_rpv(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione ou crie um período.")
            return

        cgr = ServicosRPV.parse_brl(self.entry_cgr.get())
        cgf = ServicosRPV.parse_brl(self.entry_cgf.get())

        if cgr == 0 and cgf == 0:
            messagebox.showwarning("Aviso", "Preencha ao menos um dos valores.")
            return

        rpv = self.servicos.salvar_valores(periodo, cgr, cgf)

        self._recalcular()
        self._atualizar_historico()

        messagebox.showinfo("Salvo ✅", f"Período : {periodo}\n{'─'*32}\n  CGR  =  {ServicosRPV.formatar_brl(cgr)}\n  CGF  =  {ServicosRPV.formatar_brl(cgf)}\n{'─'*32}\n  RPV  =  {ServicosRPV.formatar_brl(rpv)}\n\nRPV salvo no banco de dados.")

    def _atualizar_historico(self):
        self.hist_box.configure(state="normal")
        self.hist_box.delete("1.0", "end")
        
        texto = self.servicos.gerar_texto_historico()
        self.hist_box.insert("end", texto)
        
        self.hist_box.configure(state="disabled")

    def _adicionar_excel_final(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione ou crie um período para adicionar ao Excel final.")
            return

        cgr = ServicosRPV.parse_brl(self.entry_cgr.get())
        cgf = ServicosRPV.parse_brl(self.entry_cgf.get())
        if cgr == 0 and cgf == 0:
            messagebox.showwarning("Aviso", "Preencha CGR/CGF antes de adicionar ao Excel final.")
            return

        self.servicos.salvar_valores(periodo, cgr, cgf)
        destino = escolher_destino_excel_final(parent=self)
        if not destino:
            return
        arquivo = ExcelConsolidado.exportar(nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅", f"Arquivo criado com sucesso:\n{arquivo}")