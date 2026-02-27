import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog
from database import DatabasePMPV
from excel_handler import ExcelHandlerPMPV

# Configuração Visual
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class CalculadoraTrimestralPMPV(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("Sistema PMPV Master - Gestão Trimestral")
        self.geometry("1300x850")
        
        # Banco de Dados
        self.db = DatabasePMPV()
        
        self.empresas_padrao = ["PETROBRAS", "GALP", "PETRORECONCAVO", "BRAVA", "ENEVA", "ORIZON"]
        
        self.mapa_dias = {
            "Janeiro": 31, "Fevereiro": 28, "Março": 31, "Abril": 30,
            "Maio": 31, "Junho": 30, "Julho": 31, "Agosto": 31,
            "Setembro": 30, "Outubro": 31, "Novembro": 30, "Dezembro": 31
        }
        self.lista_meses = list(self.mapa_dias.keys())
        self.dias_config = {"Mês 1": 30, "Mês 2": 30, "Mês 3": 30}
        self.dados_meses  = {}
        self.scroll_frames = {}   # {tab_nome: CTkScrollableFrame}

        self._setup_ui()

    def _setup_ui(self):
        # HEADER
        head = ctk.CTkFrame(self, height=60, corner_radius=0)
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Calculadora PMPV Master", font=("Roboto", 24, "bold")).pack(side="left", padx=20, pady=10)

        # CONFIGURAÇÃO
        conf = ctk.CTkFrame(self, fg_color="transparent")
        conf.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(conf, text="📅 Trimestre começa em:", font=("Roboto", 14, "bold")).pack(side="left")
        self.combo_mes = ctk.CTkComboBox(conf, values=self.lista_meses, command=self._atualizar_trimestre)
        self.combo_mes.set("Novembro")
        self.combo_mes.pack(side="left", padx=10)
        
        self.chk_biss = ctk.CTkCheckBox(conf, text="Ano Bissexto", command=self._atualizar_trimestre)
        self.chk_biss.pack(side="left", padx=10)

        # ABAS
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        for i in range(1, 4):
            nome = f"Mês {i}"
            self.tabview.add(nome)
            self.dados_meses[nome] = self._criar_aba(self.tabview.tab(nome), nome)
        
        self._atualizar_trimestre()

        # RODAPÉ
        foot = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=15)
        foot.pack(fill="x", padx=20, pady=20)

        # Esquerda: Conta Gráfica
        left = ctk.CTkFrame(foot, fg_color="transparent")
        left.pack(side="left", padx=20, pady=20)
        ctk.CTkLabel(left, text="Conta Gráfica (R$):").pack(anchor="w")
        self.entry_cg = ctk.CTkEntry(left, justify="center")
        self.entry_cg.insert(0, "-0.0210")
        self.entry_cg.pack(pady=5)
        ctk.CTkButton(left, text="⚡ CALCULAR", command=self.calcular, fg_color="#27ae60", hover_color="#2ecc71").pack(pady=5)

        # Centro: Resultados
        center = ctk.CTkFrame(foot, fg_color="transparent")
        center.pack(side="left", expand=True)
        self.lbl_pmpv = ctk.CTkLabel(center, text="PMPV: R$ 0.0000", font=("Roboto", 20))
        self.lbl_pmpv.pack()
        self.lbl_final = ctk.CTkLabel(center, text="PREÇO FINAL: R$ 0.0000", font=("Roboto", 28, "bold"), text_color="#f1c40f")
        self.lbl_final.pack()
        vp_row = ctk.CTkFrame(center, fg_color="transparent")
        vp_row.pack(pady=(4, 0))
        self.lbl_vp = ctk.CTkLabel(vp_row, text="VP Total: — m³", font=("Roboto", 13), text_color="#3498db")
        self.lbl_vp.pack(side="left")
        self.btn_vp_detail = ctk.CTkButton(
            vp_row, text="▼ por mês", command=self._popup_vp,
            width=80, height=22, font=("Roboto", 11),
            fg_color="#1a5276", hover_color="#2e86c1",
        )
        self.btn_vp_detail.pack(side="left", padx=(8, 0))

        # Direita: Botões
        right = ctk.CTkFrame(foot, fg_color="transparent")
        right.pack(side="right", padx=20)
        ctk.CTkButton(right, text="📥 Importar Memória MC",  command=self._importar_memoria_calculo,   fg_color="#d35400", hover_color="#e67e22").pack(pady=5)
        ctk.CTkButton(right, text="💾 Salvar Sessão",       command=self.salvar,               fg_color="#8e44ad").pack(pady=5)
        ctk.CTkButton(right, text="📅 Salvar PMPV Mensal",  command=self._salvar_pmpv_mensal,  fg_color="#16a085").pack(pady=5)
        ctk.CTkButton(right, text="📊 Exportar Excel",      command=self.exportar,             fg_color="#2980b9").pack(pady=5)
        ctk.CTkButton(right, text="📄 Exportar Memória MC", command=self.exportar_memoria_mc,  fg_color="#1a5276", hover_color="#2e86c1").pack(pady=5)

    def _criar_aba(self, parent, tab_nome: str = ""):
        # Cabeçalho Tabela
        head = ctk.CTkFrame(parent, height=30, fg_color="#2c3e50")
        head.pack(fill="x", pady=5)
        cols = [("Empresa", 200), ("Molécula", 100), ("Transporte", 100), ("Logística", 100), ("Total", 100), ("Volume", 120), ("Ações", 80)]
        for txt, w in cols:
            ctk.CTkLabel(head, text=txt, width=w, font=("Roboto", 12, "bold")).pack(side="left", padx=2)

        # Scroll
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        if tab_nome:
            self.scroll_frames[tab_nome] = scroll

        linhas = []
        for emp in self.empresas_padrao:
            linhas.append(self._add_linha(scroll, emp, linhas))

        ctk.CTkButton(parent, text="➕ Adicionar", command=lambda: self._add_nova(scroll, linhas), fg_color="transparent", border_width=1).pack(pady=5)
        return linhas

    def _add_linha(self, parent, nome, lista):
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", pady=2)
        
        conf = {"width": 100, "height": 30}
        
        e_nom = ctk.CTkEntry(row, width=200, height=30); e_nom.insert(0, nome); e_nom.pack(side="left", padx=2)
        e_mol = ctk.CTkEntry(row, **conf); e_mol.pack(side="left", padx=2)
        e_tra = ctk.CTkEntry(row, **conf); e_tra.pack(side="left", padx=2)
        e_log = ctk.CTkEntry(row, **conf); e_log.pack(side="left", padx=2)
        
        l_tot = ctk.CTkLabel(row, text="0.0000", width=100, height=30, fg_color="#34495e", corner_radius=5)
        l_tot.pack(side="left", padx=2)
        
        e_vol = ctk.CTkEntry(row, width=120, height=30, text_color="#f39c12", font=("Roboto", 12, "bold"))
        e_vol.pack(side="left", padx=2)
        e_vol._entry.bind("<FocusOut>",  lambda _e, w=e_vol: self._sanitizar_vol(w))
        e_vol._entry.bind("<<Paste>>",   lambda _e, w=e_vol: self.after(10, lambda: self._sanitizar_vol(w)))

        ctk.CTkButton(row, text="📋", width=40, command=lambda: self._popup_copy(dados), fg_color="#8e44ad").pack(side="left", padx=2)
        ctk.CTkButton(row, text="🗑️", width=40, command=lambda: self._del_linha(row, dados, lista), fg_color="#c0392b").pack(side="left", padx=2)

        dados = {'nome': e_nom, 'mol': e_mol, 'trans': e_tra, 'log': e_log, 'tot': l_tot, 'vol': e_vol, '_frame': row}
        
        # Bind Cálculo
        for e in [e_mol, e_tra, e_log]:
            e._entry.bind("<KeyRelease>", lambda e, d=dados: self._calc_row(d))
            
        return dados

    def _calc_row(self, d):
        tot = self._val(d['mol']) + self._val(d['trans']) + self._val(d['log'])
        d['tot'].configure(text=f"{tot:.4f}")

    def _val(self, e):
        try: return float(e.get().replace(',', '.'))
        except: return 0.0

    @staticmethod
    def _limpar_str_volume(val: str) -> str:
        """Sanitiza uma string de volume (função pura, sem UI).

        Regras:
          - Troca vírgula por ponto.
          - Mantém apenas dígitos e pontos.
          - Múltiplos pontos → separa o último segmento:
              * 3 dígitos → separador de milhar → remove todos os pontos.
              * outro tamanho → ponto decimal → une os demais e preserva o último.
        """
        limpo = val.replace(",", ".")
        limpo = "".join(c for c in limpo if c.isdigit() or c == ".")
        partes = limpo.split(".")
        if len(partes) > 2:
            ultimo = partes[-1]
            if len(ultimo) == 3:
                limpo = "".join(partes)
            else:
                limpo = "".join(partes[:-1]) + "." + ultimo
        return limpo

    def _sanitizar_vol(self, entry):
        """Remove qualquer caractere inválido do campo Volume (aceita colagem)."""
        val = entry.get()
        limpo = self._limpar_str_volume(val)
        if limpo != val:
            cursor = entry._entry.index(tk.INSERT)
            entry.delete(0, "end")
            entry.insert(0, limpo)
            entry._entry.icursor(min(cursor, len(limpo)))

    def _add_nova(self, parent, lista):
        novo = self._add_linha(parent, "Nova Empresa", lista)
        lista.append(novo)

    def _del_linha(self, row, dados, lista):
        if messagebox.askyesno("Remover", "Apagar linha?"):
            row.destroy()
            if dados in lista: lista.remove(dados)

    # ------------------------------------------------------------------
    # Importar dados da Memória de Cálculo (aba "Custo médio ponderado")
    # ------------------------------------------------------------------
    def _importar_memoria_calculo(self):
        """Lê a Memória de Cálculo e preenche a aba corrente com volumes e preços."""
        from tkinter import filedialog
        import pandas as pd

        path = filedialog.askopenfilename(
            title="Selecione a Memória de Cálculo (Excel)",
            filetypes=[("Excel", "*.xlsx *.xls")],
        )
        if not path:
            return

        # ── Carregar aba de cálculo (tenta vários nomes conhecidos) ──────
        _ABAS_CANDIDATAS = ["PMPV", "Custo médio ponderado", "Custo medio ponderado"]
        df = None
        aba_usada = None
        try:
            xl_tmp = pd.ExcelFile(path)
            for candidata in _ABAS_CANDIDATAS:
                if candidata in xl_tmp.sheet_names:
                    df = pd.read_excel(xl_tmp, sheet_name=candidata, header=None)
                    aba_usada = candidata
                    break
            if df is None:
                # Última chance: primeira aba disponível
                df = pd.read_excel(xl_tmp, sheet_name=xl_tmp.sheet_names[0], header=None)
                aba_usada = xl_tmp.sheet_names[0]
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível ler o arquivo:\n{exc}")
            return

        # ── Detectar colunas de meses (datetime na 1ª linha de empresa) ──
        _PT = {"Jan": "Jan", "Feb": "Fev", "Mar": "Mar", "Apr": "Abr",
               "May": "Mai", "Jun": "Jun", "Jul": "Jul", "Aug": "Ago",
               "Sep": "Set", "Oct": "Out", "Nov": "Nov", "Dec": "Dez"}

        meses_cols: dict[int, str] = {}
        first_header_row = None

        for ri in range(min(15, len(df))):
            for ci in range(2, len(df.columns)):
                cell = df.iloc[ri, ci]
                if pd.notna(cell) and hasattr(cell, "strftime"):
                    first_header_row = ri
                    for ci2 in range(2, len(df.columns)):
                        c2 = df.iloc[ri, ci2]
                        if pd.notna(c2) and hasattr(c2, "strftime"):
                            eng = c2.strftime("%b/%y")          # e.g. "May/25"
                            p   = eng.split("/")
                            lbl = _PT.get(p[0], p[0]) + "/" + p[1]  # "Mai/25"
                            meses_cols[ci2] = lbl
                    break
            if first_header_row is not None:
                break

        if not meses_cols:
            messagebox.showwarning(
                "Aviso",
                f"Nenhuma coluna de mês encontrada na aba '{aba_usada}'.\n"
                "Verifique se o arquivo tem a aba 'PMPV' ou 'Custo médio ponderado'.",
            )
            return

        # ── Pedir mês ao usuário ──────────────────────────────────────────
        meses_list = list(meses_cols.values())
        opcoes     = "  •  ".join(meses_list)
        sel = simpledialog.askstring(
            "Selecionar Mês",
            f"Meses disponíveis:\n  {opcoes}\n\n"
            f"Digite o mês (ex: {meses_list[-1]}):",
            initialvalue=meses_list[-1],
        )
        if not sel:
            return

        col_dados = next(
            (ci for ci, lbl in meses_cols.items()
             if lbl.lower() == sel.strip().lower()
             or sel.strip().lower() in lbl.lower()),
            None,
        )
        if col_dados is None:
            messagebox.showerror(
                "Erro",
                f"Mês '{sel}' não encontrado.\n"
                f"Disponíveis: {', '.join(meses_list)}",
            )
            return

        first_month_col = min(meses_cols.keys())

        # ── Parsear seções de empresa ─────────────────────────────────────
        # Cada seção começa quando col1=NaN e col_mês=datetime (cabeçalho de empresa)
        # Linhas de dados têm col1 em {A, B, C, E}
        empresas: dict[str, dict] = {}
        empresa_atual: str | None = None

        for ri in range(len(df)):
            col1 = df.iloc[ri, 1]
            col2 = df.iloc[ri, 2]
            first_m_cell = df.iloc[ri, first_month_col]

            col1_str = str(col1).strip() if pd.notna(col1) else ""
            col2_str = str(col2).strip() if pd.notna(col2) else ""
            is_date  = pd.notna(first_m_cell) and hasattr(first_m_cell, "strftime")

            # Linha de cabeçalho de empresa
            if (not col1_str or col1_str == "nan") and col2_str and col2_str != "nan" and is_date:
                empresa_atual = col2_str
                empresas.setdefault(empresa_atual, {"mol": 0.0, "trans": 0.0, "log": 0.0, "volume": 0.0})
                continue

            if empresa_atual is None:
                continue

            val_raw = df.iloc[ri, col_dados]
            val     = float(val_raw) if pd.notna(val_raw) and str(val_raw).strip() not in ("", "nan") else 0.0

            if col1_str == "A":
                empresas[empresa_atual]["mol"]    = val
            elif col1_str == "B":
                empresas[empresa_atual]["trans"]  = val
            elif col1_str == "C" and val:
                empresas[empresa_atual]["log"]    = val
            elif col1_str == "E":
                empresas[empresa_atual]["volume"] = val

        # Remover empresas sem volume
        empresas = {k: v for k, v in empresas.items() if v["volume"] > 0}

        if not empresas:
            messagebox.showwarning(
                "Sem dados",
                f"Nenhuma empresa com volume encontrada para o mês '{sel}'.\n"
                "Verifique se os dados de dezembro foram adicionados ao Excel.",
            )
            return

        # ── Preencher a aba corrente ──────────────────────────────────────
        mes_nome = self.tabview.get()
        linhas   = self.dados_meses[mes_nome]
        scroll   = self.scroll_frames.get(mes_nome)

        if scroll is None:
            messagebox.showerror("Erro interno", "Scroll frame não encontrado.")
            return

        # Limpar linhas existentes
        for d in linhas[:]:
            try:
                d["_frame"].destroy()
            except Exception:
                pass
        linhas.clear()

        # Adicionar linhas importadas
        for emp_nome, dados in empresas.items():
            d = self._add_linha(scroll, emp_nome, linhas)
            linhas.append(d)
            for campo in ("mol", "trans", "log"):
                v = dados[campo]
                d[campo].delete(0, "end")
                if v:
                    d[campo].insert(0, f"{v:.4f}")
            d["vol"].delete(0, "end")
            d["vol"].insert(0, f"{dados['volume']:.0f}")
            self._calc_row(d)

        resumo = "\n".join(
            f"  • {n:<35} vol = {v['volume']:>15,.0f}  |  total = {v['mol']+v['trans']+v['log']:.4f} R$/m³"
            for n, v in empresas.items()
        )
        messagebox.showinfo(
            "Importado ✅",
            f"Mês: {sel}  →  {len(empresas)} empresa(s) carregada(s) em '{mes_nome}'\n\n"
            + resumo,
        )

    def _popup_copy(self, origem):
        top = ctk.CTkToplevel(self)
        top.geometry("250x200")
        top.title("Copiar")
        top.transient(self)
        ctk.CTkLabel(top, text="Copiar para:", font=("Roboto", 14, "bold")).pack(pady=10)
        
        for i in range(1, 4):
            nome = f"Mês {i}"
            ctk.CTkButton(top, text=nome, command=lambda n=nome: self._exec_copy(origem, n, top)).pack(pady=5)

    def _linha_disponivel(self, d):
        """Uma linha está disponível como destino de cópia se todos os campos
        de dados (mol, trans, log, vol) estiverem em branco.
        Nome vazio é sempre disponível; 'Nova Empresa' com dados já preenchidos
        não é sobrescrito."""
        nome = d['nome'].get().strip()
        campos_dados = [d['mol'], d['trans'], d['log'], d['vol']]
        todos_vazios = all(not c.get().strip() for c in campos_dados)
        if nome == "":
            return True
        return todos_vazios

    def _exec_copy(self, orig, dest_key, win):
        win.destroy()
        target_list = self.dados_meses[dest_key]
        dest = next((d for d in target_list if self._linha_disponivel(d)), None)

        if not dest:
            messagebox.showinfo(
                "Destino cheio",
                "Não há linha disponível no destino.\n"
                "Clique em '➕ Adicionar' no mês de destino para criar uma linha vazia."
            )
            return

        for k in ['nome', 'mol', 'trans', 'log', 'vol']:
            dest[k].delete(0, "end")
            dest[k].insert(0, orig[k].get())
        self._calc_row(dest)

    def _atualizar_trimestre(self, _=None):
        mes = self.combo_mes.get()
        if not mes: return
        idx = self.lista_meses.index(mes)
        biss = self.chk_biss.get()
        
        for i in range(3):
            m_atual = self.lista_meses[(idx + i) % 12]
            dias = self.mapa_dias[m_atual]
            if m_atual == "Fevereiro" and biss: dias = 29
            self.dias_config[f"Mês {i+1}"] = dias

    def calcular(self):
        c_tot = 0.0
        v_tot_vf = 0.0  # Soma dos Volumes Faturados (VP * dias) para calcular o PMPV
        vp_total = 0.0  # Soma dos Volumes Prospectos (apenas os volumes inseridos)
        
        cg = self._val(self.entry_cg)
        avisos = []
        vp_por_mes: dict[str, float] = {} 
        vf_por_mes: dict[str,float]  ={}# mes_nome → VP daquele mês (soma direta)

        idx_start = self.lista_meses.index(self.combo_mes.get())

        for i, (k, linhas) in enumerate(self.dados_meses.items()):
            dias = self.dias_config.get(k, 30)
            mes_nome = self.lista_meses[(idx_start + i) % 12]
            vp_mes = 0.0  # Soma de VP apenas para este mês
            vf_mes=0.0

            for l in linhas:
                vol = self._val(l['vol'])  # Este é o VP (Volume Prospecto) da empresa
                if vol <= 0:
                    continue

                mol   = self._val(l['mol'])
                trans = self._val(l['trans'])
                log   = self._val(l['log'])
                pr    = mol + trans + log

                # Cálculo do Volume Faturado (VF = VP * dias mensais)
                vf = vol * dias
                
                # Ponderação financeira usa o VF
                c_tot += pr * vf
                v_tot_vf += vf
                vf_mes += vf
                
                # Mas a soma de VP usa apenas o volume original inserido
                vp_mes += vol
                vp_total += vol

                # Registra parâmetros de preço que estavam vazios (tratados como 0)
                campos_vazios = []
                if not l['mol'].get().strip():   campos_vazios.append("Molécula")
                if not l['trans'].get().strip(): campos_vazios.append("Transporte")
                if not l['log'].get().strip():   campos_vazios.append("Logística")

                if campos_vazios:
                    empresa = l['nome'].get().strip() or "(sem nome)"
                    avisos.append(f"  • {mes_nome} | {empresa}: {', '.join(campos_vazios)} → 0")

            if vp_mes > 0:
                vp_por_mes[mes_nome] = vp_mes
                vf_por_mes[mes_nome]=vf_mes

        if v_tot_vf == 0:
            return messagebox.showwarning("Erro", "Volume Zero — nenhuma linha com volume preenchido.")

        # O PMPV é o Custo Total dividido pelo Volume Faturado (VF)
        pmpv  = c_tot / v_tot_vf
        final = pmpv + cg

        self.lbl_pmpv.configure(text=f"PMPV: R$ {pmpv:.4f}")
        self.lbl_final.configure(text=f"PREÇO FINAL: R$ {final:.4f}")
        
        # O ecrã mostra a soma real do VP (sem multiplicar por dias)
        self.lbl_vp.configure(text=f"VP Total: {vp_total:,.0f} m³")

        self.res_final = {
            'volume_total': v_tot_vf,  # Mantemos o VF total para salvaguardar a coerência do custo e relatórios Excel
            'custo_total': c_tot,
            'pmpv': pmpv, 
            'conta_grafica': cg, 
            'preco_final': final,
            'vp_mensal': vp_total,      # Soma pura dos VPs
            'vp_por_mes': vp_por_mes,
            'vf_por_mes': vf_por_mes,   # Dicionário de VPs puros por mês (usado no botão "▼ por mês")
        }

        if avisos:
            messagebox.showinfo(
                "PMPV Calculado ✅  —  Parâmetros vazios",
                f"PMPV = R$ {pmpv:.4f}   |   Preço Final = R$ {final:.4f}\n\n"
                f"Os campos abaixo estavam vazios e foram considerados 0:\n\n"
                + "\n".join(avisos)
            )
    def _popup_vp(self):
        """Exibe janela com VP e VF discriminados por mês."""
        vp_por_mes: dict = (self.res_final or {}).get('vp_por_mes', {})
        vf_por_mes: dict = (self.res_final or {}).get('vf_por_mes', {})
        vp_tot: float    = (self.res_final or {}).get('vp_mensal', 0.0)
        vf_tot: float    = (self.res_final or {}).get('vf_mensal', 0.0)

        win = ctk.CTkToplevel(self)
        win.title("Volumes por Mês")
        win.geometry("450x300")
        win.grab_set()

        ctk.CTkLabel(win, text="Volumes (VP) vs (VF) por Mês", font=("Roboto", 15, "bold")).pack(pady=(16, 8))

        frame = ctk.CTkFrame(win, fg_color="#1e1e2e")
        frame.pack(fill="both", expand=True, padx=16, pady=4)

        if not vp_por_mes:
            ctk.CTkLabel(frame, text="Calcule primeiro o PMPV.", text_color="#aaa").pack(pady=20)
        else:
            # Cabeçalho da tabela do popup
            head = ctk.CTkFrame(frame, fg_color="transparent")
            head.pack(fill="x", padx=12, pady=5)
            ctk.CTkLabel(head, text="Mês", font=("Roboto", 12, "bold"), width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(head, text="VF (Faturado)", font=("Roboto", 12, "bold"), width=100, anchor="e").pack(side="right")
            ctk.CTkLabel(head, text="VP (Prospecto)", font=("Roboto", 12, "bold"), width=100, anchor="e").pack(side="right", padx=10)

            # Linhas com os valores de cada mês
            for mes in vp_por_mes.keys():
                vp_val = vp_por_mes[mes]
                vf_val = vf_por_mes.get(mes, 0.0)
                
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(row, text=mes, font=("Roboto", 13), width=120, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=f"{vf_val:,.0f} m³", font=("Roboto", 13), text_color="#e67e22", width=100, anchor="e").pack(side="right")
                ctk.CTkLabel(row, text=f"{vp_val:,.0f} m³", font=("Roboto", 13, "bold"), text_color="#3498db", width=100, anchor="e").pack(side="right", padx=10)

            # Linha de separação e Totais
            sep = ctk.CTkFrame(frame, height=1, fg_color="#444")
            sep.pack(fill="x", padx=12, pady=6)
            
            row_tot = ctk.CTkFrame(frame, fg_color="transparent")
            row_tot.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row_tot, text="TOTAL", font=("Roboto", 13, "bold"), width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row_tot, text=f"{vf_tot:,.0f} m³", font=("Roboto", 13, "bold"), text_color="#d35400", width=100, anchor="e").pack(side="right")
            ctk.CTkLabel(row_tot, text=f"{vp_tot:,.0f} m³", font=("Roboto", 13, "bold"), text_color="#1abc9c", width=100, anchor="e").pack(side="right", padx=10)

        ctk.CTkButton(win, text="Fechar", command=win.destroy, width=100).pack(pady=12)
    def _get_data_dict(self):
        idx_start = self.lista_meses.index(self.combo_mes.get())
        export = {}
        for i in range(1, 4):
            real_name = self.lista_meses[(idx_start + i - 1) % 12]
            linhas = []
            for l in self.dados_meses[f"Mês {i}"]:
                if l['nome'].get():
                    linhas.append({
                        'empresa': l['nome'].get(), 'molecula': self._val(l['mol']),
                        'transporte': self._val(l['trans']), 'logistica': self._val(l['log']),
                        'volume': self._val(l['vol'])
                    })
            export[real_name] = linhas
        return export

    def salvar(self):
        nome = simpledialog.askstring("Salvar", "Nome da Sessão:")
        if not nome or not hasattr(self, 'res_final'): return
        
        sid = self.db.criar_sessao(nome)
        dados = self._get_data_dict()
        
        idx = 1
        for _, lista in dados.items():
            self.db.salvar_dados_mes(sid, idx, lista); idx += 1
            
        self.db.salvar_resultado(sid, self.res_final['volume_total'], self.res_final['custo_total'],
                                self.res_final['pmpv'], self.res_final['conta_grafica'], self.res_final['preco_final'])
        messagebox.showinfo("Sucesso", "Salvo!")

    def exportar(self):
        if not hasattr(self, 'res_final'): return messagebox.showwarning("Erro", "Calcule antes!")
        dados = self._get_data_dict()
        # Formatar chaves para Mês 1..3 pro excel handler
        d_fmt = {f"Mês {i+1}": v for i, v in enumerate(dados.values())}
        ExcelHandlerPMPV.exportar_trimestre(d_fmt, self.res_final)
        messagebox.showinfo("Sucesso", "Excel Gerado!")

    def exportar_memoria_mc(self):
        """Exporta no formato Memória de Cálculo, reimportável pelo botão 📥 Importar MC.
        O usuário escolhe entre exportar os 3 meses juntos ou apenas 1 mês específico."""
        if not hasattr(self, 'res_final'):
            return messagebox.showwarning("Erro", "Calcule o PMPV antes de exportar.")

        dados_full = self._get_data_dict()
        meses_nomes = list(dados_full.keys())   # ex: ['Outubro', 'Novembro', 'Dezembro']

        # ── Janela de escolha de período ─────────────────────────────
        escolha = {"valor": None}   # mutável para ser capturado pelo closure

        dlg = ctk.CTkToplevel(self)
        dlg.title("Exportar Memória MC")
        dlg.geometry("320x260")
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.transient(self)

        ctk.CTkLabel(dlg, text="Selecione o período para exportar:",
                     font=("Roboto", 13, "bold")).pack(pady=(18, 8))

        def _escolher(v):
            escolha["valor"] = v
            dlg.destroy()

        ctk.CTkButton(
            dlg,
            text=f"📅 Trimestre completo  ({' + '.join(meses_nomes)})",
            command=lambda: _escolher("todos"),
            fg_color="#1a5276", hover_color="#2e86c1",
            width=280,
        ).pack(pady=6)

        ctk.CTkLabel(dlg, text="── ou apenas 1 mês ──",
                     font=("Roboto", 11), text_color="gray").pack(pady=4)

        for mes in meses_nomes:
            ctk.CTkButton(
                dlg,
                text=f"📆 {mes}",
                command=lambda m=mes: _escolher(m),
                fg_color="#154360", hover_color="#1a5276",
                width=280,
            ).pack(pady=4)

        ctk.CTkButton(dlg, text="Cancelar", command=dlg.destroy,
                      fg_color="#7f8c8d", width=100).pack(pady=(8, 4))

        self.wait_window(dlg)

        if escolha["valor"] is None:
            return

        # ── Filtrar dados e recalcular resultado se for 1 mês ────────
        if escolha["valor"] == "todos":
            dados     = dados_full
            dias_cfg  = self.dias_config
            resultado = self.res_final
            sufixo    = "trimestre"
        else:
            mes_sel = escolha["valor"]
            idx     = meses_nomes.index(mes_sel)
            dados   = {mes_sel: dados_full[mes_sel]}
            dias_cfg = {"Mês 1": self.dias_config.get(f"Mês {idx + 1}", 30)}

            # Recalcula PMPV apenas para o mês selecionado
            dias_mes = dias_cfg["Mês 1"]
            c_tot = v_tot = 0.0
            cg = self._val(self.entry_cg)
            for l in dados_full[mes_sel]:
                vol = self._val(l['vol']) if isinstance(l, dict) and 'vol' in l else l.get('volume', 0.0)
                if vol <= 0:
                    continue
                # _get_data_dict devolve dicts com chaves 'molecula','transporte','logistica','volume'
                pr = l.get('molecula', 0.0) + l.get('transporte', 0.0) + l.get('logistica', 0.0)
                v_mes  = vol * dias_mes
                c_tot += pr * v_mes
                v_tot += v_mes

            if v_tot == 0:
                return messagebox.showwarning("Aviso", f"Nenhum volume em {mes_sel}.")

            pmpv_mes  = c_tot / v_tot
            resultado = {
                'volume_total': v_tot, 'custo_total': c_tot,
                'pmpv': pmpv_mes, 'conta_grafica': cg,
                'preco_final': pmpv_mes + cg,
            }
            sufixo = mes_sel

        # ── Diálogo de save ──────────────────────────────────────────
        from tkinter import filedialog
        caminho = filedialog.asksaveasfilename(
            title="Salvar Memória de Cálculo",
            defaultextension=".xlsx",
            initialfile=f"Memória de Cálculo — {sufixo}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not caminho:
            return

        try:
            arq = ExcelHandlerPMPV.exportar_memoria_calculo(
                dados_por_mes=dados,
                resultado=resultado,
                dias_config=dias_cfg,
                nome_arquivo=caminho,
            )
            messagebox.showinfo(
                "✅ Exportado",
                f"Arquivo gerado com sucesso:\n{arq}\n\n"
                "Você pode reimportá-lo com '📥 Importar Memória MC'."
            )
        except Exception as exc:
            messagebox.showerror("Erro ao exportar", str(exc))

    def _salvar_pmpv_mensal(self):
        """Salva o PMPV calculado no banco de dados associado a um período mensal."""
        if not hasattr(self, 'res_final'):
            messagebox.showwarning("Aviso", "Calcule o PMPV antes de salvar.")
            return

        pmpv = self.res_final['pmpv']

        periodo = simpledialog.askstring(
            "Salvar PMPV Mensal",
            f"PMPV calculado: R$ {pmpv:.4f}/m³\n\nDigite o período mensal (ex: Jan/2026):",
            parent=self,
        )
        if not periodo or not periodo.strip():
            return

        periodo = periodo.strip()
        self.db.salvar_pmpv_mensal(periodo, pmpv)

        # Exibe histórico atualizado
        historico = self.db.listar_pmpv_mensal()
        linhas = "\n".join(
            f"  {r['periodo']:<15}  R$ {r['pmpv']:.4f}/m³"
            for r in historico[:8]
        )
        messagebox.showinfo(
            "PMPV Mensal Salvo ✅",
            f"Período  : {periodo}\n"
            f"PMPV     : R$ {pmpv:.4f}/m³\n\n"
            f"Disponível automaticamente no módulo CGF.\n\n"
            f"Últimos registros:\n{linhas}",
        )

if __name__ == "__main__":
    # Truque para rodar sozinho como Toplevel
    root = ctk.CTk()
    root.withdraw()
    app = CalculadoraTrimestralPMPV(root)
    app.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()