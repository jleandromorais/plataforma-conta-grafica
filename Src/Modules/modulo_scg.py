import customtkinter as ctk
from tkinter import messagebox, simpledialog
# Importa a tua classe de banco de dados (que deve estar noutro ficheiro chamado database.py)
from database import DatabasePMPV

# Configura o visual da janela para o modo escuro e tema azul
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ── Cores ────────────────────────────────────────────────────────────────────
# Guardar as cores em variáveis é uma excelente prática! 
# Se um dia quiseres mudar o azul para verde, só precisas de alterar aqui.
COR_CARD     = "#1e293b" # Cor de fundo dos "cartões" (painéis)
COR_FUNDO    = "#0f172a" # Cor do fundo geral da aplicação
COR_INPUT    = "#334155" # Cor das caixas de texto
COR_VERDE    = "#10b981"
COR_AZUL     = "#3b82f6"
COR_VERMELHO = "#ef4444"
COR_AMARELO  = "#f59e0b"
COR_ROXO     = "#8b5cf6"
COR_TEXTO    = "#f8fafc"
COR_MUTED    = "#94a3b8" # Cor de texto "desbotado" (para elementos secundários)


# ── Componente: linha de valor ────────────────────────────────────────────────
class LinhaValor(ctk.CTkFrame):
    """
    Esta classe é um componente personalizado. Ela herda de CTkFrame (um quadro).
    Cada linha representa um valor financeiro (ex: CGR) e contém tudo o que ele precisa:
    Ícone, Nome, Etiqueta de Origem (BD ou Manual), Valor em texto ou Caixa de Digitação.
    """
    def __init__(self, parent, icone: str, nome: str, key: str,
                 cor_icone: str = COR_AZUL, editavel: bool = True):
        # Inicializa o quadro transparente
        super().__init__(parent, fg_color="transparent")
        self.key      = key         # Chave de identificação (ex: "cgr")
        self.editavel = editavel    # Define se o utilizador pode alterar este valor

        # 1. Ícone da esquerda
        ctk.CTkLabel(self, text=icone, font=("Segoe UI Emoji", 18),
                     width=36, text_color=cor_icone).pack(side="left", padx=(0, 8))

        # 2. Nome da métrica (ex: "CGR (Auditoria XML)")
        ctk.CTkLabel(self, text=nome, font=("Roboto", 13),
                     width=200, anchor="w", text_color=COR_TEXTO).pack(side="left")

        # 3. Badge (Etiqueta pequena que diz se vem do Banco ou se foi digitado Manualmente)
        self.badge = ctk.CTkLabel(self, text="BD", font=("Roboto", 10, "bold"),
                                  width=52, height=22, corner_radius=11,
                                  fg_color=COR_VERDE, text_color="white")
        self.badge.pack(side="left", padx=8)

        # 4. Valor (Modo Leitura / Automático)
        self.lbl_valor = ctk.CTkLabel(self, text="R$ 0,00",
                                      font=("Roboto", 15, "bold"),
                                      width=190, height=36, corner_radius=8,
                                      fg_color=COR_INPUT, text_color=COR_TEXTO,
                                      anchor="e") # anchor="e" alinha o texto à direita (East)
        self.lbl_valor.pack(side="left", padx=8)

        # 5. Entry (Caixa de texto para o Modo Manual)
        self.entry = ctk.CTkEntry(self, placeholder_text="0,00",
                                  font=("Roboto", 14), width=190, height=36)
        # Nota: O 'entry' NÃO leva .pack() aqui porque, por defeito, a aplicação
        # começa no modo automático. Ele só aparece se clicarmos em "Manual".

    # ── helpers (Funções auxiliares da Linha) ────────────────────────────────
    def set_valor(self, valor: float, origem: str = "BD"):
        """Atualiza o texto visível e muda a cor/texto da etiqueta (badge)."""
        self.lbl_valor.configure(text=_fmt(valor)) # Formata para R$
        
        # Muda a indicação visual consoante de onde vem o dado
        if origem == "BD":
            self.badge.configure(text="📥 BD", fg_color=COR_VERDE)
        elif origem == "Manual":
            self.badge.configure(text="✏️ Manual", fg_color=COR_AMARELO)
        elif origem == "Calc":
            self.badge.configure(text="🔢 Calc", fg_color=COR_ROXO)

    def get_valor_entry(self) -> float:
        """
        Esta é uma função muito importante! Ela pega no que o utilizador digitou
        e converte num número decimal (float) que o Python consegue calcular.
        Como no Brasil se usa ponto para milhares e vírgula para casas decimais,
        é preciso tratar a string antes de a converter.
        """
        txt = self.entry.get().strip() # Pega o texto e remove espaços nas pontas
        if not txt:
            return 0.0

        last_dot   = txt.rfind(".")
        last_comma = txt.rfind(",")

        # Descobre qual é o formato digitado analisando a posição do ponto e vírgula
        if last_comma > last_dot:
            # Padrão BR: 1.000,50 -> Remove o ponto e troca a vírgula por ponto (1000.50)
            txt = txt.replace(".", "").replace(",", ".")
        elif last_dot > last_comma and last_comma >= 0:
            # Padrão Americano com milhares em vírgula: 1,000.50 -> Remove a vírgula
            txt = txt.replace(",", "")
        else:
            # Apenas pontos digitados (ex: 1.000)
            if last_dot >= 0:
                after = txt[last_dot + 1:]
                # Se o que vem depois do ponto tem 3 dígitos, era um ponto de milhar
                if len(after) == 3 and after.isdigit():
                    txt = txt.replace(".", "")

        # Verifica se o número é negativo
        negativo = txt.startswith("-")
        # Deixa passar apenas números e o ponto final
        txt = "".join(c for c in txt if c.isdigit() or c == ".")
        if negativo:
            txt = "-" + txt
            
        try:
            return float(txt) # Tenta transformar o texto num número matemático
        except ValueError:
            return 0.0 # Se der erro (ex: letras pelo meio), assume 0

    def set_entry_value(self, valor: float):
        """Põe um valor numérico dentro da caixa de digitação (Entry), formatado."""
        self.entry.delete(0, "end") # Limpa a caixa primeiro
        # Formata o número (ex: 1000.5 -> 1.000,50)
        txt = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.entry.insert(0, txt) # Insere o texto

    def mostrar_modo_auto(self):
        """Esconde a caixa de texto e mostra apenas a etiqueta (label) de leitura."""
        self.entry.pack_forget() # Esconde
        self.lbl_valor.pack(side="left", padx=8) # Mostra

    def mostrar_modo_manual(self):
        """Esconde a etiqueta de leitura e mostra a caixa de texto para edição."""
        if self.editavel: # Só deixa editar se o campo permitir (O RPV não permite, é calculado)
            self.lbl_valor.pack_forget()
            self.entry.pack(side="left", padx=8)


# ── Utilitários globais ──────────────────────────────────────────────────────
def _fmt(valor) -> str:
    """Recebe um número e devolve uma string bonita em Reais: R$ 1.500,00"""
    return f"R$ {(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ── Módulo SCG Principal ──────────────────────────────────────────────────────
class ModuloSCG(ctk.CTkToplevel):
    """
    Esta é a janela que se abre. CtkToplevel significa que é uma janela
    que aparece 'por cima' de uma janela base.
    """

    # Uma lista com as configurações de cada linha que vamos ter no ecrã.
    # É mais fácil gerir assim do que programar uma a uma.
    CAMPOS = [
        # (Chave,  ícone, Nome visível,              Cor do ícone, Permite editar?)
        ("cgr", "📄", "CGR  (Auditoria XML)",    COR_AZUL,    True),
        ("cgf", "📋", "CGF  (Volume Faturado)",  COR_VERDE,   True),
        ("rpv", "🔢", "RPV  = CGR − CGF",        COR_ROXO,    False), # RPV é calculado!
        ("ret", "⚡", "RET  (Encargos)",          COR_AMARELO, True),
        ("rp",  "🔄", "RP   (Conciliação)",       COR_AZUL,    True),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("💼 SCG — Consolidação da Conta Gráfica")
        self.geometry("860x720") # Tamanho inicial da janela
        self.configure(fg_color=COR_FUNDO)
        self.resizable(True, True) # Permite redimensionar a janela

        # Liga-se à base de dados
        self.db            = DatabasePMPV()
        self.periodo_atual = None
        self.modo_manual   = False   # False significa que arranca em modo Automático

        # Executa as funções de construção da janela
        self._build_ui()
        self._carregar_periodos()

    # ── UI (User Interface / Construção Visual) ──────────────────────────────
    def _build_ui(self):
        """
        Esta função é o 'construtor de legos'. Ela empacota os quadros (Frames) 
        uns dentro dos outros para formar o desenho da aplicação.
        """
        
        # ── HEADER (Cabeçalho)
        header = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=64)
        header.pack(fill="x") # fill="x" faz esticar horizontalmente
        header.pack_propagate(False) # Impede que o quadro encolha para o tamanho do conteúdo

        # Título principal
        ctk.CTkLabel(header, text="💼  Consolidação SCG",
                     font=("Roboto", 22, "bold"),
                     text_color=COR_TEXTO).pack(side="left", padx=24, pady=16)

        # Fórmula explicativa ao lado do título
        ctk.CTkLabel(header,
                     text="Sistema de Conta Gráfica  —  SCG = RPV × (CGR + CGF) + RET + RP",
                     font=("Roboto", 11), text_color=COR_MUTED).pack(side="left")

        # ── BARRA DE PERÍODO (Para escolher o mês/ano)
        bar = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=52)
        bar.pack(fill="x", pady=(2, 0))
        bar.pack_propagate(False)

        ctk.CTkLabel(bar, text="Período:", font=("Roboto", 12),
                     text_color=COR_MUTED).pack(side="left", padx=(20, 6), pady=14)

        # Dropdown (ComboBox) para selecionar o período
        self.combo_periodo = ctk.CTkComboBox(bar, width=180, font=("Roboto", 12),
                                             command=self._ao_mudar_periodo)
        self.combo_periodo.pack(side="left", pady=14)

        # Botão para adicionar novo período
        ctk.CTkButton(bar, text="➕ Novo", width=80, height=30,
                      fg_color=COR_AZUL, font=("Roboto", 11, "bold"),
                      command=self._criar_periodo).pack(side="left", padx=8, pady=14)

        # Botão para apagar período
        ctk.CTkButton(bar, text="🗑 Excluir", width=80, height=30,
                      fg_color=COR_VERMELHO, font=("Roboto", 11, "bold"),
                      command=self._excluir_periodo).pack(side="left", padx=(0, 20), pady=14)

        # ── TOGGLE MODO (Alternar entre Auto e Manual)
        frame_toggle = ctk.CTkFrame(self, fg_color="transparent")
        frame_toggle.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(frame_toggle, text="Fonte dos valores:",
                     font=("Roboto", 12), text_color=COR_MUTED).pack(side="left")

        self.btn_auto = ctk.CTkButton(
            frame_toggle, text="🔄 Automático (Banco de Dados)",
            width=230, height=32, font=("Roboto", 12, "bold"),
            fg_color=COR_VERDE, hover_color="#059669",
            command=self._ativar_modo_auto) # Chama a função para ficar auto
        self.btn_auto.pack(side="left", padx=(10, 6))

        self.btn_manual = ctk.CTkButton(
            frame_toggle, text="✏️ Manual",
            width=110, height=32, font=("Roboto", 12, "bold"),
            fg_color=COR_INPUT, hover_color=COR_AMARELO,
            command=self._ativar_modo_manual) # Chama a função para ficar manual
        self.btn_manual.pack(side="left")

        # ── CAIXA RPV (Destaque visual do cálculo intermédio)
        rpv_card = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=12)
        rpv_card.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(rpv_card,
                     text="🔢  RPV — Requisição de Pequeno Valor",
                     font=("Roboto", 13, "bold"), text_color=COR_ROXO
                     ).pack(anchor="w", padx=20, pady=(12, 4))

        row_rpv = ctk.CTkFrame(rpv_card, fg_color="transparent")
        row_rpv.pack(fill="x", padx=20, pady=(0, 14))

        # Quadradinho visual para mostrar o CGR
        self.lbl_rpv_cgr = ctk.CTkLabel(row_rpv, text="CGR\nR$ 0,00",
                                         font=("Roboto", 13, "bold"),
                                         fg_color=COR_AZUL, corner_radius=8,
                                         width=160, height=52, text_color="white")
        self.lbl_rpv_cgr.pack(side="left")

        ctk.CTkLabel(row_rpv, text=" − ", font=("Roboto", 22, "bold"),
                     text_color=COR_VERMELHO).pack(side="left", padx=8)

        # Quadradinho visual para mostrar o CGF
        self.lbl_rpv_cgf = ctk.CTkLabel(row_rpv, text="CGF\nR$ 0,00",
                                         font=("Roboto", 13, "bold"),
                                         fg_color=COR_VERDE, corner_radius=8,
                                         width=160, height=52, text_color="white")
        self.lbl_rpv_cgf.pack(side="left")

        ctk.CTkLabel(row_rpv, text=" = ", font=("Roboto", 22, "bold"),
                     text_color=COR_AMARELO).pack(side="left", padx=8)

        # Quadradinho visual do RPV calculado
        self.lbl_rpv_resultado = ctk.CTkLabel(
            row_rpv, text="RPV\nR$ 0,00",
            font=("Roboto", 14, "bold"),
            fg_color=COR_ROXO, corner_radius=8,
            width=180, height=52, text_color="white")
        self.lbl_rpv_resultado.pack(side="left")

        # ── PAINEL DE VALORES (Gera as linhas dinamicamente)
        painel = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        painel.pack(fill="x", padx=24, pady=10)

        ctk.CTkLabel(painel, text="Valores por módulo",
                     font=("Roboto", 13, "bold"),
                     text_color=COR_MUTED).pack(anchor="w", padx=20, pady=(14, 8))

        # Dicionário que guarda as referências de cada LinhaValor criada
        self.linhas: dict[str, LinhaValor] = {}
        
        # Um 'For' que lê a configuração lá de cima e cria os 5 campos no ecrã!
        for key, icone, nome, cor, edit in self.CAMPOS:
            linha = LinhaValor(painel, icone, nome, key, cor, edit)
            linha.pack(fill="x", padx=20, pady=5)
            self.linhas[key] = linha # Guarda na memória para acedermos depois

        # Separador visual (uma linha fina)
        ctk.CTkFrame(painel, height=1, fg_color=COR_INPUT).pack(
            fill="x", padx=20, pady=(10, 0))

        # Botão salvar manual (Criado, mas escondido. Aparece só no modo manual)
        self.btn_salvar_manual = ctk.CTkButton(
            painel, text="💾 Salvar valores manuais no banco",
            font=("Roboto", 12, "bold"), height=36,
            fg_color=COR_AMARELO, hover_color="#d97706",
            command=self._salvar_manual)

        ctk.CTkFrame(painel, height=8, fg_color="transparent").pack()

        # ── RESULTADO SCG (Botão enorme de Calcular)
        res = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        res.pack(fill="x", padx=24, pady=(0, 14))

        row_res = ctk.CTkFrame(res, fg_color="transparent")
        row_res.pack(fill="x", padx=20, pady=16)

        self.btn_calcular = ctk.CTkButton(
            row_res, text="⚡  CALCULAR SCG",
            font=("Roboto", 15, "bold"), height=50, width=220,
            fg_color=COR_VERMELHO, hover_color="#dc2626",
            command=self._calcular_scg)
        self.btn_calcular.pack(side="left")

        # Texto grande com o resultado final do SCG
        self.lbl_scg = ctk.CTkLabel(
            row_res, text="SCG =  R$ 0,00",
            font=("Roboto", 26, "bold"),
            text_color=COR_AMARELO)
        self.lbl_scg.pack(side="left", padx=30)

        # ── HISTÓRICO (Caixa de texto no fundo)
        hist_frame = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        hist_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))

        ctk.CTkLabel(hist_frame, text="📅  Histórico de períodos",
                     font=("Roboto", 13, "bold"),
                     text_color=COR_MUTED).pack(anchor="w", padx=20, pady=(14, 6))

        self.hist_box = ctk.CTkTextbox(hist_frame, font=("Consolas", 11),
                                       fg_color=COR_FUNDO, text_color=COR_MUTED,
                                       height=120)
        self.hist_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ── EVENTOS: MODO AUTO / MANUAL ──────────────────────────────────────────
    def _ativar_modo_auto(self):
        """Muda a interface para o modo Automático (Desativa as caixas de texto)."""
        self.modo_manual = False
        # Atualiza o visual dos botões
        self.btn_auto.configure(fg_color=COR_VERDE)
        self.btn_manual.configure(fg_color=COR_INPUT)
        self.btn_salvar_manual.pack_forget() # Esconde o botão de guardar
        
        # Manda todas as linhas ativarem o seu próprio modo auto
        for linha in self.linhas.values():
            linha.mostrar_modo_auto()
            
        # Refresca os dados a partir do banco de dados
        if self.periodo_atual:
            self._ao_mudar_periodo(self.periodo_atual)

    def _ativar_modo_manual(self):
        """Muda a interface para edição manual."""
        self.modo_manual = True
        self.btn_manual.configure(fg_color=COR_AMARELO)
        self.btn_auto.configure(fg_color=COR_INPUT)
        
        # Manda todas as linhas (ex: CGR) virarem caixas de input
        for linha in self.linhas.values():
            linha.mostrar_modo_manual()
            
        # Mostra o botão de guardar na interface
        self.btn_salvar_manual.pack(fill="x", padx=20, pady=(6, 12))

    # ── PERÍODO (Lógica do Banco de Dados / ComboBox) ────────────────────────
    def _carregar_periodos(self):
        """Pede os períodos à DB e coloca-os no ComboBox dropdown."""
        periodos = self.db.listar_periodos()
        nomes = [p['periodo'] for p in periodos] # Extrai apenas o nome (Ex: Dez/2025)
        self.combo_periodo.configure(values=nomes if nomes else [""])
        
        if nomes:
            self.combo_periodo.set(nomes[0]) # Seleciona o primeiro da lista
            self._ao_mudar_periodo(nomes[0])
        self._atualizar_historico(periodos)

    def _criar_periodo(self):
        """Abre uma caixinha (popup) a pedir para escrever um novo período."""
        nome = simpledialog.askstring(
            "Novo Período", "Nome do período (ex: Dez/2025 ou Q1/2026):")
        if nome and nome.strip():
            self.db.criar_periodo_consolidacao(nome.strip())
            self._carregar_periodos() # Recarrega a interface
            self.combo_periodo.set(nome.strip())
            self._ao_mudar_periodo(nome.strip())

    def _excluir_periodo(self):
        """Apaga o período atualmente selecionado da base de dados."""
        if not self.periodo_atual:
            return
        # Pede confirmação primeiro (boa prática!)
        if messagebox.askyesno("Confirmar",
                                f"Excluir o período '{self.periodo_atual}'?\n"
                                "Todos os valores serão perdidos."):
            self.db.cursor.execute(
                "DELETE FROM consolidacao WHERE periodo = ?",
                (self.periodo_atual,))
            self.db.conn.commit()
            self._carregar_periodos()

    def _ao_mudar_periodo(self, periodo: str):
        """
        Sempre que mudamos o mês selecionado, esta função atualiza TUDO no ecrã
        para mostrar os valores do mês selecionado.
        """
        self.periodo_atual = periodo
        dados = self.db.buscar_consolidacao(periodo)
        if not dados:
            return

        # Busca dados do DB ou mete zero se estiver vazio
        cgr = dados.get('cgr') or 0.0
        cgf = dados.get('cgf') or 0.0
        rpv = dados.get('rpv') or (cgr - cgf)
        ret = dados.get('ret') or 0.0
        rp  = dados.get('rp')  or 0.0
        scg = dados.get('scg') or 0.0

        valores = {"cgr": cgr, "cgf": cgf, "rpv": rpv, "ret": ret, "rp": rp}

        # Atualiza os valores visuais de cada linha correspondente
        for key, linha in self.linhas.items():
            v = valores[key]
            # O RPV aparece sempre como calculado
            origem = "Calc" if key == "rpv" else "BD"
            linha.set_valor(v, origem)
            linha.set_entry_value(v) # Prepara também a caixa manual se ela for ativada

        # Atualiza o texto gigantesco do SCG
        self.lbl_scg.configure(text=f"SCG =  {_fmt(scg)}")
        
        # Atualiza a área de destaque do RPV (a caixa roxa na interface)
        self.lbl_rpv_cgr.configure(text=f"CGR\n{_fmt(cgr)}")
        self.lbl_rpv_cgf.configure(text=f"CGF\n{_fmt(cgf)}")
        self.lbl_rpv_resultado.configure(text=f"RPV\n{_fmt(rpv)}")

    # ── LÓGICA DE DADOS (Salvar e Calcular) ──────────────────────────────────
    def _salvar_manual(self):
        """Pega no que foi escrito nas caixinhas, valida e guarda na base de dados."""
        if not self.periodo_atual:
            messagebox.showwarning("Aviso", "Selecione um período primeiro.")
            return

        # Recolhe os valores usando a função 'get_valor_entry' que converte strings em float
        cgr = self.linhas["cgr"].get_valor_entry()
        cgf = self.linhas["cgf"].get_valor_entry()
        ret = self.linhas["ret"].get_valor_entry()
        rp  = self.linhas["rp"].get_valor_entry()

        # Envia cada valor individualmente para o banco de dados
        self.db.atualizar_cgr(self.periodo_atual, cgr)
        self.db.atualizar_cgf(self.periodo_atual, cgf)
        self.db.atualizar_ret(self.periodo_atual, ret)
        self.db.atualizar_rp(self.periodo_atual, rp)
        
        # Pede ao DB para recalcular o RPV baseado nestes novos valores
        rpv = self.db.calcular_e_salvar_rpv(self.periodo_atual)

        # Atualiza o label do RPV no ecrã em tempo real
        self.linhas["rpv"].set_valor(rpv, "Calc")
        self.linhas["rpv"].set_entry_value(rpv)

        messagebox.showinfo("Salvo ✅",
                            f"Valores manuais salvos para '{self.periodo_atual}'.\n"
                            f"RPV calculado = {_fmt(rpv)}")

    def _calcular_scg(self):
        """Calcula o resultado final do SCG, quer o utilizador esteja em Auto ou Manual."""
        if not self.periodo_atual:
            messagebox.showwarning("Aviso", "Selecione um período!")
            return

        # Se o utilizador estiver em modo manual e clicar "Calcular",
        # guardamos a informação automaticamente para não a perder.
        if self.modo_manual:
            self._salvar_manual()

        # Faz o cálculo oficial na base de dados
        self.db.calcular_e_salvar_rpv(self.periodo_atual)
        scg = self.db.calcular_scg(self.periodo_atual)
        
        # Recarrega a janela para mostrar os resultados frescos
        self._ao_mudar_periodo(self.periodo_atual)
        self._atualizar_historico(self.db.listar_periodos())

        # Exibe um relatório detalhado em Pop-Up (messagebox)
        dados = self.db.buscar_consolidacao(self.periodo_atual)
        cgr = dados.get('cgr') or 0.0
        cgf = dados.get('cgf') or 0.0
        rpv = dados.get('rpv') or 0.0
        ret = dados.get('ret') or 0.0
        rp  = dados.get('rp')  or 0.0

        detalhe = (
            f"Período : {self.periodo_atual}\n"
            f"{'─'*38}\n"
            f"  CGR          = {_fmt(cgr)}\n"
            f"  CGF          = {_fmt(cgf)}\n"
            f"  RPV = CGR−CGF= {_fmt(rpv)}\n"
            f"  RET          = {_fmt(ret)}\n"
            f"  RP           = {_fmt(rp)}\n"
            f"{'─'*38}\n"
            f"  SCG = RPV×(CGR+CGF)+RET+RP\n"
            f"  SCG          = {_fmt(scg)}"
        )
        messagebox.showinfo("SCG Calculado ✅", detalhe)

    # ── HISTÓRICO ────────────────────────────────────────────────────────────
    def _atualizar_historico(self, periodos: list):
        """Popula a grande caixa de texto no fundo do ecrã com um histórico estilo tabela."""
        self.hist_box.configure(state="normal") # Permite edição para o código poder escrever
        self.hist_box.delete("1.0", "end") # Limpa tudo
        
        # Títulos das colunas bem alinhados
        cabecalho = f"{'Período':<18} {'SCG':>18}   {'Atualizado em':<22}\n"
        self.hist_box.insert("end", cabecalho)
        self.hist_box.insert("end", "─" * 62 + "\n")
        
        # Preenche com os dados da base de dados
        for p in periodos:
            scg_v = p.get('scg') or 0.0
            data  = (p.get('data_atualizacao') or '')[:16] # Corta os segundos da data
            linha = f"{p['periodo']:<18} {_fmt(scg_v):>18}   {data:<22}\n"
            self.hist_box.insert("end", linha)
            
        self.hist_box.configure(state="disabled") # Bloqueia, para o utilizador não apagar o texto

# ── Ponto de Entrada (Boot) ──────────────────────────────────────────────────
if __name__ == "__main__":
    root = ctk.CTk()  # Cria a janela principal invisível (base)
    root.withdraw()   # Esconde esta janela raiz porque estamos a usar CTkToplevel
    app = ModuloSCG(root) # Lança a NOSSA janela
    
    # Faz com que fechar a NOSSA janela encerre o programa inteiro
    root.protocol("WM_DELETE_WINDOW", root.destroy) 
    root.mainloop() # Mantém o programa a correr