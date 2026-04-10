import customtkinter as ctk
from tkinter import messagebox

from tkinter import simpledialog

from Src.Services.servicos_sr import ServicosSR
from Src.Database.database import DatabasePMPV
from Src.common.excel_final_destino import escolher_destino_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado


BG = "#0f172a"
CARD = "#1e293b"
INPUT_BG = "#334155"
VERDE = "#10b981"
VERMELHO = "#ef4444"
AMARELO = "#f59e0b"
AZUL = "#3b82f6"
TEXTO = "#f8fafc"
MUTED = "#94a3b8"
ROXO = "#8b5cf6"


def _parse_float(val: str) -> float:
    """Converte strings '1.234,56' ou '1234.56' em float. Retorna 0.0 em erro."""
    if not val:
        return 0.0
    txt = val.strip()
    last_dot = txt.rfind(".")
    last_comma = txt.rfind(",")
    if last_comma > last_dot:
        txt = txt.replace(".", "").replace(",", ".")
    elif last_dot > last_comma and last_comma >= 0:
        txt = txt.replace(",", "")
    else:
        if last_dot >= 0:
            after = txt[last_dot + 1:]
            if len(after) == 3 and after.isdigit():
                txt = txt.replace(".", "")
    negativo = txt.startswith("-")
    txt = "".join(c for c in txt if c.isdigit() or c == ".")
    if negativo:
        txt = "-" + txt
    try:
        return float(txt)
    except ValueError:
        return 0.0


def _fmt_vol(valor: float) -> str:
    texto = f"{valor:,.2f}"
    inteiro, decimal = texto.split(".")
    inteiro = inteiro.replace(",", ".")
    decimal = decimal.rstrip("0")
    return f"{inteiro},{decimal}" if decimal else inteiro


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


class TelaSR(ctk.CTkFrame):
    """
    SR = (VP − VF) × PR

    - VP: Volume Produzido (PMPV)
    - VF: Volume Faturado (PMPV)
    - PR: Preço/Parâmetro regulatório aplicado sobre a diferença de volume
    """

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG)

        self._servicos = ServicosSR()
        self._sessoes: list[dict] = []
        self._periodos_vf: list[str] = []

        self._build_ui()
        self._carregar_sessoes()

    # ── CONSTRUÇÃO DA UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="📈  SR — Saldo remanescente",
            font=("Roboto", 20, "bold"),
            text_color=TEXTO,
        ).pack(side="left", padx=24, pady=20)

        ctk.CTkLabel(
            header,
            text="SR  =  (VP − VF) × PR",
            font=("Roboto", 13, "bold"),
            text_color=AMARELO,
        ).pack(side="right", padx=24)

        # PAINEL — CARREGAR DO BANCO
        bd_card = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=12)
        bd_card.pack(fill="x", padx=24, pady=(14, 4))

        ctk.CTkLabel(
            bd_card,
            text="📥  Carregar VP e VF do Banco de Dados (Sessões PMPV)",
            font=("Roboto", 13, "bold"),
            text_color=AZUL,
        ).pack(anchor="w", padx=18, pady=(12, 4))

        row_bd = ctk.CTkFrame(bd_card, fg_color="transparent")
        row_bd.pack(fill="x", padx=18, pady=(0, 8))

        ctk.CTkLabel(
            row_bd, text="VP:", font=("Roboto", 12), text_color=MUTED, width=60
        ).pack(side="left")

        self.combo_sessao = ctk.CTkComboBox(
            row_bd,
            width=380,
            font=("Roboto", 12),
            state="readonly",
            values=["(nenhuma sessão salva)"],
        )
        self.combo_sessao.pack(side="left", padx=(6, 10))

        ctk.CTkButton(
            row_bd,
            text="⚡ Carregar VP e VF",
            width=160,
            height=34,
            font=("Roboto", 12, "bold"),
            fg_color=VERDE,
            hover_color="#059669",
            command=self._carregar_do_banco,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            row_bd,
            text="🔄 Atualizar lista",
            width=120,
            height=34,
            font=("Roboto", 11),
            fg_color=INPUT_BG,
            hover_color=AZUL,
            command=self._carregar_sessoes,
        ).pack(side="left")

        row_vf = ctk.CTkFrame(bd_card, fg_color="transparent")
        row_vf.pack(fill="x", padx=18, pady=(0, 14))

        ctk.CTkLabel(
            row_vf, text="Período VF:", font=("Roboto", 12), text_color=MUTED, width=80
        ).pack(side="left")

        self.combo_periodo_vf = ctk.CTkComboBox(
            row_vf,
            width=220,
            font=("Roboto", 12),
            state="readonly",
            values=["(sem período CGF)"],
        )
        self.combo_periodo_vf.pack(side="left", padx=(6, 10))

        ctk.CTkLabel(
            row_vf,
            text="Selecione o período para puxar o VF do CGF.",
            font=("Roboto", 11),
            text_color=MUTED,
        ).pack(side="left")

        # BADGE de origem
        self.lbl_origem = ctk.CTkLabel(
            bd_card,
            text="",
            font=("Roboto", 11, "italic"),
            text_color=MUTED,
        )
        self.lbl_origem.pack(anchor="w", padx=18, pady=(0, 8))

        # INPUTS VP / VF
        inputs = ctk.CTkFrame(self, fg_color="transparent")
        inputs.pack(fill="x", padx=24, pady=(8, 4))
        inputs.columnconfigure(0, weight=1, uniform="c")
        inputs.columnconfigure(1, weight=1, uniform="c")

        card_vp = ctk.CTkFrame(inputs, fg_color=CARD, corner_radius=12)
        card_vp.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=4)

        ctk.CTkLabel(
            card_vp,
            text="VP — Volume Produzido",
            font=("Roboto", 14, "bold"),
            text_color=TEXTO,
        ).pack(pady=(14, 2))
        ctk.CTkLabel(
            card_vp,
            text="Soma dos volumes diários das empresas (m³/dia)",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_vp, height=1, fg_color=INPUT_BG).pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(card_vp, text="VP (m³):", font=("Roboto", 11), text_color=MUTED).pack(
            anchor="w", padx=16
        )
        self.entry_vp = ctk.CTkEntry(
            card_vp,
            placeholder_text="0,00",
            font=("Roboto", 18, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
        )
        self.entry_vp.pack(fill="x", padx=16, pady=(4, 16))
        self.entry_vp.bind("<KeyRelease>", lambda e: self._recalcular())

        card_vf = ctk.CTkFrame(inputs, fg_color=CARD, corner_radius=12)
        card_vf.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=4)

        ctk.CTkLabel(
            card_vf,
            text="VF — Volume Faturado",
            font=("Roboto", 14, "bold"),
            text_color=TEXTO,
        ).pack(pady=(14, 2))
        ctk.CTkLabel(
            card_vf,
            text="Volume total faturado no trimestre (m³)",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_vf, height=1, fg_color=INPUT_BG).pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(card_vf, text="VF (m³):", font=("Roboto", 11), text_color=MUTED).pack(
            anchor="w", padx=16
        )
        self.entry_vf = ctk.CTkEntry(
            card_vf,
            placeholder_text="0,00",
            font=("Roboto", 18, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
        )
        self.entry_vf.pack(fill="x", padx=16, pady=(4, 16))
        self.entry_vf.bind("<KeyRelease>", lambda e: self._recalcular())

        # INPUT PR
        card_pr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        card_pr.pack(fill="x", padx=24, pady=(0, 8))

        ctk.CTkLabel(
            card_pr,
            text="PR — Preço / Parâmetro Regulatório",
            font=("Roboto", 14, "bold"),
            text_color=TEXTO,
        ).pack(pady=(12, 2))
        ctk.CTkLabel(
            card_pr,
            text="Parâmetro aplicado sobre a diferença (VP − VF)  |  Ex.: R$/m³",
            font=("Roboto", 10),
            text_color=MUTED,
        ).pack()
        ctk.CTkFrame(card_pr, height=1, fg_color=INPUT_BG).pack(fill="x", padx=16, pady=10)
        ctk.CTkLabel(
            card_pr, text="PR (R$/m³ ou unidade equivalente):", font=("Roboto", 11), text_color=MUTED
        ).pack(anchor="w", padx=16)
        self.entry_pr = ctk.CTkEntry(
            card_pr,
            placeholder_text="0,0000",
            font=("Roboto", 18, "bold"),
            height=46,
            justify="right",
            fg_color=INPUT_BG,
            text_color=TEXTO,
        )
        self.entry_pr.pack(fill="x", padx=16, pady=(4, 14))
        self.entry_pr.bind("<KeyRelease>", lambda e: self._recalcular())

        # RESULTADO SR
        res_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=14)
        res_card.pack(fill="x", padx=24, pady=(0, 10))

        row_res = ctk.CTkFrame(res_card, fg_color="transparent")
        row_res.pack(fill="x", padx=24, pady=16)

        ctk.CTkLabel(
            row_res,
            text="SR  =  (VP − VF) × PR  =",
            font=("Roboto", 14),
            text_color=MUTED,
        ).pack(side="left")

        self.lbl_sr = ctk.CTkLabel(
            row_res,
            text="R$ 0,00",
            font=("Roboto", 26, "bold"),
            text_color=AMARELO,
        )
        self.lbl_sr.pack(side="left", padx=16)

        self.lbl_diff = ctk.CTkLabel(
            row_res,
            text="ΔV = 0,00 m³",
            font=("Roboto", 13),
            text_color=TEXTO,
        )
        self.lbl_diff.pack(side="left", padx=8)

        # BOTÕES
        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(0, 18))

        ctk.CTkButton(
            btn_row,
            text="⚡  Calcular SR",
            font=("Roboto", 14, "bold"),
            height=42,
            width=180,
            fg_color=VERDE,
            hover_color="#059669",
            command=self._on_calcular_click,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row,
            text="💾  Salvar SR no BD",
            font=("Roboto", 12, "bold"),
            height=42,
            width=160,
            fg_color=ROXO,
            hover_color="#5b2c6f",
            command=self._salvar_sr,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            btn_row,
            text="➕  Excel Final (Módulo 9)",
            font=("Roboto", 12, "bold"),
            height=42,
            width=200,
            fg_color="#6c3483",
            hover_color="#884ea0",
            command=self._adicionar_excel_final,
        ).pack(side="left", padx=(10, 0))

        ctk.CTkButton(
            btn_row,
            text="🗑  Limpar",
            font=("Roboto", 12),
            height=42,
            width=110,
            fg_color=INPUT_BG,
            hover_color=VERMELHO,
            command=self._limpar,
        ).pack(side="left", padx=(10, 0))

    # ── LÓGICA E EVENTOS ─────────────────────────────────────────────────────

    def _carregar_sessoes(self):
        """Atualiza o combo com as sessões disponíveis no banco de dados."""
        self._sessoes = self._servicos.listar_sessoes()
        self._carregar_periodos_vf()

        if not self._sessoes:
            self.combo_sessao.configure(values=["(nenhuma sessão salva)"])
            self.combo_sessao.set("(nenhuma sessão salva)")
            return

        labels = [
            f"{s['nome']}  —  VP: {_fmt_vol(s['vp'])}  |  VF: {_fmt_vol(s['vf'])}  [{s['data_criacao']}]"
            for s in self._sessoes
        ]
        self.combo_sessao.configure(values=labels)
        self.combo_sessao.set(labels[0])

    def _carregar_periodos_vf(self):
        db = DatabasePMPV()
        try:
            self._periodos_vf = sorted(
                {
                    str(item.get("periodo", "")).strip()
                    for item in db.listar_cgf_resumos()
                    if str(item.get("periodo", "")).strip()
                },
                reverse=True,
            )
        finally:
            db.fechar()

        if not self._periodos_vf:
            self.combo_periodo_vf.configure(values=["(sem período CGF)"])
            self.combo_periodo_vf.set("(sem período CGF)")
            return

        self.combo_periodo_vf.configure(values=self._periodos_vf)
        self.combo_periodo_vf.set(self._periodos_vf[0])

    def _carregar_do_banco(self):
        """Preenche VP da sessão PMPV e VF do cgf_resumo pelo período informado."""
        if not self._sessoes:
            messagebox.showinfo(
                "Sem sessões",
                "Nenhuma sessão PMPV encontrada no banco de dados.\n\n"
                "Acesse o módulo 'Gestão PMPV', calcule e salve uma sessão primeiro.",
            )
            return

        idx = self.combo_sessao.cget("values").index(self.combo_sessao.get())
        sessao = self._sessoes[idx]

        vp = sessao.get("vp") or 0.0

        # VF vem do cgf_resumo (processado pelo módulo CGF)
        periodo = self.combo_periodo_vf.get().strip()
        if not periodo or periodo.startswith("("):
            messagebox.showwarning(
                "Período VF",
                "Selecione um período de VF no painel antes de carregar.",
            )
            return

        vf = 0.0
        if periodo and periodo.strip():
            from Src.Services.servicos_pmpv import ExcelPMPV
            db = DatabasePMPV()
            try:
                resumo = db.buscar_cgf_resumo(periodo.strip())
                if not resumo:
                    periodo_norm = ExcelPMPV._normalizar_mes(periodo.strip())
                    for item in db.listar_cgf_resumos():
                        if ExcelPMPV._normalizar_mes(str(item.get("periodo", ""))) == periodo_norm:
                            resumo = item
                            break
                if resumo and resumo.get("volume_final") is not None:
                    vf = float(resumo["volume_final"])
                else:
                    messagebox.showwarning(
                        "VF não encontrado",
                        f"Nenhum dado CGF encontrado para '{periodo.strip()}'.\n"
                        "Processe as NFs desse período no módulo CGF primeiro.\n\n"
                        "VF foi deixado em 0.",
                    )
            finally:
                db.fechar()

        self._set_entry(self.entry_vp, vp)
        self._set_entry(self.entry_vf, vf)

        self.lbl_origem.configure(
            text=f"✅  Sessão: '{sessao['nome']}'  —  Período VF: '{periodo}'  —  VP = {_fmt_vol(vp)}  |  VF = {_fmt_vol(vf)}",
            text_color=VERDE if vf > 0 else AMARELO,
        )
        self._recalcular()

    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, valor: float):
        entry.delete(0, "end")
        entry.insert(0, _fmt_vol(valor).replace(" m³", ""))

    def _obter_valores(self) -> tuple[float, float, float]:
        return (
            _parse_float(self.entry_vp.get()),
            _parse_float(self.entry_vf.get()),
            _parse_float(self.entry_pr.get()),
        )

    def _recalcular(self):
        vp, vf, pr = self._obter_valores()
        diff = vp - vf
        sr = diff * pr

        self.lbl_sr.configure(text=_fmt_brl(sr))
        self.lbl_diff.configure(
            text=f"ΔV = {_fmt_vol(diff)}"
        )

        if sr > 0:
            self.lbl_sr.configure(text_color=VERDE)
        elif sr < 0:
            self.lbl_sr.configure(text_color=VERMELHO)
        else:
            self.lbl_sr.configure(text_color=AMARELO)

    def _on_calcular_click(self):
        vp, vf, pr = self._obter_valores()
        if vp == 0 and vf == 0 and pr == 0:
            messagebox.showwarning(
                "Aviso",
                "Preencha pelo menos um dos campos (VP, VF ou PR) antes de calcular.",
            )
            return
        self._recalcular()

    def _salvar_sr(self):
        vp, vf, pr = self._obter_valores()
        if vp == 0 and vf == 0 and pr == 0:
            messagebox.showwarning("Aviso", "Preencha os campos antes de salvar.")
            return

        periodo = simpledialog.askstring(
            "Salvar SR", "Digite o período (ex: Dez/2025):", parent=self
        )
        if not periodo:
            return

        diff = vp - vf
        sr = diff * pr

        try:
            db = DatabasePMPV()
            db.salvar_sr(periodo, vp, vf, pr, sr)
            db.fechar()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível salvar no banco:\n{e}")
            return

        self.lbl_origem.configure(
            text=f"✅  SR salvo para '{periodo}'  —  SR = {_fmt_brl(sr)}",
            text_color=VERDE,
        )
        messagebox.showinfo(
            "Salvo ✅",
            f"Período: {periodo}\n"
            f"VP = {_fmt_vol(vp)} m³\n"
            f"VF = {_fmt_vol(vf)} m³\n"
            f"PR = {_fmt_brl(pr)}\n"
            f"SR = {_fmt_brl(sr)}"
        )

    def _limpar(self):
        self.entry_vp.delete(0, "end")
        self.entry_vf.delete(0, "end")
        self.entry_pr.delete(0, "end")
        self.lbl_sr.configure(text="R$ 0,00", text_color=AMARELO)
        self.lbl_diff.configure(text="ΔV = 0,00 m³")
        self.lbl_origem.configure(text="")

    def _adicionar_excel_final(self):
        vp, vf, pr = self._obter_valores()
        if vp == 0 and vf == 0 and pr == 0:
            messagebox.showwarning("Aviso", "Preencha os campos de SR antes de adicionar ao Excel final.")
            return

        periodo = simpledialog.askstring(
            "Excel Final (Módulo 9)",
            "Período para salvar e gerar o Excel final (ex: Dez/2025):\nDeixe em branco para gerar com todos os períodos.",
            parent=self,
        )
        if periodo is None:
            return

        periodo_salvar = periodo.strip() if periodo.strip() else "Geral"
        diff = vp - vf
        sr = diff * pr

        db = DatabasePMPV()
        try:
            db.salvar_sr(periodo_salvar, vp, vf, pr, sr)
        finally:
            db.fechar()

        destino = escolher_destino_excel_final(periodo=periodo.strip() if periodo.strip() else None, parent=self)
        if not destino:
            return
        arquivo = ExcelConsolidado.exportar(periodo=periodo.strip() if periodo.strip() else None, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅", f"Arquivo criado com sucesso:\n{arquivo}")


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste SR (embed)")
    root.geometry("900x700")
    TelaSR(root).pack(fill="both", expand=True)
    root.mainloop()
