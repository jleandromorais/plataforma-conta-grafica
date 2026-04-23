import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
from datetime import datetime

# --- IMPORTAÇÕES DA NOVA ARQUITETURA ---
# Vai buscar as regras matemáticas à pasta Services
from Src.Services.servicos_pmpv import ExcelPMPV
# Casos de uso da aplicação (desacoplados da infraestrutura)
from Src.application.use_cases.pmpv_use_cases import PMPVUseCases
from Src.infrastructure.exporters.excel_handler_pmpv import ExcelHandlerPMPV
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado
from Src.common.excel_final_destino import registrar_execucao_excel_final, solicitar_periodo_excel_final
from Src.Database.database import DatabasePMPV

# ==========================================
# 3. INTERFACE GRÁFICA (A Tela)
# ==========================================
class TelaPMPV(ctk.CTkFrame):
    """A interface principal do módulo PMPV."""

    @staticmethod
    def _fmt_volume(valor: float) -> str:
        texto = f"{valor:,.2f}"
        inteiro, decimal = texto.split(".")
        inteiro = inteiro.replace(",", ".")
        decimal = decimal.rstrip("0")
        return f"{inteiro},{decimal}" if decimal else inteiro
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.use_cases = PMPVUseCases()
        self.empresas_padrao = ["PETROBRAS", "GALP", "PETRORECONCAVO", "BRAVA", "ENEVA", "ORIZON"]
        self.mapa_dias = {
            "Janeiro": 31, "Fevereiro": 28, "Março": 31, "Abril": 30,
            "Maio": 31, "Junho": 30, "Julho": 31, "Agosto": 31,
            "Setembro": 30, "Outubro": 31, "Novembro": 30, "Dezembro": 31
        }
        self.lista_meses = list(self.mapa_dias.keys())
        self.dias_config = {"Mês 1": 30, "Mês 2": 30, "Mês 3": 30}
        self.dados_meses  = {}
        self.scroll_frames = {}
        self.periodos_importados = {}

        self._setup_ui()

    def _setup_ui(self):
        head = ctk.CTkFrame(self, height=60, corner_radius=0)
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Calculadora PMPV Master", font=("Roboto", 24, "bold")).pack(side="left", padx=20, pady=10)

        conf = ctk.CTkFrame(self, fg_color="transparent")
        conf.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(conf, text="📅 Trimestre começa em:", font=("Roboto", 14, "bold")).pack(side="left")
        self.combo_mes = ctk.CTkComboBox(conf, values=self.lista_meses, command=self._atualizar_trimestre)
        self.combo_mes.set("Novembro")
        self.combo_mes.pack(side="left", padx=10)
        
        self.chk_biss = ctk.CTkCheckBox(conf, text="Ano Bissexto", command=self._atualizar_trimestre)
        self.chk_biss.pack(side="left", padx=10)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        for i in range(1, 4):
            nome = f"Mês {i}"
            self.tabview.add(nome)
            self.dados_meses[nome] = self._criar_aba(self.tabview.tab(nome), nome)
        
        self._atualizar_trimestre()

        foot = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=15)
        foot.pack(fill="x", padx=20, pady=20)

        left = ctk.CTkFrame(foot, fg_color="transparent")
        left.pack(side="left", padx=20, pady=20)
        ctk.CTkLabel(left, text="Conta Gráfica (R$):").pack(anchor="w")
        self.entry_cg = ctk.CTkEntry(left, justify="center")
        self.entry_cg.insert(0, "-0.0210")
        self.entry_cg.pack(pady=5)
        ctk.CTkButton(left, text="⚡ CALCULAR", command=self.calcular, fg_color="#27ae60", hover_color="#2ecc71").pack(pady=5)

        center = ctk.CTkFrame(foot, fg_color="transparent")
        center.pack(side="left", expand=True)
        self.lbl_pmpv = ctk.CTkLabel(center, text="PMPV: R$ 0.0000", font=("Roboto", 20))
        self.lbl_pmpv.pack()
        self.lbl_final = ctk.CTkLabel(center, text="PREÇO FINAL: R$ 0.0000", font=("Roboto", 28, "bold"), text_color="#f1c40f")
        self.lbl_final.pack()
        vp_row = ctk.CTkFrame(center, fg_color="transparent")
        vp_row.pack(pady=(4, 0))
        self.lbl_vp = ctk.CTkLabel(vp_row, text="Volume Prospectivo Total: — m³", font=("Roboto", 13), text_color="#3498db")
        self.lbl_vp.pack(side="left")
        self.btn_vp_detail = ctk.CTkButton(vp_row, text="▼ por mês", command=self._popup_vp, width=90, height=22, font=("Roboto", 11), fg_color="#1a5276", hover_color="#2e86c1")
        self.btn_vp_detail.pack(side="left", padx=(8, 0))

        right = ctk.CTkFrame(foot, fg_color="transparent")
        right.pack(side="right", padx=20)
        ctk.CTkLabel(right, text="Ações PMPV", font=("Roboto", 13, "bold")).pack(pady=(0, 4))
        ctk.CTkButton(right, text="📥 Importar Memória de Cálculo", command=self._importar_memoria_calculo, fg_color="#d35400", hover_color="#e67e22").pack(pady=4, fill="x")
        ctk.CTkButton(right, text="💾 Salvar Sessão no Banco", command=self.salvar, fg_color="#8e44ad").pack(pady=4, fill="x")
        ctk.CTkButton(right, text="📅 Salvar PMPV Mensal", command=self._salvar_pmpv_mensal, fg_color="#16a085").pack(pady=4, fill="x")
        ctk.CTkButton(right, text="💧 Salvar VP Mensal", command=self._salvar_vp_mensal, fg_color="#1a5276", hover_color="#2e86c1").pack(pady=4, fill="x")
        ctk.CTkButton(right, text="📊 Exportar Excel do PMPV", command=self.exportar, fg_color="#2980b9").pack(pady=4, fill="x")
        ctk.CTkButton(right, text="➕ Adicionar ao Excel Final (Módulo 9)", command=self._adicionar_excel_final, fg_color="#6c3483", hover_color="#884ea0").pack(pady=4, fill="x")

    def _criar_aba(self, parent, tab_nome: str = ""):
        head = ctk.CTkFrame(parent, height=30, fg_color="#2c3e50")
        head.pack(fill="x", pady=5)
        cols = [("Empresa", 200), ("Molécula", 100), ("Transporte", 100), ("Logística", 100), ("Total", 100), ("Volume", 120), ("Ações", 80)]
        for txt, w in cols:
            ctk.CTkLabel(head, text=txt, width=w, font=("Roboto", 12, "bold")).pack(side="left", padx=2)

        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        if tab_nome: self.scroll_frames[tab_nome] = scroll

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
        e_vol._entry.bind("<FocusOut>", lambda _e, w=e_vol: self._sanitizar_vol(w))
        e_vol._entry.bind("<<Paste>>", lambda _e, w=e_vol: self.after(10, lambda: self._sanitizar_vol(w)))

        ctk.CTkButton(row, text="📋", width=40, command=lambda: self._popup_copy(dados), fg_color="#8e44ad").pack(side="left", padx=2)
        ctk.CTkButton(row, text="🗑️", width=40, command=lambda: self._del_linha(row, dados, lista), fg_color="#c0392b").pack(side="left", padx=2)

        dados = {'nome': e_nom, 'mol': e_mol, 'trans': e_tra, 'log': e_log, 'tot': l_tot, 'vol': e_vol, '_frame': row}
        
        for e in [e_mol, e_tra, e_log]:
            e._entry.bind("<KeyRelease>", lambda e, d=dados: self._calc_row(d))
            
        return dados

    def _calc_row(self, d):
        tot = self._val(d['mol']) + self._val(d['trans']) + self._val(d['log'])
        d['tot'].configure(text=f"{tot:.2f}")

    def _val(self, e):
        try: return float(e.get().replace(',', '.'))
        except: return 0.0

    @staticmethod
    def _limpar_str_volume(val: str) -> str:
        limpo = val.replace(",", ".")
        limpo = "".join(c for c in limpo if c.isdigit() or c == ".")
        partes = limpo.split(".")
        if len(partes) > 2:
            ultimo = partes[-1]
            if len(ultimo) == 3: limpo = "".join(partes)
            else: limpo = "".join(partes[:-1]) + "." + ultimo
        return limpo

    def _sanitizar_vol(self, entry):
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

    def _extrair_dados_da_tela(self):
        dados_extraidos = {}
        for k, linhas_ui in self.dados_meses.items():
            linhas_puras = []
            for l in linhas_ui:
                campos_vazios = []
                if not l['mol'].get().strip(): campos_vazios.append("Molécula")
                if not l['trans'].get().strip(): campos_vazios.append("Transporte")
                if not l['log'].get().strip(): campos_vazios.append("Logística")

                linhas_puras.append({
                    'empresa': l['nome'].get().strip(),
                    'molecula': self._val(l['mol']),
                    'transporte': self._val(l['trans']),
                    'logistica': self._val(l['log']),
                    'volume': self._val(l['vol']),
                    'campos_vazios': campos_vazios
                })
            dados_extraidos[k] = linhas_puras
        return dados_extraidos

    def calcular(self):
        dados = self._extrair_dados_da_tela()
        cg_valor = self._val(self.entry_cg)
        idx_start = self.lista_meses.index(self.combo_mes.get())

        try:
            self.res_final = self.use_cases.calcular_resultados(
                dados_extraidos=dados,
                valor_cg=cg_valor,
                dias_config=self.dias_config,
                lista_meses=self.lista_meses,
                idx_start=idx_start
            )
        except ValueError as e:
            return messagebox.showwarning("Erro", str(e))

        self.lbl_pmpv.configure(text=f"PMPV: R$ {self.res_final['pmpv']:.4f}")
        self.lbl_final.configure(text=f"PREÇO FINAL: R$ {self.res_final['preco_final']:.4f}")
        self.lbl_vp.configure(text=f"Volume Prospectivo Total: {self._fmt_volume(self.res_final['vp_mensal'])} m³")

        if self.res_final['avisos']:
            messagebox.showinfo(
                "PMPV Calculado ✅  —  Parâmetros vazios",
                f"PMPV = R$ {self.res_final['pmpv']:.4f}   |   Preço Final = R$ {self.res_final['preco_final']:.4f}\n\n"
                f"Os campos abaixo estavam vazios e foram considerados 0:\n\n"
                + "\n".join(self.res_final['avisos'])
            )



    def _importar_memoria_calculo(self):
        path = filedialog.askopenfilename(title="Selecione a Memória de Cálculo", filetypes=[("Excel", "*.xlsx *.xls")])
        if not path: return

        sel = simpledialog.askstring("Selecionar Mês", "Digite o mês (ex: Jan/25 ou Outubro):")
        if not sel: return

        try:
            # Chama o ExcelPMPV do ficheiro de Serviços!
            empresas_importadas = ExcelPMPV.ler_dados_memoria_calculo(path, sel.strip())
        except ValueError as e:
            messagebox.showerror("Erro na Importação", str(e))
            return

        if not empresas_importadas:
            messagebox.showwarning("Sem dados", "Nenhuma empresa com volume encontrada para este mês.")
            return

        mes_nome = self.tabview.get()
        self.periodos_importados[mes_nome] = sel.strip()
        linhas = self.dados_meses[mes_nome]
        scroll = self.scroll_frames.get(mes_nome)

        for d in linhas[:]:
            try: d["_frame"].destroy()
            except Exception: pass
        linhas.clear()

        for emp_nome, dados in empresas_importadas.items():
            d = self._add_linha(scroll, emp_nome, linhas)
            linhas.append(d)
            for campo in ("mol", "trans", "log"):
                v = dados[campo]
                d[campo].delete(0, "end")
                if v: d[campo].insert(0, f"{v:.4f}")
            d["vol"].delete(0, "end")
            d["vol"].insert(0, f"{dados['volume']:.7f}")
            self._calc_row(d)

        messagebox.showinfo("Importado ✅", f"Mês: {sel} → {len(empresas_importadas)} empresa(s) carregada(s).")

    def _tab_do_mes(self, mes_nome: str) -> str:
        idx_start = self.lista_meses.index(self.combo_mes.get())
        for i in range(1, 4):
            nome_real = self.lista_meses[(idx_start + i - 1) % 12]
            if nome_real == mes_nome:
                return f"Mês {i}"
        return ""

    def _inferir_periodo_por_ancora(self, mes_nome: str) -> str:
        tab_alvo = self._tab_do_mes(mes_nome)
        if not tab_alvo:
            return ""

        try:
            idx_alvo = int(tab_alvo.split(" ")[1]) - 1
        except Exception:
            return ""

        mapa_abrev_idx = {
            "jan": 0, "fev": 1, "mar": 2, "abr": 3,
            "mai": 4, "jun": 5, "jul": 6, "ago": 7,
            "set": 8, "out": 9, "nov": 10, "dez": 11,
        }
        lista_abrev = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

        for tab_origem, periodo_origem in self.periodos_importados.items():
            if not periodo_origem:
                continue

            periodo_norm = ExcelPMPV._normalizar_mes(periodo_origem)
            if "/" not in periodo_norm:
                continue

            mes_abrev, ano_txt = periodo_norm.split("/", 1)
            if mes_abrev not in mapa_abrev_idx or not ano_txt.isdigit():
                continue

            try:
                idx_origem = int(tab_origem.split(" ")[1]) - 1
            except Exception:
                continue

            delta_tabs = idx_alvo - idx_origem
            total_meses = int(ano_txt) * 12 + mapa_abrev_idx[mes_abrev] + delta_tabs
            novo_ano = total_meses // 12
            novo_mes_idx = total_meses % 12
            return f"{lista_abrev[novo_mes_idx]}/{novo_ano:02d}"

        return ""


    def _periodo_do_mes(self, mes_nome: str) -> str:
        """Dado um nome de mês (ex: 'Novembro'), retorna o período (ex: 'Nov/25') usando as importações."""
        tab_mes = self._tab_do_mes(mes_nome)
        periodo_direto = self.periodos_importados.get(tab_mes, "") if tab_mes else ""
        if periodo_direto:
            return periodo_direto
        return self._inferir_periodo_por_ancora(mes_nome)

    def _buscar_vf_do_cgf(self) -> tuple[dict[str, float], float]:
        """Busca VF real de cada mês no cgf_resumo (calculado pelo módulo CGF)."""
        vf_por_mes = {}
        total = 0.0
        db = DatabasePMPV()
        try:
            for mes_nome in (self.res_final or {}).get("vp_por_mes", {}).keys():
                periodo = self._periodo_do_mes(mes_nome)
                if not periodo:
                    continue
                periodo_norm = ExcelPMPV._normalizar_mes(periodo)
                resumo = db.buscar_cgf_resumo(periodo)
                if not resumo:
                    for item in db.listar_cgf_resumos():
                        if ExcelPMPV._normalizar_mes(str(item.get("periodo", ""))) == periodo_norm:
                            resumo = item
                            break
                if resumo and resumo.get("volume_final") is not None:
                    valor = float(resumo["volume_final"])
                    vf_por_mes[mes_nome] = valor
                    total += valor
        finally:
            db.fechar()
        return vf_por_mes, total

    def _popup_vp(self):
        vp_por_mes = (self.res_final or {}).get('vp_por_mes', {})
        vp_tot = (self.res_final or {}).get('vp_mensal', 0.0)

        win = ctk.CTkToplevel(self)
        win.title("Volume Prospectivo por Mês")
        win.geometry("380x280")
        win.grab_set()

        ctk.CTkLabel(win, text="Volume Prospectivo por Mês (VP)", font=("Roboto", 15, "bold")).pack(pady=(16, 8))
        ctk.CTkLabel(win, text="VF vem do módulo CGF após processar as NFs", font=("Roboto", 11), text_color="#888").pack(pady=(0, 6))
        frame = ctk.CTkFrame(win, fg_color="#1e1e2e")
        frame.pack(fill="both", expand=True, padx=16, pady=4)

        if not vp_por_mes:
            ctk.CTkLabel(frame, text="Calcule primeiro o PMPV.", text_color="#aaa").pack(pady=20)
        else:
            head = ctk.CTkFrame(frame, fg_color="transparent")
            head.pack(fill="x", padx=12, pady=5)
            ctk.CTkLabel(head, text="Mês", font=("Roboto", 12, "bold"), width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(head, text="Volume Prospectivo", font=("Roboto", 12, "bold"), width=160, anchor="e").pack(side="right")

            for mes, vp_val in vp_por_mes.items():
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(row, text=mes, font=("Roboto", 13), width=140, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=f"{self._fmt_volume(vp_val)} m³", font=("Roboto", 13, "bold"), text_color="#3498db", width=160, anchor="e").pack(side="right")

            sep = ctk.CTkFrame(frame, height=1, fg_color="#444")
            sep.pack(fill="x", padx=12, pady=6)

            row_tot = ctk.CTkFrame(frame, fg_color="transparent")
            row_tot.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row_tot, text="TOTAL", font=("Roboto", 13, "bold"), width=140, anchor="w").pack(side="left")
            ctk.CTkLabel(row_tot, text=f"{self._fmt_volume(vp_tot)} m³", font=("Roboto", 13, "bold"), text_color="#1abc9c", width=160, anchor="e").pack(side="right")

        ctk.CTkButton(win, text="Fechar", command=win.destroy, width=100).pack(pady=12)

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
        nome = d['nome'].get().strip()
        campos_dados = [d['mol'], d['trans'], d['log'], d['vol']]
        todos_vazios = all(not c.get().strip() for c in campos_dados)
        if nome == "": return True
        return todos_vazios

    def _exec_copy(self, orig, dest_key, win):
        win.destroy()
        target_list = self.dados_meses[dest_key]
        dest = next((d for d in target_list if self._linha_disponivel(d)), None)

        if not dest:
            return messagebox.showinfo("Destino cheio", "Não há linha disponível no destino.")

        for k in ['nome', 'mol', 'trans', 'log', 'vol']:
            dest[k].delete(0, "end")
            dest[k].insert(0, orig[k].get())
        self._calc_row(dest)

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

        dados = self._get_data_dict()
        self.use_cases.salvar_sessao_completa(nome, dados, self.res_final)
        messagebox.showinfo(
            "Sessão Salva",
            f"VP salvo: {self._fmt_volume(self.res_final.get('vp_mensal', 0.0))} m³\n"
            f"VF será carregado do módulo CGF ao usar o SR."
        )

    def exportar(self):
        if not hasattr(self, 'res_final'): return messagebox.showwarning("Erro", "Calcule antes!")
        dados = self._get_data_dict()
        d_fmt = {f"Mês {i+1}": v for i, v in enumerate(dados.values())}
        ExcelHandlerPMPV.exportar_trimestre(d_fmt, self.res_final)
        messagebox.showinfo("Sucesso", "Excel Gerado!")

    def _salvar_vp_mensal(self):
        if not hasattr(self, 'res_final'):
            return messagebox.showwarning("Aviso", "Calcule o PMPV antes de salvar.")

        vp_por_mes = self.res_final.get('vp_por_mes', {})
        if not vp_por_mes:
            return messagebox.showwarning("Aviso", "Sem dados de VP por mês. Calcule novamente.")

        meses_nome = list(vp_por_mes.keys())
        tabs = [f"Mês {i+1}" for i in range(len(meses_nome))]

        win = ctk.CTkToplevel(self)
        win.title("Salvar VP Mensal")
        win.geometry("400x240")
        win.grab_set()

        ctk.CTkLabel(win, text="Salvar Volume Prospectivo por Mês", font=("Roboto", 14, "bold")).pack(pady=(16, 6))

        frame = ctk.CTkFrame(win, fg_color="transparent")
        frame.pack(fill="x", padx=24, pady=4)
        frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Mês do trimestre:", anchor="w").grid(row=0, column=0, sticky="w", pady=6)
        combo_tab = ctk.CTkComboBox(frame, values=tabs, width=150)
        combo_tab.set(tabs[0])
        combo_tab.grid(row=0, column=1, padx=10, pady=6, sticky="ew")

        vp_inicial = vp_por_mes.get(meses_nome[0], 0.0) if meses_nome else 0.0
        lbl_vp = ctk.CTkLabel(frame, text=f"VP: {self._fmt_volume(vp_inicial)} m³", text_color="#3498db", font=("Roboto", 12, "bold"))
        lbl_vp.grid(row=1, column=0, columnspan=2, pady=4)

        def ao_mudar_mes(choice):
            idx = tabs.index(choice) if choice in tabs else 0
            mes_nome = meses_nome[idx] if idx < len(meses_nome) else ""
            lbl_vp.configure(text=f"VP: {self._fmt_volume(vp_por_mes.get(mes_nome, 0.0))} m³")

        combo_tab.configure(command=ao_mudar_mes)

        ctk.CTkLabel(frame, text="Período (ex: Dez/2025):", anchor="w").grid(row=2, column=0, sticky="w", pady=6)
        entry_periodo = ctk.CTkEntry(frame, width=150, placeholder_text="Dez/2025")
        entry_periodo.grid(row=2, column=1, padx=10, pady=6, sticky="ew")

        def salvar():
            periodo = entry_periodo.get().strip()
            if not periodo:
                messagebox.showwarning("Aviso", "Digite o período.", parent=win)
                return
            choice = combo_tab.get()
            idx = tabs.index(choice) if choice in tabs else 0
            mes_nome = meses_nome[idx] if idx < len(meses_nome) else ""
            vp_val = vp_por_mes.get(mes_nome, 0.0)

            db = DatabasePMPV()
            try:
                db.salvar_vp_mensal(periodo, vp_val)
            finally:
                db.fechar()

            messagebox.showinfo("Salvo ✅", f"Período: {periodo}\nVP: {self._fmt_volume(vp_val)} m³", parent=win)
            win.destroy()

        ctk.CTkButton(win, text="💾 Salvar VP", command=salvar, fg_color="#16a085", hover_color="#0d9488").pack(pady=16)

    def _adicionar_excel_final(self):
        if not hasattr(self, 'res_final'):
            return messagebox.showwarning("Aviso", "Calcule o PMPV antes de adicionar ao Excel final.")

        nome = datetime.now().strftime("PMPV_%d%m%Y_%H%M")
        dados = self._get_data_dict()
        self.use_cases.salvar_sessao_completa(nome, dados, self.res_final)

        periodo = solicitar_periodo_excel_final(
            parent=self,
            titulo="Excel Final (Módulo 9) - PMPV",
            mensagem="Informe o período do relatório final (ex: Dez/2025):",
        )
        if not periodo:
            return

        periodo_salvar = periodo.strip()
        meta_execucao = registrar_execucao_excel_final(etapa="PMPV", periodo=periodo_salvar, parent=self)
        if not meta_execucao:
            return
        destino, nome_sessao, periodo_norm, execucao = meta_execucao
        arquivo = ExcelConsolidado.exportar(periodo=periodo_norm, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅", f"Arquivo criado com sucesso:\n{arquivo}\n\nSessão: {nome_sessao}\nPeríodo: {periodo_norm}\nEtapa PMPV registrada (execução #{execucao}).")

    def _salvar_pmpv_mensal(self):
        if not hasattr(self, 'res_final'): return messagebox.showwarning("Aviso", "Calcule o PMPV antes de salvar.")
        pmpv = self.res_final['pmpv']
        periodo = simpledialog.askstring("Salvar PMPV Mensal", f"PMPV: R$ {pmpv:.4f}/m³\nDigite o período (ex: Jan/2026):", parent=self)
        if not periodo or not periodo.strip(): return

        self.use_cases.salvar_pmpv_mensal(periodo.strip(), pmpv)
        messagebox.showinfo("Salvo", f"Período: {periodo.strip()}\nPMPV: R$ {pmpv:.4f}/m³")

if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste PMPV (embed)")
    root.geometry("1300x850")
    app = TelaPMPV(root)
    app.pack(fill="both", expand=True)
    root.mainloop()