import customtkinter as ctk
from tkinter import messagebox, simpledialog

# Importa a tua classe de banco de dados (que deve estar no ficheiro database.py)
from database import DatabasePMPV

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

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

# ── Utilitários globais ──────────────────────────────────────────────────────
def _fmt(valor) -> str:
    """Recebe um número e devolve uma string formatada em Reais ou Unidades."""
    return f"R$ {(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Componente: linha de valor ────────────────────────────────────────────────
class LinhaValor(ctk.CTkFrame):
    """Componente visual que representa uma linha de dados (Ícone, Nome, Valor)."""

    def __init__(self, parent, icone: str, nome: str, key: str, cor_icone: str = COR_AZUL, editavel: bool = True):
        super().__init__(parent, fg_color="transparent")
        self.key = key
        self.editavel = editavel

        # Ícone e Nome
        ctk.CTkLabel(self, text=icone, font=("Segoe UI Emoji", 18),
                     width=36, text_color=cor_icone).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self, text=nome, font=("Roboto", 13),
                     width=200, anchor="w", text_color=COR_TEXTO).pack(side="left")

        # Badge "BD" ou "Manual"
        self.badge = ctk.CTkLabel(self, text="BD", font=("Roboto", 10, "bold"),
                                  width=52, height=22, corner_radius=11,
                                  fg_color=COR_VERDE, text_color="white")
        self.badge.pack(side="left", padx=8)

        # Label de Valor (Leitura)
        self.lbl_valor = ctk.CTkLabel(self, text="0,00", font=("Roboto", 15, "bold"),
                                      width=190, height=36, corner_radius=8,
                                      fg_color=COR_INPUT, text_color=COR_TEXTO, anchor="e")
        self.lbl_valor.pack(side="left", padx=8)

        # Entry (Edição Manual)
        self.entry = ctk.CTkEntry(self, placeholder_text="0,00", font=("Roboto", 14), width=190, height=36)

    def set_valor(self, valor: float, origem: str = "BD"):
        """Atualiza o texto visível e muda a cor/texto da etiqueta (badge)."""
        # Se for um volume (VP ou VF), podemos tirar o R$, mas deixei o _fmt padrão por simplicidade
        self.lbl_valor.configure(text=_fmt(valor))

        if origem == "BD":
            self.badge.configure(text="📥 BD", fg_color=COR_VERDE)
        elif origem == "Manual":
            self.badge.configure(text="✏️ Manual", fg_color=COR_AMARELO)
        elif origem == "Calc":
            self.badge.configure(text="🔢 Calc", fg_color=COR_ROXO)

    def get_valor_entry(self) -> float:
        """Lê o que foi digitado e converte para número decimal (float)."""
        txt = self.entry.get().strip()
        if not txt:
            return 0.0

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

    def set_entry_value(self, valor: float):
        """Põe um valor numérico dentro da caixa de digitação (Entry), formatado."""
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


# ── Módulo SR (Saldo Remanescente) ───────────────────────────────────────────
class ModuloSR(ctk.CTkToplevel):
    """
    Janela dedicada ao cálculo do Saldo Remanescente.
    Fórmula principal: SR = (VP - VF) * PR
    """

    # Corrigido a sintaxe da lista. Sem parênteses extra e com vírgulas nos locais certos!
    CAMPOS = [
        # (Chave,  ícone, Nome visível,                Cor do ícone, Permite editar?)
        ("vp",    "📄", "VP  (Volume Prospecto)",      COR_AZUL,    True),
        ("vf",    "📋", "VF  (Volume Faturado)",       COR_VERDE,   True),
        ("diff",  "🔢", "Diff = VP − VF",              COR_ROXO,    False), # Calculado
        ("pr",    "⚡", "PR  (Preço Referência)",      COR_AMARELO, True),
        ("sr",    "🔄", "SR  (Saldo Remanescente)",    COR_AZUL,    False), # Calculado
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("📊 SR — Saldo Remanescente")
        self.geometry("860x760")
        self.configure(fg_color=COR_FUNDO)
        self.resizable(True, True)

        self.db = DatabasePMPV()
        self.periodo_atual = None
        self.modo_manual = False 

        self._build_ui()
        # self._carregar_periodos() # Descomenta quando a função do banco de dados estiver pronta!

    # ── UI Visual ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── HEADER
        header = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="📊  Cálculo do SR", font=("Roboto", 22, "bold"),
                     text_color=COR_TEXTO).pack(side="left", padx=24, pady=16)

        ctk.CTkLabel(header, text="Fórmula: SR = (VP - VF) × PR",
                     font=("Roboto", 12), text_color=COR_MUTED).pack(side="left", padx=10)

        # ── SELETOR DE PERÍODO E BOTÕES DE MODO (Auto/Manual)
        bar = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=52)
        bar.pack(fill="x", pady=(2, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="Período:", text_color=COR_MUTED).pack(side="left", padx=(20, 6), pady=14)
        
        # O ComboBox onde o utilizador escolhe o mês
        self.combo_periodo = ctk.CTkComboBox(bar, width=150, command=self._ao_mudar_periodo)
        self.combo_periodo.pack(side="left", pady=14)

        # Botões de Modo
        self.btn_auto = ctk.CTkButton(bar, text="🔄 BD", width=60, fg_color=COR_VERDE,
                                      command=self._ativar_modo_auto)
        self.btn_auto.pack(side="right", padx=10, pady=10)

        self.btn_manual = ctk.CTkButton(bar, text="✏️ Manual", width=80, fg_color=COR_INPUT,
                                        command=self._ativar_modo_manual)
        self.btn_manual.pack(side="right", pady=10)

        # ── CAIXA DE DESTAQUE (Mostra a conta da Diferença)
        destaque_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=12)
        destaque_card.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(destaque_card, text="🔢  Passo 1: Diferença de Volumes (VP - VF)",
                     font=("Roboto", 13, "bold"), text_color=COR_ROXO).pack(anchor="w", padx=20, pady=(12, 4))

        row_destaque = ctk.CTkFrame(destaque_card, fg_color="transparent")
        row_destaque.pack(fill="x", padx=20, pady=(0, 14))

        self.lbl_card_vp = ctk.CTkLabel(row_destaque, text="VP\n0,00", font=("Roboto", 13, "bold"),
                                        fg_color=COR_AZUL, corner_radius=8, width=160, height=52, text_color="white")
        self.lbl_card_vp.pack(side="left")

        ctk.CTkLabel(row_destaque, text=" − ", font=("Roboto", 22, "bold"), text_color=COR_VERMELHO).pack(side="left", padx=8)

        self.lbl_card_vf = ctk.CTkLabel(row_destaque, text="VF\n0,00", font=("Roboto", 13, "bold"),
                                        fg_color=COR_VERDE, corner_radius=8, width=160, height=52, text_color="white")
        self.lbl_card_vf.pack(side="left")

        ctk.CTkLabel(row_destaque, text=" = ", font=("Roboto", 22, "bold"), text_color=COR_AMARELO).pack(side="left", padx=8)

        self.lbl_card_diff = ctk.CTkLabel(row_destaque, text="Diferença\n0,00", font=("Roboto", 14, "bold"),
                                          fg_color=COR_ROXO, corner_radius=8, width=180, height=52, text_color="white")
        self.lbl_card_diff.pack(side="left")

        # ── PAINEL DE VALORES (Gera as linhas dinamicamente)
        painel = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        painel.pack(fill="x", padx=24, pady=10)

        self.linhas: dict[str, LinhaValor] = {}
        for key, icone, nome, cor, edit in self.CAMPOS:
            linha = LinhaValor(painel, icone, nome, key, cor, edit)
            linha.pack(fill="x", padx=20, pady=5)
            self.linhas[key] = linha

        self.btn_salvar_manual = ctk.CTkButton(painel, text="💾 Salvar valores", fg_color=COR_AMARELO,
                                               text_color="black", command=self._salvar_manual)

        # ── RESULTADO FINAL SR ────────────────────────────────────────────────
        res = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        res.pack(fill="x", padx=24, pady=(0, 14))

        row_res = ctk.CTkFrame(res, fg_color="transparent")
        row_res.pack(fill="x", padx=20, pady=16)

        self.btn_calcular = ctk.CTkButton(row_res, text="⚡  CALCULAR SR", font=("Roboto", 15, "bold"),
                                          height=50, width=220, fg_color=COR_VERMELHO, command=self._calcular_sr)
        self.btn_calcular.pack(side="left")

        self.lbl_sr_final = ctk.CTkLabel(row_res, text="SR =  R$ 0,00", font=("Roboto", 26, "bold"), text_color=COR_AMARELO)
        self.lbl_sr_final.pack(side="left", padx=30)

    # ── EVENTOS DA INTERFACE ─────────────────────────────────────────────────
    def _ativar_modo_auto(self):
        self.modo_manual = False
        self.btn_auto.configure(fg_color=COR_VERDE)
        self.btn_manual.configure(fg_color=COR_INPUT)
        self.btn_salvar_manual.pack_forget()
        for linha in self.linhas.values(): linha.mostrar_modo_auto()

    def _ativar_modo_manual(self):
        self.modo_manual = True
        self.btn_manual.configure(fg_color=COR_AMARELO, text_color="black")
        self.btn_auto.configure(fg_color=COR_INPUT)
        for linha in self.linhas.values(): linha.mostrar_modo_manual()
        self.btn_salvar_manual.pack(fill="x", padx=20, pady=(6, 12))

    # ── LÓGICA DE CÁLCULO E BANCO DE DADOS ───────────────────────────────────
    def _ao_mudar_periodo(self, periodo: str):
        """Simula a busca de dados no banco e atualiza o ecrã."""
        self.periodo_atual = periodo
        
        # AQUI DEVES CHAMAR O TEU BANCO DE DADOS
        # Exemplo: dados = self.db.buscar_dados_sr(periodo)
        
        # Valores simulados (Substitui pelas chamadas à DB reais)
        vp = 50000.0  # self.db.buscar_vp(periodo)
        vf = 45000.0  # self.db.buscar_vf(periodo)
        pr = 1.50     # O preço de referência
        
        # Cálculos matemáticos
        diff = vp - vf
        sr = diff * pr

        valores = {"vp": vp, "vf": vf, "diff": diff, "pr": pr, "sr": sr}

        # Atualiza todas as linhas de texto do painel
        for key, linha in self.linhas.items():
            origem = "Calc" if key in ["diff", "sr"] else "BD"
            linha.set_valor(valores[key], origem)
            linha.set_entry_value(valores[key])

        # Atualiza a caixa roxa de destaque
        self.lbl_card_vp.configure(text=f"VP\n{_fmt(vp)}")
        self.lbl_card_vf.configure(text=f"VF\n{_fmt(vf)}")
        self.lbl_card_diff.configure(text=f"Diferença\n{_fmt(diff)}")

        # Atualiza o letreiro grande do Resultado
        self.lbl_sr_final.configure(text=f"SR =  {_fmt(sr)}")

    def _salvar_manual(self):
        """Salva os valores que o utilizador digitou e recalcula."""
        vp = self.linhas["vp"].get_valor_entry()
        vf = self.linhas["vf"].get_valor_entry()
        pr = self.linhas["pr"].get_valor_entry()

        # AQUI DEVES GRAVAR NA TUA DB
        # Ex: self.db.atualizar_sr_manual(self.periodo_atual, vp, vf, pr)

        # Refaz o cálculo em tempo real
        diff = vp - vf
        sr = diff * pr

        # Mostra o resultado atualizado na linha visual
        self.linhas["diff"].set_valor(diff, "Calc")
        self.linhas["sr"].set_valor(sr, "Calc")
        
        # Atualiza a caixa roxa e letreiro
        self.lbl_card_vp.configure(text=f"VP\n{_fmt(vp)}")
        self.lbl_card_vf.configure(text=f"VF\n{_fmt(vf)}")
        self.lbl_card_diff.configure(text=f"Diferença\n{_fmt(diff)}")
        self.lbl_sr_final.configure(text=f"SR =  {_fmt(sr)}")

        messagebox.showinfo("Salvo ✅", "Valores manuais salvos com sucesso!")

    def _calcular_sr(self):
        """Botão grande de calcular. Executa a matemática e mostra resumo."""
        if self.modo_manual:
            self._salvar_manual()
            
        vp = self.linhas["vp"].get_valor_entry() if self.modo_manual else 50000.0 # Busca do DB
        vf = self.linhas["vf"].get_valor_entry() if self.modo_manual else 45000.0 # Busca do DB
        pr = self.linhas["pr"].get_valor_entry() if self.modo_manual else 1.50    # Busca do DB
        
        diff = vp - vf
        sr = diff * pr

        detalhe = (
            f"  VP (Volume Prospecto) = {_fmt(vp)}\n"
            f"  VF (Volume Faturado)  = {_fmt(vf)}\n"
            f"  Diferença (VP - VF)   = {_fmt(diff)}\n"
            f"  PR (Preço Referência) = {_fmt(pr)}\n"
            f"{'─'*38}\n"
            f"  Cálculo: Diferença × PR\n"
            f"  SR Final              = {_fmt(sr)}"
        )
        messagebox.showinfo("SR Calculado ✅", detalhe)

# ── Ponto de Entrada (Para Testar) ──────────────────────────────────────────
if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    app = ModuloSR(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()