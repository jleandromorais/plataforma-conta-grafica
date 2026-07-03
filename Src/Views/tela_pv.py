import customtkinter as ctk
from tkinter import messagebox, simpledialog

from Src.config import ui_theme as ui
from Src.Services.servicos_pv import ServicosPV
from Src.common.excel_final_destino import registrar_execucao_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# Paleta (aliases do design system central — ver Src/config/ui_theme.py)
BG = ui.COR_FUNDO
CARD = ui.COR_CARD
INPUT_BG = ui.COR_INPUT
VERDE = ui.COR_SUCESSO
AZUL = ui.COR_PRIMARIA
VERMELHO = ui.COR_PERIGO
AMARELO = ui.COR_DESTAQUE
ROXO = ui.COR_ROXO
TEXTO = ui.COR_TEXTO
MUTED = ui.COR_MUTED


class TelaPV(ctk.CTkFrame):
    """PV = PMPV + PR — preço final para fechamento da conta gráfica."""

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG)
        self.servicos = ServicosPV()
        self._build_ui()
        self._carregar_periodos()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="💰  PV — Preço Final",
            font=("Roboto", 20, "bold"),
            text_color=TEXTO,
        ).pack(side="left", padx=24, pady=20)

        ctk.CTkLabel(
            header,
            text="PV  =  PMPV  +  PR",
            font=("Roboto", 13, "bold"),
            text_color=AMARELO,
        ).pack(side="right", padx=24)

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

        cards_row = ctk.CTkFrame(self, fg_color="transparent")
        cards_row.pack(fill="x", padx=24, pady=16)
        cards_row.columnconfigure(0, weight=1, uniform="c")
        cards_row.columnconfigure(1, weight=1, uniform="c")

        card_pmpv = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_pmpv.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ctk.CTkLabel(
            card_pmpv,
            text="📊  PMPV",
            font=("Roboto", 16, "bold"),
            text_color=AZUL,
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            card_pmpv,
            text="Preço médio mensal\n(R$/m³)",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_pmpv, height=1, fg_color=INPUT_BG).pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            card_pmpv, text="PMPV (R$/m³):", font=("Roboto", 11), text_color=MUTED
        ).pack(anchor="w", padx=14)

        self.entry_pmpv = ctk.CTkEntry(
            card_pmpv,
            placeholder_text="0,0000",
            font=("Roboto", 16, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
            border_color=AZUL,
            border_width=2,
        )
        self.entry_pmpv.pack(fill="x", padx=14, pady=(4, 16))
        self.entry_pmpv.bind("<KeyRelease>", lambda e: self._recalcular())

        card_pr = ctk.CTkFrame(cards_row, fg_color=CARD, corner_radius=12)
        card_pr.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ctk.CTkLabel(
            card_pr,
            text="💡  PR",
            font=("Roboto", 16, "bold"),
            text_color=ROXO,
        ).pack(pady=(16, 2))
        ctk.CTkLabel(
            card_pr,
            text="Preço regulatório final\n(R$/m³)",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_pr, height=1, fg_color=INPUT_BG).pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(
            card_pr, text="PR (R$/m³):", font=("Roboto", 11), text_color=MUTED
        ).pack(anchor="w", padx=14)

        self.entry_pr = ctk.CTkEntry(
            card_pr,
            placeholder_text="0,0000",
            font=("Roboto", 16, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
            border_color=ROXO,
            border_width=2,
        )
        self.entry_pr.pack(fill="x", padx=14, pady=(4, 16))
        self.entry_pr.bind("<KeyRelease>", lambda e: self._recalcular())

        res_card = ctk.CTkFrame(self, fg_color=ui.COR_REALCE, corner_radius=14)
        res_card.pack(fill="x", padx=24, pady=(0, 14))

        row_res = ctk.CTkFrame(res_card, fg_color="transparent")
        row_res.pack(fill="x", padx=24, pady=18)

        ctk.CTkLabel(
            row_res,
            text="PV  =  PMPV  +  PR  =",
            font=("Roboto", 13),
            text_color=MUTED,
        ).pack(side="left")

        self.lbl_pv = ctk.CTkLabel(
            row_res,
            text="R$ 0,0000",
            font=("Roboto", 26, "bold"),
            text_color=AMARELO,
        )
        self.lbl_pv.pack(side="left", padx=16)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 14))

        ctk.CTkButton(
            btn_row,
            text="💾  Salvar PV no banco",
            font=("Roboto", 13, "bold"),
            height=44,
            width=220,
            fg_color=VERDE,
            hover_color="#059669",
            command=self._salvar_pv,
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

        hist = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        hist.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        ctk.CTkLabel(
            hist,
            text="📅  Histórico de PV por período",
            font=("Roboto", 13, "bold"),
            text_color=MUTED,
        ).pack(anchor="w", padx=20, pady=(14, 4))

        self.hist_box = ctk.CTkTextbox(
            hist, font=("Consolas", 11), fg_color=BG, text_color=MUTED, height=140
        )
        self.hist_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

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
            self._preencher_campos(dados["pmpv"], dados["pr"])

    def _preencher_campos(self, pmpv: float, pr: float):
        from Src.common.formatting import format_brl4_plain
        self.entry_pmpv.delete(0, "end")
        self.entry_pmpv.insert(0, format_brl4_plain(pmpv))
        self.entry_pr.delete(0, "end")
        self.entry_pr.insert(0, format_brl4_plain(pr))
        self._recalcular()

    def _carregar_do_banco(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione um período primeiro.")
            return

        dados = self.servicos.buscar_dados_periodo(periodo)
        if not dados or (dados["pmpv"] == 0 and dados["pr"] == 0):
            messagebox.showinfo(
                "Sem dados",
                f"Nenhum valor encontrado para '{periodo}'.\n\n"
                "Execute os módulos PMPV e PR e salve no banco.",
            )
            return

        self._preencher_campos(dados["pmpv"], dados["pr"])
        messagebox.showinfo(
            "Carregado ✅",
            f"Valores carregados do banco:\n\n"
            f"  PMPV = {ServicosPV.formatar_brl(dados['pmpv'])}\n"
            f"  PR   = {ServicosPV.formatar_brl(dados['pr'])}\n"
            f"  PV   = {ServicosPV.formatar_brl(dados['pv'])}",
        )

    def _limpar_campos(self):
        self.entry_pmpv.delete(0, "end")
        self.entry_pr.delete(0, "end")
        self.lbl_pv.configure(text="R$ 0,0000", text_color=AMARELO)

    def _recalcular(self):
        pmpv = ServicosPV.parse_brl(self.entry_pmpv.get())
        pr = ServicosPV.parse_brl(self.entry_pr.get())
        pv = ServicosPV.calcular_pv(pmpv, pr)

        self.lbl_pv.configure(text=ServicosPV.formatar_brl(pv))
        if pv > 0:
            self.lbl_pv.configure(text_color=VERDE)
        elif pv < 0:
            self.lbl_pv.configure(text_color=VERMELHO)
        else:
            self.lbl_pv.configure(text_color=AMARELO)

        # Auto-save silencioso
        periodo = self.combo_periodo.get()
        if periodo and (pmpv != 0 or pr != 0):
            try:
                self.servicos.salvar_valores(periodo, pmpv, pr)
                self._atualizar_historico()
            except Exception:
                pass

    def _salvar_pv(self):
        periodo = self.combo_periodo.get()
        if not periodo:
            messagebox.showwarning("Aviso", "Selecione ou crie um período.")
            return

        pmpv = ServicosPV.parse_brl(self.entry_pmpv.get())
        pr = ServicosPV.parse_brl(self.entry_pr.get())

        if pmpv == 0 and pr == 0:
            messagebox.showwarning("Aviso", "Preencha ao menos um dos valores.")
            return

        pv = self.servicos.salvar_valores(periodo, pmpv, pr)

        self._recalcular()
        self._atualizar_historico()

        messagebox.showinfo(
            "Salvo ✅",
            f"Período : {periodo}\n{'─' * 32}\n"
            f"  PMPV = {ServicosPV.formatar_brl(pmpv)}\n"
            f"  PR   = {ServicosPV.formatar_brl(pr)}\n"
            f"{'─' * 32}\n"
            f"  PV   = {ServicosPV.formatar_brl(pv)}\n\n"
            "PV salvo no banco de dados.",
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

        pmpv = ServicosPV.parse_brl(self.entry_pmpv.get())
        pr = ServicosPV.parse_brl(self.entry_pr.get())
        if pmpv == 0 and pr == 0:
            messagebox.showwarning("Aviso", "Preencha os campos antes de adicionar ao Excel final.")
            return

        self.servicos.salvar_valores(periodo, pmpv, pr)
        meta_execucao = registrar_execucao_excel_final(etapa="PV", periodo=periodo, parent=self)
        if not meta_execucao:
            return

        destino, nome_sessao, periodo_norm, execucao = meta_execucao
        arquivo = ExcelConsolidado.exportar(periodo=periodo_norm, nome_arquivo=destino)
        messagebox.showinfo(
            "Excel final gerado ✅",
            f"Arquivo criado com sucesso:\n{arquivo}\n\n"
            f"Sessão: {nome_sessao}\nPeríodo: {periodo_norm}\n"
            f"Etapa PV registrada (execução #{execucao}).",
        )


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste TelaPV (embed)")
    root.geometry("980x730")
    TelaPV(root).pack(fill="both", expand=True)
    root.mainloop()
