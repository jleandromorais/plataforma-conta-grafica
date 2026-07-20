from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox, simpledialog
from Src.config import ui_theme as ui
from Src.Services.servicos_scg import ServicosSCG
from Src.Services.servicos_auditoria import empresa_integra_cgr
from Src.Database.database import DatabasePMPV
from Src.common.formatting import format_brl_plain
from Src.common.periodos import TRIMESTRES_CIVIS, MESES_ABREVS as MESES_ANO
from Src.common.excel_final_destino import registrar_execucao_excel_final, remover_excel_final_ativo
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# ── Cores (aliases do design system central — ver Src/config/ui_theme.py) ──────
COR_CARD     = ui.COR_CARD
COR_FUNDO    = ui.COR_FUNDO
COR_INPUT    = ui.COR_INPUT
COR_VERDE    = ui.COR_SUCESSO
COR_AZUL     = ui.COR_PRIMARIA
COR_VERMELHO = ui.COR_PERIGO
COR_AMARELO  = ui.COR_DESTAQUE
COR_ROXO     = ui.COR_ROXO
COR_TEXTO    = ui.COR_TEXTO
COR_MUTED    = ui.COR_MUTED


from Src.common.formatting import format_brl as _fmt


class LinhaValor(ctk.CTkFrame):
    def __init__(self, parent, icone: str, nome: str, key: str,
                 cor_icone: str = COR_AZUL, editavel: bool = True):
        super().__init__(parent, fg_color="transparent")
        self.key = key
        self.editavel = editavel

        ctk.CTkLabel(self, text=icone, font=("Segoe UI Emoji", 18),
                     width=36, text_color=cor_icone).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(self, text=nome, font=("Roboto", 13),
                     width=200, anchor="w", text_color=COR_TEXTO).pack(side="left")

        self.badge = ctk.CTkLabel(self, text="BD", font=("Roboto", 10, "bold"),
                                   width=52, height=22, corner_radius=11,
                                   fg_color=COR_VERDE, text_color="white")
        self.badge.pack(side="left", padx=8)

        self.lbl_valor = ctk.CTkLabel(self, text="R$ 0,00",
                                       font=("Roboto", 15, "bold"),
                                       width=190, height=36, corner_radius=8,
                                       fg_color=COR_INPUT, text_color=COR_TEXTO, anchor="e")
        self.lbl_valor.pack(side="left", padx=8)

        self.entry = ctk.CTkEntry(self, placeholder_text="0,00",
                                   font=("Roboto", 14), width=190, height=36)

    def set_valor(self, valor: float, origem: str = "BD"):
        self.lbl_valor.configure(text=_fmt(valor))
        if origem == "BD":     self.badge.configure(text="📥 BD",     fg_color=COR_VERDE)
        elif origem == "Manual": self.badge.configure(text="✏️ Manual", fg_color=COR_AMARELO)
        elif origem == "Calc": self.badge.configure(text="🔢 Calc",   fg_color=COR_ROXO)

    def get_valor_entry(self) -> float:
        txt = self.entry.get().strip()
        if not txt: return 0.0
        ld, lc = txt.rfind("."), txt.rfind(",")
        if lc > ld: txt = txt.replace(".", "").replace(",", ".")
        elif ld > lc and lc >= 0: txt = txt.replace(",", "")
        else:
            if ld >= 0 and len(txt[ld+1:]) == 3 and txt[ld+1:].isdigit():
                txt = txt.replace(".", "")
        neg = txt.startswith("-")
        txt = "".join(c for c in txt if c.isdigit() or c == ".")
        if neg: txt = "-" + txt
        try: return float(txt)
        except ValueError: return 0.0

    def set_entry_value(self, valor: float):
        self.entry.delete(0, "end")
        self.entry.insert(0, format_brl_plain(valor))

    def mostrar_modo_auto(self):
        self.entry.pack_forget()
        self.lbl_valor.pack(side="left", padx=8)

    def mostrar_modo_manual(self):
        if self.editavel:
            self.lbl_valor.pack_forget()
            self.entry.pack(side="left", padx=8)


class TelaSCG(ctk.CTkFrame):
    CAMPOS = [
        ("cgr", "📄", "CGR  (Auditoria CGR)",   COR_AZUL,    True),
        ("cgf", "📋", "CGF  (Volume Faturado)",  COR_VERDE,   True),
        ("rpv", "🔢", "RPV  = CGR − CGF",        COR_ROXO,    False),
        ("ret", "⚡", "RET  (Encargos)",          COR_AMARELO, True),
        ("rp",  "🔄", "RP   (Conciliação)",       COR_AZUL,    True),
    ]

    TRIMESTRES = TRIMESTRES_CIVIS

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=COR_FUNDO)
        self.servicos      = ServicosSCG()
        self.periodo_atual = None
        self.modo_manual   = False
        self.modo_trimestral = False
        self._dados_tri: list[dict] = []   # [{mes, cgr, cgf, rpv, ret, rp, scg}, ...]

        self._build_ui()
        self._carregar_periodos()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        import datetime as _dt

        # HEADER
        hdr = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="💼  Consolidação SCG",
                     font=("Roboto", 22, "bold"), text_color=COR_TEXTO).pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(hdr, text="SCG = RPV + RET + RP",
                     font=("Roboto", 11), text_color=COR_MUTED).pack(side="left")

        # BARRA DE PERÍODO
        self.bar_periodo = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=0, height=52)
        self.bar_periodo.pack(fill="x", pady=(2, 0))
        self.bar_periodo.pack_propagate(False)

        ctk.CTkLabel(self.bar_periodo, text="Período:", font=("Roboto", 12),
                     text_color=COR_MUTED).pack(side="left", padx=(20, 6), pady=14)
        self.combo_periodo = ctk.CTkComboBox(self.bar_periodo, width=180, font=("Roboto", 12),
                                              command=self._ao_mudar_periodo)
        self.combo_periodo.pack(side="left", pady=14)
        ctk.CTkButton(self.bar_periodo, text="➕ Novo", width=80, height=30, fg_color=COR_AZUL,
                      font=("Roboto", 11, "bold"),
                      command=self._criar_periodo).pack(side="left", padx=8, pady=14)
        ctk.CTkButton(self.bar_periodo, text="🗑 Excluir", width=80, height=30, fg_color=COR_VERMELHO,
                      font=("Roboto", 11, "bold"),
                      command=self._excluir_periodo).pack(side="left", padx=(0, 20), pady=14)

        # TOGGLE MODO FONTE
        self.frame_toggle = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_toggle.pack(fill="x", padx=24, pady=(14, 0))

        ctk.CTkLabel(self.frame_toggle, text="Fonte dos valores:",
                     font=("Roboto", 12), text_color=COR_MUTED).pack(side="left")
        self.btn_auto = ctk.CTkButton(
            self.frame_toggle, text="🔄 Automático (BD)", width=180, height=32,
            font=("Roboto", 12, "bold"), fg_color=COR_VERDE,
            command=self._ativar_modo_auto)
        self.btn_auto.pack(side="left", padx=(10, 6))
        self.btn_manual = ctk.CTkButton(
            self.frame_toggle, text="✏️ Manual", width=110, height=32,
            font=("Roboto", 12, "bold"), fg_color=COR_INPUT,
            command=self._ativar_modo_manual)
        self.btn_manual.pack(side="left", padx=(0, 6))
        self.btn_trimestral = ctk.CTkButton(
            self.frame_toggle, text="📅 Trimestral", width=130, height=32,
            font=("Roboto", 12, "bold"), fg_color=COR_INPUT,
            command=self._ativar_modo_trimestral)
        self.btn_trimestral.pack(side="left")

        # PAINEL TRIMESTRAL (oculto por padrão)
        self.frame_tri = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)

        ctk.CTkLabel(self.frame_tri, text="📅  Trimestre",
                     font=("Roboto", 13, "bold"), text_color=COR_AMARELO).pack(
            anchor="w", padx=16, pady=(12, 6))

        row_tri = ctk.CTkFrame(self.frame_tri, fg_color="transparent")
        row_tri.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(row_tri, text="Trimestre:", font=("Roboto", 11),
                     text_color=COR_MUTED).pack(side="left")
        self.combo_trimestre_scg = ctk.CTkComboBox(
            row_tri, values=list(self.TRIMESTRES.keys()), width=130,
            font=("Roboto", 11), state="readonly",
            command=lambda _: None)
        self.combo_trimestre_scg.set("Jan - Mar")
        self.combo_trimestre_scg.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(row_tri, text="Ano:", font=("Roboto", 11),
                     text_color=COR_MUTED).pack(side="left")
        self.entry_ano_tri = ctk.CTkEntry(row_tri, width=65, justify="center",
                                           font=("Roboto", 11))
        self.entry_ano_tri.insert(0, str(_dt.datetime.now().year))
        self.entry_ano_tri.pack(side="left", padx=(4, 12))

        ctk.CTkButton(row_tri, text="⚡ Carregar Trimestre", width=160, height=32,
                      font=("Roboto", 11, "bold"), fg_color=COR_VERDE,
                      hover_color="#059669",
                      command=self._carregar_trimestre).pack(side="left", padx=(0, 6))

        ctk.CTkButton(row_tri, text="📥 Usar trimestre ativo",
                      width=160, height=32, font=("Roboto", 11),
                      fg_color=COR_INPUT, hover_color=COR_AZUL,
                      command=self._usar_trimestre_ativo).pack(side="left")

        # Tabela mensal (dentro do frame_tri)
        self.frame_tabela_tri = ctk.CTkScrollableFrame(
            self.frame_tri, fg_color="transparent", height=160)
        self.frame_tabela_tri.pack(fill="x", padx=16, pady=(8, 12))

        # CAIXA RPV
        self.rpv_card = ctk.CTkFrame(self, fg_color=ui.COR_REALCE, corner_radius=12)
        rpv_card = self.rpv_card
        rpv_card.pack(fill="x", padx=24, pady=(14, 0))
        ctk.CTkLabel(rpv_card, text="🔢  RPV — Requisição de Pequeno Valor",
                     font=("Roboto", 13, "bold"), text_color=COR_ROXO).pack(
            anchor="w", padx=20, pady=(12, 4))
        row_rpv = ctk.CTkFrame(rpv_card, fg_color="transparent")
        row_rpv.pack(fill="x", padx=20, pady=(0, 14))

        self.lbl_rpv_cgr = ctk.CTkLabel(row_rpv, text="CGR\nR$ 0,00",
                                          font=("Roboto", 13, "bold"), fg_color=COR_AZUL,
                                          corner_radius=8, width=160, height=52, text_color="white")
        self.lbl_rpv_cgr.pack(side="left")
        ctk.CTkLabel(row_rpv, text=" − ", font=("Roboto", 22, "bold"),
                     text_color=COR_VERMELHO).pack(side="left", padx=8)
        self.lbl_rpv_cgf = ctk.CTkLabel(row_rpv, text="CGF\nR$ 0,00",
                                          font=("Roboto", 13, "bold"), fg_color=COR_VERDE,
                                          corner_radius=8, width=160, height=52, text_color="white")
        self.lbl_rpv_cgf.pack(side="left")
        ctk.CTkLabel(row_rpv, text=" = ", font=("Roboto", 22, "bold"),
                     text_color=COR_AMARELO).pack(side="left", padx=8)
        self.lbl_rpv_resultado = ctk.CTkLabel(row_rpv, text="RPV\nR$ 0,00",
                                               font=("Roboto", 14, "bold"), fg_color=COR_ROXO,
                                               corner_radius=8, width=180, height=52, text_color="white")
        self.lbl_rpv_resultado.pack(side="left")

        # PAINEL DE VALORES
        painel = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        painel.pack(fill="x", padx=24, pady=10)
        ctk.CTkLabel(painel, text="Valores por módulo",
                     font=("Roboto", 13, "bold"), text_color=COR_MUTED).pack(
            anchor="w", padx=20, pady=(14, 8))

        self.linhas: dict[str, LinhaValor] = {}
        for key, icone, nome, cor, edit in self.CAMPOS:
            linha = LinhaValor(painel, icone, nome, key, cor, edit)
            linha.pack(fill="x", padx=20, pady=5)
            self.linhas[key] = linha

        ctk.CTkFrame(painel, height=1, fg_color=COR_INPUT).pack(fill="x", padx=20, pady=(10, 0))
        self.btn_salvar_manual = ctk.CTkButton(
            painel, text="💾 Salvar valores manuais no banco",
            font=("Roboto", 12, "bold"), height=36,
            fg_color=COR_AMARELO, text_color="black",
            command=self._salvar_manual)
        ctk.CTkFrame(painel, height=8, fg_color="transparent").pack()

        # RESULTADO SCG
        res = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        res.pack(fill="x", padx=24, pady=(0, 14))
        row_res = ctk.CTkFrame(res, fg_color="transparent")
        row_res.pack(fill="x", padx=20, pady=16)

        self.btn_calcular = ctk.CTkButton(
            row_res, text="⚡  CALCULAR SCG",
            font=("Roboto", 15, "bold"), height=50, width=220,
            fg_color=COR_VERMELHO, command=self._calcular_scg)
        self.btn_calcular.pack(side="left")

        self.btn_excel_final = ctk.CTkButton(
            row_res, text="➕ Excel Final (Módulo 9)",
            font=("Roboto", 13, "bold"), height=50, width=230,
            fg_color="#6c3483", hover_color="#884ea0",
            command=self._adicionar_excel_final)
        self.btn_excel_final.pack(side="left", padx=(10, 0))

        self.btn_remover_excel_final = ctk.CTkButton(
            row_res, text="➖ Retirar Excel Final",
            font=("Roboto", 12, "bold"), height=50, width=200,
            fg_color=COR_INPUT, hover_color=COR_VERMELHO,
            command=self._remover_excel_final)
        self.btn_remover_excel_final.pack(side="left", padx=(10, 0))

        self.lbl_scg = ctk.CTkLabel(row_res, text="SCG =  R$ 0,00",
                                     font=("Roboto", 26, "bold"), text_color=COR_AMARELO)
        self.lbl_scg.pack(side="left", padx=30)

        # HISTÓRICO
        hist_frame = ctk.CTkFrame(self, fg_color=COR_CARD, corner_radius=12)
        hist_frame.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        ctk.CTkLabel(hist_frame, text="📅  Histórico de períodos",
                     font=("Roboto", 13, "bold"), text_color=COR_MUTED).pack(
            anchor="w", padx=20, pady=(14, 6))
        self.hist_box = ctk.CTkTextbox(hist_frame, font=("Consolas", 11),
                                        fg_color=COR_FUNDO, text_color=COR_MUTED, height=120)
        self.hist_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ── MODOS ─────────────────────────────────────────────────────────────────

    def _ativar_modo_auto(self):
        self.modo_manual = False
        self.modo_trimestral = False
        self.btn_auto.configure(fg_color=COR_VERDE)
        self.btn_manual.configure(fg_color=COR_INPUT)
        self.btn_trimestral.configure(fg_color=COR_INPUT)
        self.bar_periodo.pack(fill="x", pady=(2, 0), before=self.frame_toggle)
        self.frame_tri.pack_forget()
        self.btn_salvar_manual.pack_forget()
        for l in self.linhas.values(): l.mostrar_modo_auto()
        if self.periodo_atual: self._ao_mudar_periodo(self.periodo_atual)

    def _ativar_modo_manual(self):
        self.modo_manual = True
        self.modo_trimestral = False
        self.btn_manual.configure(fg_color=COR_AMARELO, text_color="black")
        self.btn_auto.configure(fg_color=COR_INPUT)
        self.btn_trimestral.configure(fg_color=COR_INPUT)
        self.bar_periodo.pack(fill="x", pady=(2, 0), before=self.frame_toggle)
        self.frame_tri.pack_forget()
        for l in self.linhas.values(): l.mostrar_modo_manual()
        self.btn_salvar_manual.pack(fill="x", padx=20, pady=(6, 12))

    def _ativar_modo_trimestral(self):
        self.modo_trimestral = True
        self.modo_manual = False
        self.btn_trimestral.configure(fg_color=COR_AMARELO, text_color="black")
        self.btn_auto.configure(fg_color=COR_INPUT)
        self.btn_manual.configure(fg_color=COR_INPUT)
        self.bar_periodo.pack_forget()
        self.btn_salvar_manual.pack_forget()
        for l in self.linhas.values(): l.mostrar_modo_auto()
        # Insere o painel trimestral logo abaixo do toggle
        self.frame_tri.pack(fill="x", padx=24, pady=(8, 0),
                             before=self.rpv_card)

    # ── TRIMESTRAL ────────────────────────────────────────────────────────────

    def _get_meses_tri(self) -> list[str]:
        tri = self.combo_trimestre_scg.get()
        ano = self.entry_ano_tri.get().strip() or "2026"
        if len(ano) == 2: ano = "20" + ano
        meses_abrev = self.TRIMESTRES.get(tri, ["Jan", "Fev", "Mar"])
        return [f"{m}/{ano}" for m in meses_abrev]

    def _usar_trimestre_ativo(self):
        with DatabasePMPV() as db:
            meses = db.buscar_trimestre_ativo()
        if not meses or len(meses) < 3:
            messagebox.showwarning("Aviso", "Nenhum trimestre ativo salvo.\nSalve primeiro pelo módulo PMPV.")
            return
        # Detecta qual trimestre corresponde aos meses ativos
        abrevs = [m.split("/")[0] for m in meses]
        ano = meses[-1].split("/")[1] if "/" in meses[-1] else str(__import__("datetime").datetime.now().year)
        if len(ano) == 2: ano = "20" + ano
        for nome, lista in self.TRIMESTRES.items():
            if lista == abrevs:
                self.combo_trimestre_scg.set(nome)
                break
        self.entry_ano_tri.delete(0, "end")
        self.entry_ano_tri.insert(0, ano)
        self._carregar_trimestre()

    def _carregar_trimestre(self):
        meses = self._get_meses_tri()
        self._dados_tri = []
        total = {"cgr": 0.0, "cgf": 0.0, "rpv": 0.0, "ret": 0.0, "rp": 0.0, "scg": 0.0}

        for mes in meses:
            d = self._buscar_dados_fontes(mes)
            d["mes"] = mes
            self._dados_tri.append(d)
            for k in total: total[k] += d[k]

        # Atualiza os totais nos cards existentes
        self._aplicar_dados(total)

        # Reconstrói a tabela mensal
        for w in self.frame_tabela_tri.winfo_children():
            w.destroy()

        colunas = ["DADOS", "UNIDADE"] + meses + ["TOTAL"]
        larguras = [22, 8] + [14] * len(meses) + [16]

        # Cabeçalho
        hdr = ctk.CTkFrame(self.frame_tabela_tri, fg_color="#0e4d8f", corner_radius=6)
        hdr.pack(fill="x", pady=(0, 2))
        for col, larg in zip(colunas, larguras):
            ctk.CTkLabel(hdr, text=col, font=("Roboto", 10, "bold"),
                         text_color="white", width=larg * 7, anchor="center").pack(
                side="left", padx=2, pady=4)

        # Linhas de dados
        campos = [
            ("CGR",             "R$", "cgr", COR_AZUL),
            ("CGF",             "R$", "cgf", COR_VERDE),
            ("RPV = CGR − CGF", "R$", "rpv", COR_ROXO),
            ("RET (EAT + EC)",  "R$", "ret", COR_AMARELO),
            ("RP (Penalidades)","R$", "rp",  COR_MUTED),
            ("SCG",             "R$", "scg", COR_VERMELHO),
        ]

        for li, (label, unidade, key, cor) in enumerate(campos):
            bg = COR_CARD if li % 2 == 0 else ui.COR_CARD_ALT
            is_scg = key == "scg"
            row_f = ctk.CTkFrame(self.frame_tabela_tri,
                                  fg_color=ui.COR_REALCE if is_scg else bg, corner_radius=4)
            row_f.pack(fill="x", pady=1)

            ctk.CTkLabel(row_f, text=label,
                         font=("Roboto", 11, "bold") if is_scg else ("Roboto", 11),
                         text_color=cor, width=22 * 7, anchor="w").pack(side="left", padx=(6, 2))
            ctk.CTkLabel(row_f, text=unidade,
                         font=("Roboto", 10), text_color=COR_MUTED, width=8 * 7).pack(side="left")

            tot = 0.0
            for d in self._dados_tri:
                v = d.get(key, 0.0)
                tot += v
                cor_v = COR_VERDE if v >= 0 else COR_VERMELHO
                ctk.CTkLabel(row_f, text=_fmt(v),
                             font=("Roboto", 11, "bold") if is_scg else ("Roboto", 10),
                             text_color=cor_v if is_scg else COR_TEXTO,
                             width=14 * 7, anchor="e").pack(side="left", padx=2)

            cor_tot = COR_VERDE if tot >= 0 else COR_VERMELHO
            ctk.CTkLabel(row_f, text=_fmt(tot),
                         font=("Roboto", 11, "bold"),
                         text_color=cor_tot, width=16 * 7, anchor="e").pack(side="left", padx=(4, 6))

    # ── LÓGICA ────────────────────────────────────────────────────────────────

    @staticmethod
    def _buscar_dados_fontes(periodo: str) -> dict:
        with DatabasePMPV() as db:
            # CGR considera NF-e (compra de gás) + CT-e da TAG/Mastergás
            # (transporte via gasoduto, que a planilha oficial trata como
            # parte do CGR). CT-e das demais transportadoras é frete e não
            # integra o CGR.
            cgr = sum(float(i.get("cgr_liquido") or 0)
                      for i in (db.listar_auditoria_itens(periodo) or [])
                      if i.get("tipo") == "NF-e" or empresa_integra_cgr(i.get("empresa")))
            cons = db.buscar_consolidacao(periodo) or {}
            cgf = float(cons.get("cgf") or 0)
            ret = float(cons.get("ret") or 0)
            rp = sum(float(i.get("valor") or 0)
                     for i in (db.listar_concilia_itens(periodo) or []))
        rpv = cgr - cgf
        scg = rpv + ret + rp
        return {"cgr": cgr, "cgf": cgf, "rpv": rpv, "ret": ret, "rp": rp, "scg": scg}

    def _aplicar_dados(self, dados: dict):
        for key, linha in self.linhas.items():
            v = dados.get(key, 0.0)
            origem = "Calc" if key == "rpv" else "BD"
            linha.set_valor(v, origem)
            linha.set_entry_value(v)
        self.lbl_scg.configure(text=f"SCG =  {_fmt(dados['scg'])}")
        self.lbl_rpv_cgr.configure(text=f"CGR\n{_fmt(dados['cgr'])}")
        self.lbl_rpv_cgf.configure(text=f"CGF\n{_fmt(dados['cgf'])}")
        self.lbl_rpv_resultado.configure(text=f"RPV\n{_fmt(dados['rpv'])}")

    def _ao_mudar_periodo(self, periodo: str):
        self.periodo_atual = periodo
        if self.modo_trimestral:
            return  # trimestral não usa o combo de período
        if self.modo_manual:
            dados = self.servicos.buscar_dados_periodo(periodo) or {
                "cgr": 0.0, "cgf": 0.0, "rpv": 0.0, "ret": 0.0, "rp": 0.0, "scg": 0.0}
        else:
            dados_fontes = self._buscar_dados_fontes(periodo)
            dados_bd     = self.servicos.buscar_dados_periodo(periodo) or {}
            tem_fontes   = any(v != 0.0 for k, v in dados_fontes.items() if k != "rpv")
            dados = dados_fontes if tem_fontes else (dados_bd or dados_fontes)
        self._aplicar_dados(dados)

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

    def _salvar_manual(self):
        if not self.periodo_atual: return
        cgr = self.linhas["cgr"].get_valor_entry()
        cgf = self.linhas["cgf"].get_valor_entry()
        ret = self.linhas["ret"].get_valor_entry()
        rp  = self.linhas["rp"].get_valor_entry()
        rpv = self.servicos.salvar_valores_manuais(self.periodo_atual, cgr, cgf, ret, rp)
        self.linhas["rpv"].set_valor(rpv, "Calc")
        self.linhas["rpv"].set_entry_value(rpv)
        messagebox.showinfo("Salvo ✅",
                            f"Valores salvos para '{self.periodo_atual}'.\nRPV = {_fmt(rpv)}")

    def _calcular_scg(self):
        if self.modo_trimestral:
            # Salva cada mês individualmente e recalcula
            if not self._dados_tri:
                messagebox.showwarning("Aviso", "Carregue o trimestre primeiro.")
                return
            for d in self._dados_tri:
                mes = d["mes"]
                self.servicos.salvar_valores_manuais(mes, d["cgr"], d["cgf"], d["ret"], d["rp"])
                self.servicos.calcular_scg_oficial(mes)
            self._carregar_trimestre()
            self._atualizar_historico()
            total_scg = sum(d["scg"] for d in self._dados_tri)
            messagebox.showinfo("SCG Trimestral ✅",
                                f"SCG calculado e salvo para os 3 meses.\nTotal = {_fmt(total_scg)}")
            return

        if not self.periodo_atual: return
        if self.modo_manual: self._salvar_manual()
        dados = self.servicos.calcular_scg_oficial(self.periodo_atual)
        self._ao_mudar_periodo(self.periodo_atual)
        self._atualizar_historico()
        messagebox.showinfo("SCG Calculado ✅",
            f"Período : {self.periodo_atual}\n{'─'*38}\n"
            f"  CGR = {_fmt(dados['cgr'])}\n"
            f"  CGF = {_fmt(dados['cgf'])}\n"
            f"  RPV = {_fmt(dados['rpv'])}\n"
            f"  RET = {_fmt(dados['ret'])}\n"
            f"  RP  = {_fmt(dados['rp'])}\n{'─'*38}\n"
            f"  SCG = {_fmt(dados['scg'])}")

    def _atualizar_historico(self):
        self.hist_box.configure(state="normal")
        self.hist_box.delete("1.0", "end")
        self.hist_box.insert("end", self.servicos.gerar_texto_historico())
        self.hist_box.configure(state="disabled")

    def _adicionar_excel_final(self):
        if self.modo_trimestral and self._dados_tri:
            # Usa o último mês do trimestre como período de referência
            periodo_ref = self._dados_tri[-1]["mes"]
        elif self.periodo_atual:
            periodo_ref = self.periodo_atual
        else:
            messagebox.showwarning("Aviso", "Selecione um período antes de gerar o Excel final.")
            return

        self.servicos.calcular_scg_oficial(periodo_ref)
        meta = registrar_execucao_excel_final(etapa="SCG", periodo=periodo_ref, parent=self)
        if not meta: return
        destino, nome_sessao, periodo_norm, execucao = meta
        arquivo = ExcelConsolidado.exportar(periodo=periodo_norm, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅",
                            f"Arquivo criado:\n{arquivo}\nSessão: {nome_sessao}\n"
                            f"Período: {periodo_norm}\nExecução #{execucao}")

    def _remover_excel_final(self):
        removido, mensagem = remover_excel_final_ativo(parent=self)
        if removido: messagebox.showinfo("Excel Final", mensagem)
        else:        messagebox.showwarning("Excel Final", mensagem)
