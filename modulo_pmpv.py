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
        self.dados_meses = {} 

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
            self.dados_meses[nome] = self._criar_aba(self.tabview.tab(nome))
        
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

        # Direita: Botões
        right = ctk.CTkFrame(foot, fg_color="transparent")
        right.pack(side="right", padx=20)
        ctk.CTkButton(right, text="💾 Salvar Sessão",       command=self.salvar,               fg_color="#8e44ad").pack(pady=5)
        ctk.CTkButton(right, text="📅 Salvar PMPV Mensal",  command=self._salvar_pmpv_mensal,  fg_color="#16a085").pack(pady=5)
        ctk.CTkButton(right, text="📊 Exportar Excel",      command=self.exportar,             fg_color="#2980b9").pack(pady=5)

    def _criar_aba(self, parent):
        # Cabeçalho Tabela
        head = ctk.CTkFrame(parent, height=30, fg_color="#2c3e50")
        head.pack(fill="x", pady=5)
        cols = [("Empresa", 200), ("Molécula", 100), ("Transporte", 100), ("Logística", 100), ("Total", 100), ("Volume", 120), ("Ações", 80)]
        for txt, w in cols:
            ctk.CTkLabel(head, text=txt, width=w, font=("Roboto", 12, "bold")).pack(side="left", padx=2)

        # Scroll
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
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

        ctk.CTkButton(row, text="📋", width=40, command=lambda: self._popup_copy(dados), fg_color="#8e44ad").pack(side="left", padx=2)
        ctk.CTkButton(row, text="🗑️", width=40, command=lambda: self._del_linha(row, dados, lista), fg_color="#c0392b").pack(side="left", padx=2)

        dados = {'nome': e_nom, 'mol': e_mol, 'trans': e_tra, 'log': e_log, 'tot': l_tot, 'vol': e_vol}
        
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

    def _add_nova(self, parent, lista):
        novo = self._add_linha(parent, "Nova Empresa", lista)
        lista.append(novo)

    def _del_linha(self, row, dados, lista):
        if messagebox.askyesno("Remover", "Apagar linha?"):
            row.destroy()
            if dados in lista: lista.remove(dados)

    def _popup_copy(self, origem):
        top = ctk.CTkToplevel(self)
        top.geometry("250x200")
        top.title("Copiar")
        top.transient(self)
        ctk.CTkLabel(top, text="Copiar para:", font=("Roboto", 14, "bold")).pack(pady=10)
        
        for i in range(1, 4):
            nome = f"Mês {i}"
            ctk.CTkButton(top, text=nome, command=lambda n=nome: self._exec_copy(origem, n, top)).pack(pady=5)

    def _exec_copy(self, orig, dest_key, win):
        win.destroy()
        # Procura linha vazia ou cria nova
        target_list = self.dados_meses[dest_key]
        dest = next((d for d in target_list if d['nome'].get() in ["", "Nova Empresa"]), None)
        
        if not dest: 
             messagebox.showinfo("Ops", "Crie uma linha vazia no destino antes.")
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
        c_tot = v_tot = 0.0
        cg = self._val(self.entry_cg)
        
        for k, linhas in self.dados_meses.items():
            dias = self.dias_config.get(k, 30)
            for l in linhas:
                vol = self._val(l['vol'])
                if vol > 0:
                    v_mes = vol * dias
                    pr = self._val(l['mol']) + self._val(l['trans']) + self._val(l['log'])
                    c_tot += pr * v_mes
                    v_tot += v_mes
        
        if v_tot == 0: return messagebox.showwarning("Erro", "Volume Zero")
        
        pmpv = c_tot / v_tot
        final = pmpv + cg
        
        self.lbl_pmpv.configure(text=f"PMPV: R$ {pmpv:.4f}")
        self.lbl_final.configure(text=f"PREÇO FINAL: R$ {final:.4f}")
        
        self.res_final = {'volume_total': v_tot, 'custo_total': c_tot, 'pmpv': pmpv, 'conta_grafica': cg, 'preco_final': final}

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