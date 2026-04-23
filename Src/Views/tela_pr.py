import customtkinter as ctk
from tkinter import messagebox, simpledialog

from Src.Services.servicos_pr import ServicosPR
from Src.common.excel_final_destino import registrar_execucao_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# ── Paleta ────────────────────────────────────────────────────────────────────
BG       = "#0f172a"
CARD     = "#1e293b"
INPUT_BG = "#334155"
VERDE    = "#10b981"
AZUL     = "#3b82f6"
VERMELHO = "#ef4444"
AMARELO  = "#f59e0b"
ROXO     = "#8b5cf6"
TEXTO    = "#f8fafc"
MUTED    = "#94a3b8"


class TelaPR(ctk.CTkFrame):
    """PR = (SGR + SR) / VP — cálculo por período com persistência no banco."""

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG)
        self.servicos = ServicosPR()
        self._build_ui()
        self._carregar_periodos()

    # ── CONSTRUÇÃO DA UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="💡  PR — Preço Regulatório Final",
            font=("Roboto", 20, "bold"),
            text_color=TEXTO,
        ).pack(side="left", padx=24, pady=20)

        ctk.CTkLabel(
            header,
            text="PR  =  (SGR + SR)  /  VP",
            font=("Roboto", 13, "bold"),
            text_color=AMARELO,
        ).pack(side="right", padx=24)

        # PERÍODO
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=50)
        bar.pack(fill="x", pady=(2, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(
            bar, text="Período:", font=("Roboto", 12), text_color=MUTED
        ).pack(side="left", padx=(20, 6), pady=12)

        self.combo_periodo = ctk.CTkComboBox(
            bar, width=180, font=("Roboto", 12), command=self._ao_mudar_periodo
        )
        self.combo_periodo.pack(side="left", pady=12)

        ctk.CTkButton(
            bar,
            text="➕ Novo período",
            width=120,
            height=30,
            fg_color=AZUL,
            font=("Roboto", 11, "bold"),
            command=self._criar_periodo,
        ).pack(side="left", padx=10)

        # FONTE DOS VALORES
        fonte_frame = ctk.CTkFrame(self, fg_color="transparent")
        fonte_frame.pack(fill="x", padx=24, pady=(16, 0))

        ctk.CTkLabel(
            fonte_frame, text="Fonte dos valores:", font=("Roboto", 12), text_color=MUTED
        ).pack(side="left")

        ctk.CTkButton(
            fonte_frame,
            text="⚡ Carregar do Banco de Dados",
            width=220,
            height=34,
            font=("Roboto", 12, "bold"),
            fg_color=VERDE,
            hover_color="#059669",
            command=self._carregar_do_banco,
        ).pack(side="left", padx=(10, 8))

        ctk.CTkButton(
            fonte_frame,
            text="🗑 Limpar",
            width=80,
            height=34,
            font=("Roboto", 11),
            fg_color=INPUT_BG,
            hover_color=VERMELHO,
            command=self._limpar_campos,
        ).pack(side="left")

        # CARTÕES DE ENTRADA (SGR/SCG | SR | VP)
        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", padx=24, pady=16)
        cards_row.columnconfigure(0, weight=1, uniform="c")
        cards_row.columnconfigure(1, weight=1, uniform="c")
        cards_row.columnconfigure(2, weight=1, uniform="c")

        # Card SGR/SCG
        card_scg = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_scg.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(
            card_scg,
            text="💼  SGR / SCG",
            font=("Roboto", 15, "bold"),
            text_color=ROXO,
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            card_scg,
            text="Saldo Gráfico Regulatório\n(SCG do sistema)",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_scg, height=1, fg_color=INPUT_BG).pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            card_scg, text="Valor (R$):", font=("Roboto", 11), text_color=MUTED
        ).pack(anchor="w", padx=14)

        self.entry_scg = ctk.CTkEntry(
            card_scg,
            placeholder_text="0,00",
            font=("Roboto", 16, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
            border_color=ROXO,
            border_width=2,
        )
        self.entry_scg.pack(fill="x", padx=14, pady=(4, 16))
        self.entry_scg.bind("<KeyRelease>", lambda e: self._recalcular())

        # Card SR
        card_sr = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_sr.grid(row=0, column=1, sticky="nsew", padx=6)

        ctk.CTkLabel(
            card_sr,
            text="📈  SR",
            font=("Roboto", 15, "bold"),
            text_color=VERDE,
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            card_sr,
            text="Saldo Remanescente\n(VP − VF) × PR",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_sr, height=1, fg_color=INPUT_BG).pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            card_sr, text="Valor (R$):", font=("Roboto", 11), text_color=MUTED
        ).pack(anchor="w", padx=14)

        self.entry_sr = ctk.CTkEntry(
            card_sr,
            placeholder_text="0,00",
            font=("Roboto", 16, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
            border_color=VERDE,
            border_width=2,
        )
        self.entry_sr.pack(fill="x", padx=14, pady=(4, 16))
        self.entry_sr.bind("<KeyRelease>", lambda e: self._recalcular())

        # Card VP
        card_vp = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_vp.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(
            card_vp,
            text="🔢  VP",
            font=("Roboto", 15, "bold"),
            text_color=AZUL,
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            card_vp,
            text="Volume Produzido (m³)\ndivisor da fórmula",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_vp, height=1, fg_color=INPUT_BG).pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            card_vp, text="VP (m³):", font=("Roboto", 11), text_color=MUTED
        ).pack(anchor="w", padx=14)

        self.entry_vp = ctk.CTkEntry(
            card_vp,
            placeholder_text="0,00",
            font=("Roboto", 16, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
            border_color=AZUL,
            border_width=2,
        )
        self.entry_vp.pack(fill="x", padx=14, pady=(4, 16))
        self.entry_vp.bind("<KeyRelease>", lambda e: self._recalcular())

        # RESULTADO PR
        res_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=14)
        res_card.pack(fill="x", padx=24, pady=(0, 14))

        row_res = ctk.CTkFrame(res_card, fg_color="transparent")
        row_res.pack(fill="x", padx=24, pady=18)

        ctk.CTkLabel(
            row_res,
            text="PR  =  (SGR + SR)  /  VP  =",
            font=("Roboto", 13),
            text_color=MUTED,
        ).pack(side="left")

        self.lbl_pr = ctk.CTkLabel(
            row_res,
            text="R$ 0,0000",
            font=("Roboto", 26, "bold"),
            text_color=AMARELO,
        )
        self.lbl_pr.pack(side="left", padx=16)

        self.lbl_aviso = ctk.CTkLabel(
            row_res, text="", font=("Roboto", 12, "italic"), text_color=MUTED, width=240
        )
        self.lbl_aviso.pack(side="left")

        # BOTÕES DE AÇÃO
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkButton(
            btn_row,
            text="💾  Salvar PR no banco",
            font=("Roboto", 13, "bold"),
            height=44,
            width=220,
            fg_color=ROXO,
            hover_color="#7c3aed",
            command=self._salvar_pr,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="➕  Excel Final (Módulo 9)",
            font=("Roboto", 12, "bold"),
            height=44,
            width=220,
            fg_color="#6c3483",
            hover_color="#884ea0",
            command=self._adicionar_excel_final,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🔄  Atualizar histórico",
            font=("Roboto", 12),
            height=44,
            width=170,
            fg_color=INPUT_BG,
            hover_color=AZUL,
            command=self._atualizar_historico,
        ).pack(side="left")

        # HISTÓRICO
        hist = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        hist.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        ctk.CTkLabel(
            hist,
            text="📅  Histórico de PR por período",
            font=("Roboto", 13, "bold"),
            text_color=MUTED,
        ).pack(anchor="w", padx=20, pady=(14, 4))

        self.hist_box = ctk.CTkTextbox(
            hist, font=("Consolas", 11), fg_color=BG, text_color=MUTED, height=140
        )
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
        nome = simpledialog.askstring(
            "Novo Período",
            "Nome do período (ex: Dez/2025 ou Jan/2026):",
            initialvalue="",
        )
        if nome and nome.strip():
            self.servicos.criar_periodo(nome)
            self._carregar_periodos()
            self.combo_periodo.set(nome.strip())
            self._ao_mudar_periodo(nome.strip())

    def _ao_mudar_periodo(self, periodo: str):
        dados = self.servicos.buscar_dados_periodo(periodo)
        if dados:
            self._preencher_campos(dados["scg"], dados["sr"], dados["vp"])

    def _preencher_campos(self, scg: float, sr: float, vp: float):
        def _fmt(v: float) -> str:
            return f"{(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        self.entry_scg.delete(0, "end")
        self.entry_scg.insert(0, _fmt(scg))
        self.entry_sr.delete(0, "end")
        self.entry_sr.insert(0, _fmt(sr))
        self.entry_vp.delete(0, "end")
        self.entry_vp.insert(0, _fmt(vp))
        self._recalcular()

    def _carregar_do_banco(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione um período primeiro.")
            return

        dados = self.servicos.buscar_dados_periodo(periodo)
        if not dados or (dados["scg"] == 0 and dados["sr"] == 0 and dados["vp"] == 0):
            messagebox.showinfo(
                "Sem dados",
                f"Nenhum valor encontrado para '{periodo}'.\n\n"
                "Execute os módulos SCG e SR e salve no banco.",
            )
            return

        self._preencher_campos(dados["scg"], dados["sr"], dados["vp"])
        messagebox.showinfo(
            "Carregado ✅",
            f"Valores carregados do banco:\n\n"
            f"  SGR/SCG = {ServicosPR.formatar_brl(dados['scg'])}\n"
            f"  SR      = {ServicosPR.formatar_brl(dados['sr'])}\n"
            f"  VP      = {ServicosPR.formatar_volume(dados['vp'])}\n"
            f"  PR      = {ServicosPR.formatar_pr(dados['pr'])}",
        )

    def _limpar_campos(self):
        self.entry_scg.delete(0, "end")
        self.entry_sr.delete(0, "end")
        self.entry_vp.delete(0, "end")
        self.lbl_pr.configure(text="R$ 0,0000", text_color=AMARELO)
        self.lbl_aviso.configure(text="")

    def _recalcular(self):
        scg = ServicosPR.parse_brl(self.entry_scg.get())
        sr = ServicosPR.parse_brl(self.entry_sr.get())
        vp = ServicosPR.parse_brl(self.entry_vp.get())
        pr = ServicosPR.calcular_pr(scg, sr, vp)

        self.lbl_pr.configure(text=ServicosPR.formatar_pr(pr))

        if vp == 0:
            self.lbl_pr.configure(text_color=AMARELO)
            self.lbl_aviso.configure(
                text="⚠ VP = 0  →  PR = 0 (evita divisão por zero)", text_color=AMARELO
            )
        elif pr > 0:
            self.lbl_pr.configure(text_color=VERDE)
            self.lbl_aviso.configure(text="▲ Resultado positivo", text_color=VERDE)
        else:
            self.lbl_pr.configure(text_color=VERMELHO)
            self.lbl_aviso.configure(text="▼ Resultado negativo", text_color=VERMELHO)

    def _salvar_pr(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione ou crie um período.")
            return

        scg = ServicosPR.parse_brl(self.entry_scg.get())
        sr = ServicosPR.parse_brl(self.entry_sr.get())
        vp = ServicosPR.parse_brl(self.entry_vp.get())

        if scg == 0 and sr == 0 and vp == 0:
            messagebox.showwarning("Aviso", "Preencha ao menos um dos valores.")
            return

        pr = self.servicos.salvar_valores(periodo, scg, sr, vp)

        self._recalcular()
        self._atualizar_historico()

        messagebox.showinfo(
            "Salvo ✅",
            f"Período : {periodo}\n{'─' * 32}\n"
            f"  SGR/SCG = {ServicosPR.formatar_brl(scg)}\n"
            f"  SR      = {ServicosPR.formatar_brl(sr)}\n"
            f"  VP      = {ServicosPR.formatar_volume(vp)}\n"
            f"{'─' * 32}\n"
            f"  PR      = {ServicosPR.formatar_pr(pr)}\n\n"
            "PR salvo no banco de dados.",
        )

    def _atualizar_historico(self):
        self.hist_box.configure(state="normal")
        self.hist_box.delete("1.0", "end")
        self.hist_box.insert("end", self.servicos.gerar_texto_historico())
        self.hist_box.configure(state="disabled")

    def _adicionar_excel_final(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione ou crie um período para adicionar ao Excel final.")
            return

        scg = ServicosPR.parse_brl(self.entry_scg.get())
        sr = ServicosPR.parse_brl(self.entry_sr.get())
        vp = ServicosPR.parse_brl(self.entry_vp.get())
        if scg == 0 and sr == 0 and vp == 0:
            messagebox.showwarning("Aviso", "Preencha os campos antes de adicionar ao Excel final.")
            return

        self.servicos.salvar_valores(periodo, scg, sr, vp)
        meta_execucao = registrar_execucao_excel_final(etapa="PR", periodo=periodo, parent=self)
        if not meta_execucao:
            return
        destino, nome_sessao, periodo_norm, execucao = meta_execucao
        arquivo = ExcelConsolidado.exportar(periodo=periodo_norm, nome_arquivo=destino)
        messagebox.showinfo(
            "Excel final gerado ✅",
            f"Arquivo criado com sucesso:\n{arquivo}\n\n"
            f"Sessão: {nome_sessao}\nPeríodo: {periodo_norm}\n"
            f"Etapa PR registrada (execução #{execucao}).",
        )


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste TelaPR (embed)")
    root.geometry("1000x750")
    TelaPR(root).pack(fill="both", expand=True)
    root.mainloop()
