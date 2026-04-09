import customtkinter as ctk
from tkinter import messagebox, simpledialog
from Src.Services.servicos_scg import ServicosSCG
from Src.common.excel_final_destino import escolher_destino_excel_final, remover_excel_final_ativo
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# ── Cores ────────────────────────────────────────────────────────────────────
COR_CARD     = "#1e293b" 
COR_FUNDO    = "#0f172a" 
COR_INPUT    = "#334155" 
COR_VERDE    = "#10b981"
COR_AZUL     = "#3b82f6"
COR_VERMELHO = "#ef4444"
COR_AMARELO  = "#f59e0b"
COR_ROXO     = "#8b5cf6"
COR_TEXTO    = "#f8fafc"
COR_MUTED    = "#94a3b8"

class LinhaValor(ctk.CTkFrame):
    def __init__(self, parent, icone: str, nome: str, key: str, cor_icone: str = COR_AZUL, editavel: bool = True):
        super().__init__(parent, fg_color="transparent")
        self.key = key
        self.editavel = editavel

        ctk.CTkLabel(self, text=icone, font=("Segoe UI Emoji", 18), width=36, text_color=cor_icone).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self, text=nome, font=("Roboto", 13), width=200, anchor="w", text_color=COR_TEXTO).pack(side="left")

        self.badge = ctk.CTkLabel(self, text="BD", font=("Roboto", 10, "bold"), width=52, height=22, corner_radius=11, fg_color=COR_VERDE, text_color="white")
        self.badge.pack(side="left", padx=8)

        self.lbl_valor = ctk.CTkLabel(self, text="R$ 0,00", font=("Roboto", 15, "bold"), width=190, height=36, corner_radius=8, fg_color=COR_INPUT, text_color=COR_TEXTO, anchor="e")
        self.lbl_valor.pack(side="left", padx=8)

        self.entry = ctk.CTkEntry(self, placeholder_text="0,00", font=("Roboto", 14), width=190, height=36)

    def set_valor(self, valor: float, origem: str = "BD"):
        self.lbl_valor.configure(text=ServicosSCG.formatar_brl(valor))
        if origem == "BD": self.badge.configure(text="📥 BD", fg_color=COR_VERDE)
        elif origem == "Manual": self.badge.configure(text="✏️ Manual", fg_color=COR_AMARELO)
        elif origem == "Calc": self.badge.configure(text="🔢 Calc", fg_color=COR_ROXO)

    def get_valor_entry(self) -> float:
        txt = self.entry.get().strip()
        if not txt: return 0.0

        last_dot = txt.rfind(".")
        last_comma = txt.rfind(",")

        if last_comma > last_dot: txt = txt.replace(".", "").replace(",", ".")
        elif last_dot > last_comma and last_comma >= 0: txt = txt.replace(",", "")
        else:
            if last_dot >= 0:
                after = txt[last_dot + 1:]
                if len(after) == 3 and after.isdigit(): txt = txt.replace(".", "")

        negativo = txt.startswith("-")
        txt = "".join(c for c in txt if c.isdigit() or c == ".")
        if negativo: txt = "-" + txt
            
        try: return float(txt)
        except ValueError: return 0.0

    def set_entry_value(self, valor: float):
        self.entry.delete(0, "end")
        txt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.entry.insert(0, txt)

    def mostrar_modo_auto(self):
        self.entry.pack_forget()
        self.lbl_valor.pack(side="left", padx=8)

    def mostrar_modo_manual(self):
        if self.editavel:
            self.lbl_valor.pack_forget()
            self.entry.pack(side="left", padx=8)


class TelaSCG(ctk.CTkFrame):
    CAMPOS = [
        ("cgr", "📄", "CGR  (Auditoria XML)",    COR_AZUL,    True),
        ("cgf", "📋", "CGF  (Volume Faturado)",  COR_VERDE,   True),
        ("rpv", "🔢", "RPV  = CGR − CGF",        COR_ROXO,    False),
        ("ret", "⚡", "RET  (Encargos)",          COR_AMARELO, True),
        ("rp",  "🔄", "RP   (Conciliação)",       COR_AZUL,    True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=COR_FUNDO)

        self.servicos = ServicosSCG()
        self.periodo_atual = None
        self.modo_manual   = False

        self._build_ui()
        self._carregar_periodos()

    def _build_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="💼  Consolidação SCG", font=("Roboto", 22, "bold"), text_color=COR_TEXTO).pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(header, text="SCG = RPV + RET + RP", font=("Roboto", 11), text_color=COR_MUTED).pack(side="left")

        # BARRA DE PERÍODO
        bar = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=52)
        bar.pack(fill="x", pady=(2, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="Período:", font=("Roboto", 12), text_color=COR_MUTED).pack(side="left", padx=(20, 6), pady=14)
        self.combo_periodo = ctk.CTkComboBox(bar, width=180, font=("Roboto", 12), command=self._ao_mudar_periodo)
        self.combo_periodo.pack(side="left", pady=14)

        ctk.CTkButton(bar, text="➕ Novo", width=80, height=30, fg_color=COR_AZUL, font=("Roboto", 11, "bold"), command=self._criar_periodo).pack(side="left", padx=8, pady=14)
        ctk.CTkButton(bar, text="🗑 Excluir", width=80, height=30, fg_color=COR_VERMELHO, font=("Roboto", 11, "bold"), command=self._excluir_periodo).pack(side="left", padx=(0, 20), pady=14)

        # TOGGLE MODO
        frame_toggle = ctk.CTkFrame(self, fg_color="transparent")
        frame_toggle.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(frame_toggle, text="Fonte dos valores:", font=("Roboto", 12), text_color=COR_MUTED).pack(side="left")
        self.btn_auto = ctk.CTkButton(frame_toggle, text="🔄 Automático (Banco de Dados)", width=230, height=32, font=("Roboto", 12, "bold"), fg_color=COR_VERDE, command=self._ativar_modo_auto)
        self.btn_auto.pack(side="left", padx=(10, 6))

        self.btn_manual = ctk.CTkButton(frame_toggle, text="✏️ Manual", width=110, height=32, font=("Roboto", 12, "bold"), fg_color=COR_INPUT, command=self._ativar_modo_manual)
        self.btn_manual.pack(side="left")

        # CAIXA RPV
        rpv_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=12)
        rpv_card.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(rpv_card, text="🔢  RPV — Requisição de Pequeno Valor", font=("Roboto", 13, "bold"), text_color=COR_ROXO).pack(anchor="w", padx=20, pady=(12, 4))
        row_rpv = ctk.CTkFrame(rpv_card, fg_color="transparent")
        row_rpv.pack(fill="x", padx=20, pady=(0, 14))

        self.lbl_rpv_cgr = ctk.CTkLabel(row_rpv, text="CGR\nR$ 0,00", font=("Roboto", 13, "bold"), fg_color=COR_AZUL, corner_radius=8, width=160, height=52, text_color="white")
        self.lbl_rpv_cgr.pack(side="left")

        ctk.CTkLabel(row_rpv, text=" − ", font=("Roboto", 22, "bold"), text_color=COR_VERMELHO).pack(side="left", padx=8)

        self.lbl_rpv_cgf = ctk.CTkLabel(row_rpv, text="CGF\nR$ 0,00", font=("Roboto", 13, "bold"), fg_color=COR_VERDE, corner_radius=8, width=160, height=52, text_color="white")
        self.lbl_rpv_cgf.pack(side="left")

        ctk.CTkLabel(row_rpv, text=" = ", font=("Roboto", 22, "bold"), text_color=COR_AMARELO).pack(side="left", padx=8)

        self.lbl_rpv_resultado = ctk.CTkLabel(row_rpv, text="RPV\nR$ 0,00", font=("Roboto", 14, "bold"), fg_color=COR_ROXO, corner_radius=8, width=180, height=52, text_color="white")
        self.lbl_rpv_resultado.pack(side="left")

        # PAINEL DE VALORES
        painel = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        painel.pack(fill="x", padx=24, pady=10)

        ctk.CTkLabel(painel, text="Valores por módulo", font=("Roboto", 13, "bold"), text_color=COR_MUTED).pack(anchor="w", padx=20, pady=(14, 8))

        self.linhas: dict[str, LinhaValor] = {}
        for key, icone, nome, cor, edit in self.CAMPOS:
            linha = LinhaValor(painel, icone, nome, key, cor, edit)
            linha.pack(fill="x", padx=20, pady=5)
            self.linhas[key] = linha

        ctk.CTkFrame(painel, height=1, fg_color=COR_INPUT).pack(fill="x", padx=20, pady=(10, 0))
        self.btn_salvar_manual = ctk.CTkButton(painel, text="💾 Salvar valores manuais no banco", font=("Roboto", 12, "bold"), height=36, fg_color=COR_AMARELO, text_color="black", command=self._salvar_manual)
        ctk.CTkFrame(painel, height=8, fg_color="transparent").pack()

        # RESULTADO SCG
        res = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        res.pack(fill="x", padx=24, pady=(0, 14))
        row_res = ctk.CTkFrame(res, fg_color="transparent")
        row_res.pack(fill="x", padx=20, pady=16)

        self.btn_calcular = ctk.CTkButton(row_res, text="⚡  CALCULAR SCG", font=("Roboto", 15, "bold"), height=50, width=220, fg_color=COR_VERMELHO, command=self._calcular_scg)
        self.btn_calcular.pack(side="left")

        self.btn_excel_final = ctk.CTkButton(
            row_res,
            text="➕ Excel Final (Módulo 9)",
            font=("Roboto", 13, "bold"),
            height=50,
            width=230,
            fg_color="#6c3483",
            hover_color="#884ea0",
            command=self._adicionar_excel_final,
        )
        self.btn_excel_final.pack(side="left", padx=(10, 0))

        self.btn_remover_excel_final = ctk.CTkButton(
            row_res,
            text="➖ Retirar Excel Final",
            font=("Roboto", 12, "bold"),
            height=50,
            width=200,
            fg_color=COR_INPUT,
            hover_color=COR_VERMELHO,
            command=self._remover_excel_final,
        )
        self.btn_remover_excel_final.pack(side="left", padx=(10, 0))

        self.lbl_scg = ctk.CTkLabel(row_res, text="SCG =  R$ 0,00", font=("Roboto", 26, "bold"), text_color=COR_AMARELO)
        self.lbl_scg.pack(side="left", padx=30)

        # HISTÓRICO
        hist_frame = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        hist_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        ctk.CTkLabel(hist_frame, text="📅  Histórico de períodos", font=("Roboto", 13, "bold"), text_color=COR_MUTED).pack(anchor="w", padx=20, pady=(14, 6))

        self.hist_box = ctk.CTkTextbox(hist_frame, font=("Consolas", 11), fg_color=COR_FUNDO, text_color=COR_MUTED, height=120)
        self.hist_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ── EVENTOS ──────────────────────────────────────────
    def _ativar_modo_auto(self):
        self.modo_manual = False
        self.btn_auto.configure(fg_color=COR_VERDE)
        self.btn_manual.configure(fg_color=COR_INPUT)
        self.btn_salvar_manual.pack_forget()
        for linha in self.linhas.values(): linha.mostrar_modo_auto()
        if self.periodo_atual: self._ao_mudar_periodo(self.periodo_atual)

    def _ativar_modo_manual(self):
        self.modo_manual = True
        self.btn_manual.configure(fg_color=COR_AMARELO, text_color="black")
        self.btn_auto.configure(fg_color=COR_INPUT)
        for linha in self.linhas.values(): linha.mostrar_modo_manual()
        self.btn_salvar_manual.pack(fill="x", padx=20, pady=(6, 12))

    def _carregar_periodos(self):
        periodos = self.servicos.obter_periodos()
        nomes = [p['periodo'] for p in periodos]
        self.combo_periodo.configure(values=nomes if nomes else [""])
        
        if nomes:
            self.combo_periodo.set(nomes[0])
            self._ao_mudar_periodo(nomes[0])
        self._atualizar_historico()

    def _criar_periodo(self):
        nome = simpledialog.askstring("Novo Período", "Nome do período (ex: Dez/2025):")
        if nome and nome.strip():
            self.servicos.criar_periodo(nome)
            self._carregar_periodos()
            self.combo_periodo.set(nome.strip())
            self._ao_mudar_periodo(nome.strip())

    def _excluir_periodo(self):
        if not self.periodo_atual: return
        if messagebox.askyesno("Confirmar", f"Excluir '{self.periodo_atual}'?\nValores serão perdidos."):
            self.servicos.apagar_periodo(self.periodo_atual)
            self._carregar_periodos()

    def _ao_mudar_periodo(self, periodo: str):
        self.periodo_atual = periodo
        dados = self.servicos.buscar_dados_periodo(periodo)
        if not dados: return

        for key, linha in self.linhas.items():
            v = dados[key]
            origem = "Calc" if key == "rpv" else "BD"
            linha.set_valor(v, origem)
            linha.set_entry_value(v) 

        self.lbl_scg.configure(text=f"SCG =  {ServicosSCG.formatar_brl(dados['scg'])}")
        self.lbl_rpv_cgr.configure(text=f"CGR\n{ServicosSCG.formatar_brl(dados['cgr'])}")
        self.lbl_rpv_cgf.configure(text=f"CGF\n{ServicosSCG.formatar_brl(dados['cgf'])}")
        self.lbl_rpv_resultado.configure(text=f"RPV\n{ServicosSCG.formatar_brl(dados['rpv'])}")

    def _salvar_manual(self):
        if not self.periodo_atual: return

        cgr = self.linhas["cgr"].get_valor_entry()
        cgf = self.linhas["cgf"].get_valor_entry()
        ret = self.linhas["ret"].get_valor_entry()
        rp  = self.linhas["rp"].get_valor_entry()

        rpv = self.servicos.salvar_valores_manuais(self.periodo_atual, cgr, cgf, ret, rp)

        self.linhas["rpv"].set_valor(rpv, "Calc")
        self.linhas["rpv"].set_entry_value(rpv)

        messagebox.showinfo("Salvo ✅", f"Valores salvos para '{self.periodo_atual}'.\nRPV calculado = {ServicosSCG.formatar_brl(rpv)}")

    def _calcular_scg(self):
        if not self.periodo_atual: return

        if self.modo_manual:
            self._salvar_manual()

        dados = self.servicos.calcular_scg_oficial(self.periodo_atual)
        
        self._ao_mudar_periodo(self.periodo_atual)
        self._atualizar_historico()

        detalhe = (
            f"Período : {self.periodo_atual}\n"
            f"{'─'*38}\n"
            f"  CGR          = {ServicosSCG.formatar_brl(dados['cgr'])}\n"
            f"  CGF          = {ServicosSCG.formatar_brl(dados['cgf'])}\n"
            f"  RPV = CGR−CGF= {ServicosSCG.formatar_brl(dados['rpv'])}\n"
            f"  RET          = {ServicosSCG.formatar_brl(dados['ret'])}\n"
            f"  RP           = {ServicosSCG.formatar_brl(dados['rp'])}\n"
            f"{'─'*38}\n"
            f"  SCG = RPV+RET+RP\n"
            f"  SCG          = {ServicosSCG.formatar_brl(dados['scg'])}"
        )
        messagebox.showinfo("SCG Calculado ✅", detalhe)

    def _atualizar_historico(self):
        self.hist_box.configure(state="normal") 
        self.hist_box.delete("1.0", "end") 
        
        texto = self.servicos.gerar_texto_historico()
        self.hist_box.insert("end", texto)
            
        self.hist_box.configure(state="disabled")

    def _adicionar_excel_final(self):
        if not self.periodo_atual:
            messagebox.showwarning("Aviso", "Selecione um período antes de gerar o Excel final.")
            return

        self.servicos.calcular_scg_oficial(self.periodo_atual)
        destino = escolher_destino_excel_final(periodo=self.periodo_atual, parent=self)
        if not destino:
            return
        arquivo = ExcelConsolidado.exportar(periodo=self.periodo_atual, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅", f"Arquivo criado com sucesso:\n{arquivo}")

    def _remover_excel_final(self):
        removido, mensagem = remover_excel_final_ativo(parent=self)
        if removido:
            messagebox.showinfo("Excel Final", mensagem)
        else:
            messagebox.showwarning("Excel Final", mensagem)