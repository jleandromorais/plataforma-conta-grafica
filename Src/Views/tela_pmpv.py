import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime

# --- IMPORTAÇÕES DA NOVA ARQUITETURA ---
# Vai buscar as regras matemáticas à pasta Services
from Src.Services.servicos_pmpv import ExcelPMPV
# Casos de uso da aplicação (desacoplados da infraestrutura)
from Src.application.use_cases.pmpv_use_cases import PMPVUseCases
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado
from Src.common.excel_final_destino import registrar_execucao_excel_final, novo_excel_final
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
        self._abrevs_meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        self.trimestres = {
            "Nov - Jan": (10, 11, 0),
            "Fev - Abr": (1, 2, 3),
            "Mai - Jul": (4, 5, 6),
            "Ago - Out": (7, 8, 9),
        }
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

        ctk.CTkLabel(conf, text="📅 Período:", font=("Roboto", 14, "bold")).pack(side="left")
        _mes_idx = datetime.now().month - 1  # 0=Jan … 11=Dez
        tri_padrao = next(
            (k for k, v in self.trimestres.items() if _mes_idx in v),
            "Fev - Abr"
        )
        self.combo_trimestre = ctk.CTkComboBox(conf, values=list(self.trimestres.keys()), width=130, command=self._atualizar_trimestre)
        self.combo_trimestre.set(tri_padrao)
        self.combo_trimestre.pack(side="left", padx=(8, 4))

        ctk.CTkLabel(conf, text="Ano:", font=("Roboto", 13)).pack(side="left")
        self.entry_ano = ctk.CTkEntry(conf, width=64, justify="center")
        self.entry_ano.insert(0, str(datetime.now().year))
        self.entry_ano.pack(side="left", padx=(4, 10))
        self.entry_ano._entry.bind("<FocusOut>", self._atualizar_trimestre)

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
        ctk.CTkButton(right, text="➕ Adicionar ao Excel Final (Módulo 9)", command=self._adicionar_excel_final, fg_color="#6c3483", hover_color="#884ea0").pack(pady=4, fill="x")
        ctk.CTkButton(right, text="🗋 Novo Excel (zerar sessão)", command=lambda: novo_excel_final(parent=self), fg_color="#7f8c8d", hover_color="#95a5a6").pack(pady=4, fill="x")

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
        tri = self.combo_trimestre.get()
        if not tri or tri not in self.trimestres: return
        biss = self.chk_biss.get()
        for i, mes_idx in enumerate(self.trimestres[tri]):
            m_atual = self.lista_meses[mes_idx]
            dias = self.mapa_dias[m_atual]
            if m_atual == "Fevereiro" and biss: dias = 29
            self.dias_config[f"Mês {i+1}"] = dias

        # Grava o trimestre activo no banco para os outros módulos usarem
        try:
            periodos = self._get_periodos_trimestre()
            if periodos:
                from Src.Database.database import DatabasePMPV as _DB
                db = _DB()
                try:
                    db.salvar_trimestre_ativo(periodos)
                finally:
                    db.fechar()
        except Exception:
            pass

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
        tri = self.combo_trimestre.get()
        idx_start = self.trimestres.get(tri, (0, 1, 2))[0]

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

        periodos = self._get_periodos_trimestre()
        if not periodos:
            return messagebox.showwarning("Aviso", "Verifique o trimestre e o ano selecionados.")

        erros = []
        importados = 0

        for i, periodo in enumerate(periodos):
            tab_nome = f"Mês {i+1}"
            try:
                empresas_importadas = ExcelPMPV.ler_dados_memoria_calculo(path, periodo)
            except ValueError as e:
                erros.append(f"{tab_nome} ({periodo}): {e}")
                continue

            if not empresas_importadas:
                erros.append(f"{tab_nome} ({periodo}): nenhuma empresa com volume encontrada.")
                continue

            self.periodos_importados[tab_nome] = periodo
            linhas = self.dados_meses[tab_nome]
            scroll = self.scroll_frames.get(tab_nome)

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

            importados += 1

        tri = self.combo_trimestre.get()
        if erros and importados == 0:
            messagebox.showerror("Erro na Importação", "\n".join(erros))
        elif erros:
            messagebox.showwarning(
                "Importação Parcial ⚠️",
                f"{importados}/3 meses importados do trimestre {tri}.\n\nProblemas:\n" + "\n".join(erros)
            )
        else:
            messagebox.showinfo("Importado ✅", f"Trimestre {tri}: 3 meses carregados automaticamente.")

    def _tab_do_mes(self, mes_nome: str) -> str:
        tri = self.combo_trimestre.get()
        indices = self.trimestres.get(tri, (0, 1, 2))
        for i, mes_idx in enumerate(indices):
            if self.lista_meses[mes_idx] == mes_nome:
                return f"Mês {i+1}"
        return ""

    def _get_periodos_trimestre(self) -> list:
        """Retorna ex: ['Nov/25', 'Dez/25', 'Jan/26'] respeitando virada de ano."""
        tri = self.combo_trimestre.get()
        indices = self.trimestres.get(tri, [])
        try:
            ano = int(self.entry_ano.get())
        except ValueError:
            return []
        periodos = []
        ano_atual = ano
        for i, mes_idx in enumerate(indices):
            if i > 0 and mes_idx < indices[i - 1]:
                ano_atual += 1
            periodos.append(f"{self._abrevs_meses[mes_idx]}/{ano_atual}")
        return periodos

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
        """Dado um nome de mês (ex: 'Novembro'), retorna o período (ex: 'Nov/25')."""
        tab_mes = self._tab_do_mes(mes_nome)
        periodo_direto = self.periodos_importados.get(tab_mes, "") if tab_mes else ""
        if periodo_direto:
            return periodo_direto
        inferido = self._inferir_periodo_por_ancora(mes_nome)
        if inferido:
            return inferido
        # Fallback automático: usa o trimestre e ano selecionados na UI
        periodos = self._get_periodos_trimestre()
        tri = self.combo_trimestre.get()
        for i, mes_idx in enumerate(self.trimestres.get(tri, [])):
            if self.lista_meses[mes_idx] == mes_nome and i < len(periodos):
                return periodos[i]
        return ""

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
        tri = self.combo_trimestre.get()
        indices = self.trimestres.get(tri, (0, 1, 2))
        export = {}
        for i, mes_idx in enumerate(indices):
            real_name = self.lista_meses[mes_idx]
            linhas = []
            for l in self.dados_meses[f"Mês {i+1}"]:
                if l['nome'].get():
                    linhas.append({
                        'empresa': l['nome'].get(), 'molecula': self._val(l['mol']),
                        'transporte': self._val(l['trans']), 'logistica': self._val(l['log']),
                        'volume': self._val(l['vol'])
                    })
            export[real_name] = linhas
        return export

    def salvar(self):
        if not hasattr(self, 'res_final'):
            return messagebox.showwarning("Aviso", "Calcule o PMPV antes de salvar.")
        tri = self.combo_trimestre.get().replace(" ", "_").replace("-", "_")
        ano = self.entry_ano.get()
        nome = f"PMPV_{tri}_{ano}"
        dados = self._get_data_dict()
        try:
            self.use_cases.salvar_sessao_completa(nome, dados, self.res_final)
            pmpv  = self.res_final.get("pmpv", 0)
            preco = self.res_final.get("preco_final", 0)
            messagebox.showinfo(
                "Sessão Salva ✅",
                f"Sessão '{nome}' gravada com sucesso no banco de dados.\n\n"
                f"PMPV:         R$ {pmpv:.4f} /m³\n"
                f"Preço Final:  R$ {preco:.4f} /m³"
            )
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar a sessão:\n\n{e}")

    def _adicionar_excel_final(self):
        if not hasattr(self, 'res_final'):
            return messagebox.showwarning("Aviso", "Calcule o PMPV antes de adicionar ao Excel final.")

        periodos = self._get_periodos_trimestre()
        periodo_salvar = periodos[-1] if periodos else ""
        if not periodo_salvar:
            return messagebox.showwarning("Aviso", "Verifique o trimestre e o ano selecionados.")

        # Confirmação antes de executar
        confirmado = self._confirmar_modulo9(periodos, periodo_salvar)
        if not confirmado:
            return

        nome = datetime.now().strftime("PMPV_%d%m%Y_%H%M")
        dados = self._get_data_dict()
        self.use_cases.salvar_sessao_completa(nome, dados, self.res_final)

        meta_execucao = registrar_execucao_excel_final(etapa="PMPV", periodo=periodo_salvar, parent=self)
        if not meta_execucao:
            return
        destino, nome_sessao, periodo_norm, execucao = meta_execucao
        arquivo = ExcelConsolidado.exportar(
            periodo=periodo_norm,
            nome_arquivo=destino,
            periodos_trimestre=periodos,   # passa os 3 meses do trimestre
        )
        self._mostrar_sucesso_modulo9(arquivo, periodo_norm, execucao, periodos)

    def _confirmar_modulo9(self, periodos: list, periodo_salvar: str) -> bool:
        """Confirmação simples e fiável usando messagebox nativo."""
        tri   = self.combo_trimestre.get()
        ano   = self.entry_ano.get()
        pmpv  = self.res_final.get("pmpv", 0)
        preco = self.res_final.get("preco_final", 0)
        cg    = self.res_final.get("conta_grafica", 0)
        vp    = self.res_final.get("vp_mensal", self.res_final.get("volume_programado_mensal", 0))
        meses = " | ".join(periodos)

        msg = (
            f"Adicionar ao Excel Final — Módulo 9\n"
            f"{'─' * 42}\n"
            f"Trimestre:        {tri} / {ano}\n"
            f"Meses:            {meses}\n"
            f"Período chave:    {periodo_salvar}\n"
            f"{'─' * 42}\n"
            f"PMPV:             R$ {pmpv:.4f} /m³\n"
            f"Conta Gráfica:    R$ {cg:.4f} /m³\n"
            f"Preço Final (PV): R$ {preco:.4f} /m³\n"
            f"Volume Prosp.:    {vp:,.0f} m³\n"
            f"{'─' * 42}\n"
            f"Confirmar exportação?"
        )
        return messagebox.askyesno("Confirmar — Módulo 9", msg)

    def _mostrar_sucesso_modulo9(self, arquivo: str, periodo: str, execucao: int, periodos: list | None = None):
        """Diálogo de sucesso estilizado para adição ao Módulo 9."""
        win = ctk.CTkToplevel(self)
        win.title("Módulo 9 — Concluído")
        win.geometry("480x310")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.lift()
        win.after(50, win.grab_set)   # delay evita falha do grab_set no CTkToplevel

        # Faixa verde no topo
        topo = ctk.CTkFrame(win, height=6, fg_color="#27ae60", corner_radius=0)
        topo.pack(fill="x")

        # Ícone + título
        ctk.CTkLabel(
            win,
            text="✅  Adicionado ao Excel Final",
            font=("Roboto", 18, "bold"),
            text_color="#27ae60",
        ).pack(pady=(18, 4))

        ctk.CTkLabel(
            win,
            text="Os dados do PMPV foram gravados com sucesso no Módulo 9.",
            font=("Roboto", 12),
            text_color="#aaaaaa",
        ).pack(pady=(0, 16))

        # Detalhes
        frame_det = ctk.CTkFrame(win, fg_color="#1a1a2e", corner_radius=10)
        frame_det.pack(fill="x", padx=20, pady=(0, 16))

        def _row(label: str, valor: str):
            f = ctk.CTkFrame(frame_det, fg_color="transparent")
            f.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(f, text=label, font=("Roboto", 11), text_color="#7f8c8d", width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=valor, font=("Roboto", 11, "bold"), text_color="#ecf0f1", anchor="w").pack(side="left")

        meses_txt = "  ·  ".join(periodos) if periodos else periodo
        _row("Trimestre:", meses_txt)
        _row("Período chave:", periodo)
        _row("Execução nº:", str(execucao))
        _row("Arquivo:", arquivo.split("\\")[-1] if "\\" in arquivo else arquivo.split("/")[-1])

        ctk.CTkButton(
            win,
            text="Fechar",
            command=win.destroy,
            width=120,
            fg_color="#27ae60",
            hover_color="#2ecc71",
        ).pack(pady=(0, 18))

if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste PMPV (embed)")
    root.geometry("1300x850")
    app = TelaPMPV(root)
    app.pack(fill="both", expand=True)
    root.mainloop()