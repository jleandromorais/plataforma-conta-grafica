from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox

from Src.Database.database import DatabasePMPV
from Src.common.excel_final_destino import registrar_execucao_excel_final, solicitar_periodo_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

BG     = "#0f172a"
CARD   = "#1e293b"
INP    = "#334155"
VERDE  = "#10b981"
VERM   = "#ef4444"
AMAR   = "#f59e0b"
AZUL   = "#3b82f6"
TEXTO  = "#f8fafc"
MUTED  = "#94a3b8"
ROXO   = "#8b5cf6"
HEADER = "#0e7490"


def _pf(val: str) -> float:
    if not val:
        return 0.0
    t = val.strip()
    ld, lc = t.rfind("."), t.rfind(",")
    if lc > ld:
        t = t.replace(".", "").replace(",", ".")
    elif ld > lc and lc >= 0:
        t = t.replace(",", "")
    else:
        if ld >= 0 and len(t[ld+1:]) == 3 and t[ld+1:].isdigit():
            t = t.replace(".", "")
    neg = t.startswith("-")
    t = "".join(c for c in t if c.isdigit() or c == ".")
    if neg:
        t = "-" + t
    try:
        return float(t)
    except ValueError:
        return 0.0


def _fv(v: float) -> str:
    s = f"{v:,.2f}"
    i, d = s.split(".")
    return f"{i.replace(',','.')},{d.rstrip('0') or '00'}"


def _fb(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


MESES_ANO = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


class _LinhasMes(ctk.CTkFrame):
    """Linha de inputs para um mês do trimestre."""

    def __init__(self, parent, mes_label: str, **kwargs):
        super().__init__(parent, fg_color=CARD, corner_radius=10, **kwargs)
        self.mes_label = mes_label
        self._build()

    def _build(self):
        # Cabeçalho do mês
        hdr = ctk.CTkFrame(self, fg_color=HEADER, corner_radius=8)
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        ctk.CTkLabel(hdr, text=f"  {self.mes_label}",
                     font=("Roboto", 13, "bold"), text_color=TEXTO).pack(
            side="left", padx=8, pady=6)

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=8, pady=(0, 8))
        for i in range(6):
            grid.columnconfigure(i, weight=1)

        def _lbl(col, txt):
            ctk.CTkLabel(grid, text=txt, font=("Roboto", 10),
                         text_color=MUTED).grid(row=0, column=col, padx=4, sticky="w")

        def _ent(col, ph="0,00", w=120):
            e = ctk.CTkEntry(grid, placeholder_text=ph,
                             font=("Roboto", 12, "bold"), height=36,
                             justify="right", fg_color=INP, text_color=TEXTO, width=w)
            e.grid(row=1, column=col, padx=4, pady=2, sticky="ew")
            return e

        _lbl(0, "VP (m³)")
        _lbl(1, "VF (m³)")
        _lbl(2, "PR (R$/m³)")
        _lbl(3, "SELIC mensal (%)")
        _lbl(4, "SR anterior (R$)")
        _lbl(5, "SR parcela (R$)")

        self.e_vp    = _ent(0)
        self.e_vf    = _ent(1)
        self.e_pr    = _ent(2, "0,0000")
        self.e_selic = _ent(3, "0,0000")
        self.e_sr_ant = _ent(4, "0,00")
        self.lbl_sr_parc = ctk.CTkLabel(
            grid, text="—", font=("Roboto", 13, "bold"),
            text_color=AMAR, width=120)
        self.lbl_sr_parc.grid(row=1, column=5, padx=4, sticky="ew")

    def get_valores(self) -> dict:
        return {
            "mes":        self.mes_label,
            "vp":         _pf(self.e_vp.get()),
            "vf":         _pf(self.e_vf.get()),
            "pr":         _pf(self.e_pr.get()),
            "selic":      _pf(self.e_selic.get()),
            "sr_anterior":_pf(self.e_sr_ant.get()),
        }

    def set_sr_parcela(self, v: float):
        cor = VERDE if v > 0 else (VERM if v < 0 else AMAR)
        self.lbl_sr_parc.configure(text=_fb(v), text_color=cor)

    def set_vp(self, v: float):
        self.e_vp.delete(0, "end")
        self.e_vp.insert(0, _fv(v))

    def set_vf(self, v: float):
        self.e_vf.delete(0, "end")
        self.e_vf.insert(0, _fv(v))


class TelaSR(ctk.CTkFrame):
    """
    SR trimestral — cálculo mês a mês com SELIC e SR anterior.

    Por mês:
        diferença  = VP − VF
        SR parcela = diferença × PR
        SR c/SELIC = SR_parcela × (1 + SELIC%) + SR_anterior

    Total = soma dos SR c/SELIC de todos os meses.
    """

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG)
        self._sessoes: list[dict] = []
        self._linhas: list[_LinhasMes] = []
        self._build_ui()
        self._carregar_sessoes()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # HEADER
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=64)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📈  SR — Saldo Remanescente Trimestral",
                     font=("Roboto", 19, "bold"), text_color=TEXTO).pack(
            side="left", padx=24, pady=16)
        ctk.CTkLabel(hdr, text="SR = (VP − VF) × PR  ×  (1 + SELIC)  +  SR anterior",
                     font=("Roboto", 12), text_color=AMAR).pack(side="right", padx=24)

        # PAINEL CARREGAR
        load = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        load.pack(fill="x", padx=20, pady=(12, 4))

        ctk.CTkLabel(load, text="📥  Carregar VP e VF do banco",
                     font=("Roboto", 13, "bold"), text_color=AZUL).pack(
            anchor="w", padx=16, pady=(10, 4))

        row1 = ctk.CTkFrame(load, fg_color="transparent")
        row1.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(row1, text="Sessão PMPV:", font=("Roboto", 11),
                     text_color=MUTED, width=100).pack(side="left")
        self.combo_sessao = ctk.CTkComboBox(
            row1, width=400, font=("Roboto", 11), state="readonly",
            values=["(nenhuma sessão)"])
        self.combo_sessao.pack(side="left", padx=(4, 10))

        ctk.CTkButton(row1, text="⚡ Carregar VP/VF", width=150, height=32,
                      font=("Roboto", 11, "bold"), fg_color=VERDE,
                      hover_color="#059669",
                      command=self._carregar_do_banco).pack(side="left", padx=(0, 6))
        ctk.CTkButton(row1, text="🔄", width=36, height=32,
                      font=("Roboto", 11), fg_color=INP,
                      command=self._carregar_sessoes).pack(side="left")

        # Seleção do trimestre SR
        row2 = ctk.CTkFrame(load, fg_color="transparent")
        row2.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(row2, text="Trimestre SR:", font=("Roboto", 11),
                     text_color=MUTED, width=100).pack(side="left")

        # Combo ano
        import datetime
        ano_atual = str(datetime.datetime.now().year)
        self.entry_ano = ctk.CTkEntry(row2, width=70, justify="center",
                                      font=("Roboto", 11))
        self.entry_ano.insert(0, ano_atual)
        self.entry_ano.pack(side="left", padx=(4, 6))

        ctk.CTkLabel(row2, text="Meses:", font=("Roboto", 11),
                     text_color=MUTED).pack(side="left", padx=(0, 4))

        self.combo_m1 = ctk.CTkComboBox(row2, values=MESES_ANO, width=80,
                                         font=("Roboto", 11), state="readonly")
        self.combo_m1.set("Jan")
        self.combo_m1.pack(side="left", padx=2)

        self.combo_m2 = ctk.CTkComboBox(row2, values=MESES_ANO, width=80,
                                         font=("Roboto", 11), state="readonly")
        self.combo_m2.set("Fev")
        self.combo_m2.pack(side="left", padx=2)

        self.combo_m3 = ctk.CTkComboBox(row2, values=MESES_ANO, width=80,
                                         font=("Roboto", 11), state="readonly")
        self.combo_m3.set("Mar")
        self.combo_m3.pack(side="left", padx=2)

        ctk.CTkButton(row2, text="Aplicar trimestre", width=130, height=30,
                      font=("Roboto", 11), fg_color=INP, hover_color=AZUL,
                      command=self._aplicar_trimestre).pack(side="left", padx=(10, 0))

        # Mês anterior ao trimestre SR (1º mês do trimestre PMPV)
        row3 = ctk.CTkFrame(load, fg_color="transparent")
        row3.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            row3,
            text="Mês anterior:",
            font=("Roboto", 11),
            text_color=AMAR,
            width=100,
        ).pack(side="left")

        self.combo_mes_ant = ctk.CTkComboBox(
            row3, values=MESES_ANO, width=80, font=("Roboto", 11), state="readonly"
        )
        self.combo_mes_ant.set("Dez")
        self.combo_mes_ant.pack(side="left", padx=2)

        self.entry_ano_ant = ctk.CTkEntry(row3, width=70, justify="center",
                                           font=("Roboto", 11))
        self.entry_ano_ant.insert(0, str(datetime.datetime.now().year - 1))
        self.entry_ano_ant.pack(side="left", padx=(2, 6))

        ctk.CTkLabel(
            row3,
            text="dias no mês:",
            font=("Roboto", 11),
            text_color=MUTED,
        ).pack(side="left", padx=(6, 2))

        self.entry_dias_ant = ctk.CTkEntry(row3, width=50, justify="center",
                                            font=("Roboto", 11))
        self.entry_dias_ant.insert(0, "31")
        self.entry_dias_ant.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            row3,
            text="⚠ 1º mês do trimestre PMPV — preencha para calcular o SR corretamente",
            font=("Roboto", 10, "italic"),
            text_color=MUTED,
        ).pack(side="left")

        # LINHAS DOS MESES (scroll)
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(4, 4))

        self._aplicar_trimestre()

        # RESULTADO TOTAL
        res = ctk.CTkFrame(self, fg_color="#1e1b4b", corner_radius=12)
        res.pack(fill="x", padx=20, pady=(0, 4))

        rrow = ctk.CTkFrame(res, fg_color="transparent")
        rrow.pack(fill="x", padx=24, pady=14)

        ctk.CTkLabel(rrow, text="SR TOTAL  =",
                     font=("Roboto", 14), text_color=MUTED).pack(side="left")
        self.lbl_total = ctk.CTkLabel(rrow, text="R$ 0,00",
                                       font=("Roboto", 26, "bold"),
                                       text_color=AMAR)
        self.lbl_total.pack(side="left", padx=16)

        self.lbl_detalhe = ctk.CTkLabel(rrow, text="",
                                         font=("Roboto", 11), text_color=MUTED)
        self.lbl_detalhe.pack(side="left")

        # BOTÕES
        brow = ctk.CTkFrame(self, fg_color="transparent")
        brow.pack(fill="x", padx=20, pady=(0, 16))

        ctk.CTkButton(brow, text="⚡ Calcular SR", width=160, height=40,
                      font=("Roboto", 13, "bold"), fg_color=VERDE,
                      hover_color="#059669",
                      command=self._calcular).pack(side="left")

        ctk.CTkButton(brow, text="💾 Salvar no BD", width=140, height=40,
                      font=("Roboto", 12, "bold"), fg_color=ROXO,
                      hover_color="#5b2c6f",
                      command=self._salvar).pack(side="left", padx=(8, 0))

        ctk.CTkButton(brow, text="➕ Excel Final (Módulo 9)", width=200, height=40,
                      font=("Roboto", 12, "bold"), fg_color="#6c3483",
                      hover_color="#884ea0",
                      command=self._adicionar_excel_final).pack(side="left", padx=(8, 0))

        ctk.CTkButton(brow, text="🗑 Limpar", width=100, height=40,
                      font=("Roboto", 12), fg_color=INP, hover_color=VERM,
                      command=self._limpar).pack(side="left", padx=(8, 0))

    # ── LÓGICA ───────────────────────────────────────────────────────────────

    def _get_trimestre_labels(self) -> list[str]:
        ano = self.entry_ano.get().strip() or "2026"
        if len(ano) == 2:
            ano = "20" + ano
        return [
            f"{self.combo_m1.get()}/{ano}",
            f"{self.combo_m2.get()}/{ano}",
            f"{self.combo_m3.get()}/{ano}",
        ]

    def _aplicar_trimestre(self):
        """Reconstrói as linhas de mês e sugere automaticamente o mês anterior."""
        for w in self.scroll.winfo_children():
            w.destroy()
        self._linhas.clear()

        for label in self._get_trimestre_labels():
            linha = _LinhasMes(self.scroll, label)
            linha.pack(fill="x", pady=4)
            for ent in (linha.e_vp, linha.e_vf, linha.e_pr,
                        linha.e_selic, linha.e_sr_ant):
                ent.bind("<KeyRelease>", lambda _e: self._calcular())
            self._linhas.append(linha)

        # Sugere o mês anterior ao 1º mês do trimestre SR
        self._sugerir_mes_anterior()

    def _sugerir_mes_anterior(self):
        """Preenche combo/ano do mês anterior com o mês que precede m1 do trimestre SR."""
        m1 = self.combo_m1.get()
        try:
            idx = MESES_ANO.index(m1)
        except ValueError:
            return
        idx_ant = (idx - 1) % 12
        mes_ant = MESES_ANO[idx_ant]
        self.combo_mes_ant.set(mes_ant)

        # Ajusta o ano: se o mês anterior for Dez e m1 for Jan, usa ano - 1
        try:
            ano_sr = int(self.entry_ano.get().strip() or "2026")
        except ValueError:
            ano_sr = 2026
        ano_ant = ano_sr - 1 if idx == 0 else ano_sr
        self.entry_ano_ant.delete(0, "end")
        self.entry_ano_ant.insert(0, str(ano_ant))

        # Dias padrão do mês anterior
        _DIAS = {"Jan": 31, "Fev": 28, "Mar": 31, "Abr": 30, "Mai": 31,
                 "Jun": 30, "Jul": 31, "Ago": 31, "Set": 30, "Out": 31,
                 "Nov": 30, "Dez": 31}
        self.entry_dias_ant.delete(0, "end")
        self.entry_dias_ant.insert(0, str(_DIAS.get(mes_ant, 30)))

    def _carregar_sessoes(self):
        db = DatabasePMPV()
        try:
            self._sessoes = db.listar_sessoes_com_volumes() or []
        finally:
            db.fechar()

        if not self._sessoes:
            self.combo_sessao.configure(values=["(nenhuma sessão)"])
            self.combo_sessao.set("(nenhuma sessão)")
            return

        labels = [
            f"{s['nome']}  —  VP: {_fv(s.get('vp',0))}  [{s.get('data_criacao','')[:10]}]"
            for s in self._sessoes
        ]
        self.combo_sessao.configure(values=labels)
        self.combo_sessao.set(labels[0])

    def _get_mes_anterior_label(self) -> str:
        """Retorna o label 'Mês/Ano' do mês anterior configurado pelo usuário."""
        ano = self.entry_ano_ant.get().strip() or "2025"
        if len(ano) == 2:
            ano = "20" + ano
        return f"{self.combo_mes_ant.get()}/{ano}"

    def _carregar_do_banco(self):
        """Preenche VP e VF nas linhas do trimestre SR.

        - Linhas 2 e 3 (índices 1 e 2): correspondem aos meses 1 e 2 da sessão
          PMPV (índices i+1 no banco). VP = soma(volume × dias).
        - Linha 1 (índice 0): corresponde ao mês anterior ao trimestre PMPV,
          informado pelo usuário. Busca VP no sr_resultados ou recalcula a partir
          dos dados_mes do período anterior; VF vem do CGF desse mês.
        """
        if not self._sessoes:
            messagebox.showinfo("Sem sessões",
                                "Nenhuma sessão PMPV encontrada.\n"
                                "Calcule e salve no módulo PMPV primeiro.")
            return

        try:
            idx = list(self.combo_sessao.cget("values")).index(
                self.combo_sessao.get())
        except ValueError:
            idx = 0
        sessao = self._sessoes[idx]
        sid = sessao["id"]

        meses_tri = self._get_trimestre_labels()   # [m1, m2, m3] do SR
        mes_ant_label = self._get_mes_anterior_label()

        try:
            dias_ant = int(self.entry_dias_ant.get().strip() or "31")
        except ValueError:
            dias_ant = 31

        # Dias padrão por mês (para os meses 2 e 3 do PMPV → linhas 1 e 2 do SR)
        _DIAS = {"Jan": 31, "Fev": 28, "Mar": 31, "Abr": 30, "Mai": 31,
                 "Jun": 30, "Jul": 31, "Ago": 31, "Set": 30, "Out": 31,
                 "Nov": 30, "Dez": 31}

        db = DatabasePMPV()
        try:
            # ── Linha 0: mês anterior (fora da sessão PMPV atual) ──────────
            linha0 = self._linhas[0]

            # VP do mês anterior: tenta sr_resultados primeiro, depois reconstrói
            sr_ant = db.buscar_sr(mes_ant_label)
            if sr_ant and sr_ant.get("vp"):
                vp0 = float(sr_ant["vp"])
            else:
                # Reconstrói a partir dos dados_mes da sessão mais recente
                # que contenha esse mês (posição 1 no banco = Mês 1 da sessão PMPV)
                dados_m0 = db.carregar_dados_mes(sid, 1) or []
                vp0 = sum(float(l.get("volume", 0) or 0) * dias_ant
                          for l in dados_m0)

            resumo0 = db.buscar_cgf_resumo(mes_ant_label)
            vf0 = float(resumo0["volume_final"]) if resumo0 and resumo0.get(
                "volume_final") is not None else 0.0

            linha0.set_vp(vp0)
            linha0.set_vf(vf0)

            # ── Linhas 1 e 2: meses 1 e 2 da sessão PMPV (índices 2 e 3) ──
            for i, linha in enumerate(self._linhas[1:], start=1):
                # Mês i da sessão PMPV corresponde ao índice i+1 no banco
                dados_mes = db.carregar_dados_mes(sid, i + 1) or []
                mes_abrev = meses_tri[i].split("/")[0]
                dias = _DIAS.get(mes_abrev, 30)
                vp = sum(float(l.get("volume", 0) or 0) * dias
                         for l in dados_mes)

                resumo = db.buscar_cgf_resumo(meses_tri[i])
                vf = float(resumo["volume_final"]) if resumo and resumo.get(
                    "volume_final") is not None else 0.0

                linha.set_vp(vp)
                linha.set_vf(vf)
        finally:
            db.fechar()

        self._calcular()

    def _calcular(self) -> list[dict] | None:
        resultados = []
        total = 0.0
        detalhes = []

        for linha in self._linhas:
            v = linha.get_valores()
            diff      = v["vp"] - v["vf"]
            sr_parc   = diff * v["pr"]
            sr_selic  = sr_parc * (1 + v["selic"] / 100) + v["sr_anterior"]
            total    += sr_selic

            linha.set_sr_parcela(sr_selic)
            detalhes.append(f"{linha.mes_label}: {_fb(sr_selic)}")
            resultados.append({
                "mes":        v["mes"],
                "vp":         v["vp"],
                "vf":         v["vf"],
                "pr":         v["pr"],
                "selic_mensal": v["selic"],
                "diferenca":  diff,
                "sr_parcela": sr_parc,
                "sr_selic":   sr_selic,
                "sr_anterior":v["sr_anterior"],
                "total":      sr_selic,
            })

        cor = VERDE if total > 0 else (VERM if total < 0 else AMAR)
        self.lbl_total.configure(text=_fb(total), text_color=cor)
        self.lbl_detalhe.configure(text="   |   ".join(detalhes))
        return resultados

    def _trimestre_label(self) -> str:
        labels = self._get_trimestre_labels()
        return f"{labels[0]}_{labels[-1]}"

    def _salvar(self):
        resultados = self._calcular()
        if not resultados:
            return
        total = sum(r["sr_selic"] for r in resultados)

        periodo = solicitar_periodo_excel_final(
            parent=self,
            titulo="Salvar SR — Período",
            mensagem="Período de referência do trimestre (ex: Mar/2026):",
            valor_inicial=self._linhas[-1].mes_label if self._linhas else "",
        )
        if not periodo:
            return

        db = DatabasePMPV()
        try:
            # Salva resumo na tabela antiga (compatibilidade com o resto)
            vp_tot = sum(r["vp"] for r in resultados)
            vf_tot = sum(r["vf"] for r in resultados)
            db.salvar_sr(periodo, vp_tot, vf_tot, 0.0, total)
            # Salva detalhe mensal
            db.salvar_sr_trimestre(self._trimestre_label(), resultados)
        finally:
            db.fechar()

        messagebox.showinfo("Salvo ✅",
                            f"SR trimestral salvo.\nTotal = {_fb(total)}")

    def _limpar(self):
        self._aplicar_trimestre()
        self.lbl_total.configure(text="R$ 0,00", text_color=AMAR)
        self.lbl_detalhe.configure(text="")

    def _adicionar_excel_final(self):
        resultados = self._calcular()
        if not resultados or all(r["vp"] == 0 and r["vf"] == 0 for r in resultados):
            messagebox.showwarning("Aviso",
                                   "Preencha os dados antes de adicionar ao Excel.")
            return

        periodo = solicitar_periodo_excel_final(
            parent=self,
            titulo="Excel Final (Módulo 9) — SR",
            mensagem="Período de referência (ex: Mar/2026):",
            valor_inicial=self._linhas[-1].mes_label if self._linhas else "",
        )
        if not periodo:
            return

        total = sum(r["sr_selic"] for r in resultados)
        vp_tot = sum(r["vp"] for r in resultados)
        vf_tot = sum(r["vf"] for r in resultados)

        db = DatabasePMPV()
        try:
            db.salvar_sr(periodo, vp_tot, vf_tot, 0.0, total)
            db.salvar_sr_trimestre(self._trimestre_label(), resultados)
        finally:
            db.fechar()

        meta = registrar_execucao_excel_final(etapa="SR", periodo=periodo, parent=self)
        if not meta:
            return
        destino, _, periodo_norm, execucao = meta
        arquivo = ExcelConsolidado.exportar(periodo=periodo_norm, nome_arquivo=destino)
        messagebox.showinfo("Excel Final ✅",
                            f"SR adicionado.\nArquivo: {arquivo}\nExecução #{execucao}")


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste SR")
    root.geometry("1100x800")
    TelaSR(root).pack(fill="both", expand=True)
    root.mainloop()
