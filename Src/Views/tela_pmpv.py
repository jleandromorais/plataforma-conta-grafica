import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog

# --- IMPORTAÇÕES DA NOVA ARQUITETURA ---
# Vai buscar as regras matemáticas à pasta Services
from Src.Services.servicos_pmpv import RegrasPMPV, ExcelPMPV
# Vai buscar a Base de Dados à pasta Database
from Src.Database.database import DatabasePMPV
# Mantive o ExcelHandler em Modules para não quebrar os teus outros códigos por agora!
from Src.Modules.excel_handler import ExcelHandlerPMPV

# ==========================================
# 3. INTERFACE GRÁFICA (A Tela)
# ==========================================
class TelaPMPV(ctk.CTkToplevel):
    """A interface principal do módulo PMPV."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("Sistema PMPV Master - Gestão Trimestral")
        self.geometry("1300x850")
        
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
        self.scroll_frames = {}

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
        self.lbl_vp = ctk.CTkLabel(vp_row, text="VP Total: — m³", font=("Roboto", 13), text_color="#3498db")
        self.lbl_vp.pack(side="left")
        self.btn_vp_detail = ctk.CTkButton(vp_row, text="▼ por mês", command=self._popup_vp, width=80, height=22, font=("Roboto", 11), fg_color="#1a5276", hover_color="#2e86c1")
        self.btn_vp_detail.pack(side="left", padx=(8, 0))

        right = ctk.CTkFrame(foot, fg_color="transparent")
        right.pack(side="right", padx=20)
        ctk.CTkButton(right, text="📥 Importar Memória MC", command=self._importar_memoria_calculo, fg_color="#d35400", hover_color="#e67e22").pack(pady=5)
        ctk.CTkButton(right, text="💾 Salvar Sessão", command=self.salvar, fg_color="#8e44ad").pack(pady=5)
        ctk.CTkButton(right, text="📅 Salvar PMPV Mensal", command=self._salvar_pmpv_mensal, fg_color="#16a085").pack(pady=5)
        ctk.CTkButton(right, text="📊 Exportar Excel", command=self.exportar, fg_color="#2980b9").pack(pady=5)
        ctk.CTkButton(right, text="📄 Exportar Memória MC", command=self.exportar_memoria_mc, fg_color="#1a5276", hover_color="#2e86c1").pack(pady=5)

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
        d['tot'].configure(text=f"{tot:.4f}")

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
            # Chama a RegrasPMPV do ficheiro de Serviços!
            self.res_final = RegrasPMPV.calcular_resultados(
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
        self.lbl_vp.configure(text=f"VP Total: {self.res_final['vp_mensal']:,.0f} m³")

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
            d["vol"].insert(0, f"{dados['volume']:.0f}")
            self._calc_row(d)

        messagebox.showinfo("Importado ✅", f"Mês: {sel} → {len(empresas_importadas)} empresa(s) carregada(s).")

    def _popup_vp(self):
        vp_por_mes = (self.res_final or {}).get('vp_por_mes', {})
        vf_por_mes = (self.res_final or {}).get('vf_por_mes', {})
        vp_tot = (self.res_final or {}).get('vp_mensal', 0.0)
        vf_tot = (self.res_final or {}).get('volume_total', 0.0)

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
            head = ctk.CTkFrame(frame, fg_color="transparent")
            head.pack(fill="x", padx=12, pady=5)
            ctk.CTkLabel(head, text="Mês", font=("Roboto", 12, "bold"), width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(head, text="VF (Faturado)", font=("Roboto", 12, "bold"), width=100, anchor="e").pack(side="right")
            ctk.CTkLabel(head, text="VP (Prospecto)", font=("Roboto", 12, "bold"), width=100, anchor="e").pack(side="right", padx=10)

            for mes in vp_por_mes.keys():
                vp_val = vp_por_mes[mes]
                vf_val = vf_por_mes.get(mes, 0.0)
                
                row = ctk.CTkFrame(frame, fg_color="transparent")
                row.pack(fill="x", padx=12, pady=3)
                ctk.CTkLabel(row, text=mes, font=("Roboto", 13), width=120, anchor="w").pack(side="left")
                ctk.CTkLabel(row, text=f"{vf_val:,.0f} m³", font=("Roboto", 13), text_color="#e67e22", width=100, anchor="e").pack(side="right")
                ctk.CTkLabel(row, text=f"{vp_val:,.0f} m³", font=("Roboto", 13, "bold"), text_color="#3498db", width=100, anchor="e").pack(side="right", padx=10)

            sep = ctk.CTkFrame(frame, height=1, fg_color="#444")
            sep.pack(fill="x", padx=12, pady=6)
            
            row_tot = ctk.CTkFrame(frame, fg_color="transparent")
            row_tot.pack(fill="x", padx=12, pady=2)
            ctk.CTkLabel(row_tot, text="TOTAL", font=("Roboto", 13, "bold"), width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row_tot, text=f"{vf_tot:,.0f} m³", font=("Roboto", 13, "bold"), text_color="#d35400", width=100, anchor="e").pack(side="right")
            ctk.CTkLabel(row_tot, text=f"{vp_tot:,.0f} m³", font=("Roboto", 13, "bold"), text_color="#1abc9c", width=100, anchor="e").pack(side="right", padx=10)

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
        d_fmt = {f"Mês {i+1}": v for i, v in enumerate(dados.values())}
        ExcelHandlerPMPV.exportar_trimestre(d_fmt, self.res_final)
        messagebox.showinfo("Sucesso", "Excel Gerado!")

    def exportar_memoria_mc(self):
        if not hasattr(self, 'res_final'): return messagebox.showwarning("Erro", "Calcule o PMPV antes de exportar.")
        messagebox.showinfo("Aviso", "Funcionalidade simplificada para manter o código limpo. Configure exportar aqui.")

    def _salvar_pmpv_mensal(self):
        if not hasattr(self, 'res_final'): return messagebox.showwarning("Aviso", "Calcule o PMPV antes de salvar.")
        pmpv = self.res_final['pmpv']
        periodo = simpledialog.askstring("Salvar PMPV Mensal", f"PMPV: R$ {pmpv:.4f}/m³\nDigite o período (ex: Jan/2026):", parent=self)
        if not periodo or not periodo.strip(): return

        self.db.salvar_pmpv_mensal(periodo.strip(), pmpv)
        messagebox.showinfo("Salvo", f"Período: {periodo.strip()}\nPMPV: R$ {pmpv:.4f}/m³")

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    app = TelaPMPV(root)
    app.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()