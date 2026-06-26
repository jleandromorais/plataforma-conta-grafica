from __future__ import annotations

import customtkinter as ctk
from tkinter import messagebox, simpledialog

from Src.config import ui_theme as ui
from Src.Services.servicos_pr import ServicosPR
from Src.Database.database import DatabasePMPV
from Src.common.excel_final_destino import registrar_execucao_excel_final
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# ── Paleta (aliases do design system central — ver Src/config/ui_theme.py) ─────
BG       = ui.COR_FUNDO
CARD     = ui.COR_CARD
INPUT_BG = ui.COR_INPUT
VERDE    = ui.COR_SUCESSO
AZUL     = ui.COR_PRIMARIA
VERMELHO = ui.COR_PERIGO
AMARELO  = ui.COR_DESTAQUE
ROXO     = ui.COR_ROXO
TEXTO    = ui.COR_TEXTO
MUTED    = ui.COR_MUTED
LARANJA  = "#f97316"

MESES_ANO = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _fmt2(v: float) -> str:
    return f"{(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _parse(txt: str) -> float:
    t = txt.strip().replace("R$", "").replace(" ", "").replace("m³", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


class _EntradaSR(ctk.CTkFrame):
    """Linha para um SR anterior: label + entry."""

    def __init__(self, parent, label: str, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        ctk.CTkLabel(self, text=label, font=("Roboto", 11),
                     text_color=MUTED, width=260, anchor="w").pack(side="left")
        self.entry = ctk.CTkEntry(self, placeholder_text="0,00",
                                   font=("Roboto", 12, "bold"), height=34,
                                   justify="right", fg_color=INPUT_BG,
                                   text_color=TEXTO, width=200)
        self.entry.pack(side="left", padx=(8, 0))

    def get(self) -> float:
        return _parse(self.entry.get())

    def set(self, v: float):
        self.entry.delete(0, "end")
        self.entry.insert(0, _fmt2(v))

    def bind_recalc(self, cb):
        self.entry.bind("<KeyRelease>", lambda _e: cb())


class TelaPR(ctk.CTkFrame):
    """
    PR = (SCG + ΣSR) / VP

    SCG  = saldo da conta gráfica (com SELIC) do trimestre atual
    ΣSR  = soma dos saldos remanescentes: SR atual + SRs de trimestres anteriores
    VP   = volume prospectivo total do trimestre
    """

    # Número de linhas de SR anteriores oferecidas ao usuário
    _N_SR_ANT = 4

    def __init__(self, parent=None):
        super().__init__(parent, fg_color=BG)
        self.servicos = ServicosPR()
        self._sr_entries: list[_EntradaSR] = []
        self._build_ui()
        self._carregar_periodos()

    # ── CONSTRUÇÃO DA UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        # HEADER
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=70)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="💡  PR — Parcela de Recuperação",
                     font=("Roboto", 20, "bold"), text_color=TEXTO).pack(
            side="left", padx=24, pady=20)
        ctk.CTkLabel(hdr, text="PR  =  (SCG + ΣSR)  /  VP",
                     font=("Roboto", 13, "bold"), text_color=AMARELO).pack(
            side="right", padx=24)

        # SELEÇÃO DO TRIMESTRE
        trim_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        trim_frame.pack(fill="x", pady=(2, 0))

        row1 = ctk.CTkFrame(trim_frame, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(10, 4))

        ctk.CTkLabel(row1, text="Trimestre:", font=("Roboto", 12, "bold"),
                     text_color=MUTED).pack(side="left", padx=(0, 16))

        self.combo_m1 = ctk.CTkComboBox(row1, width=150, font=("Roboto", 11))
        self.combo_m2 = ctk.CTkComboBox(row1, width=150, font=("Roboto", 11))
        self.combo_m3 = ctk.CTkComboBox(row1, width=150, font=("Roboto", 11))
        for label, combo in [("Mês 1:", self.combo_m1), ("Mês 2:", self.combo_m2),
                              ("Mês 3:", self.combo_m3)]:
            ctk.CTkLabel(row1, text=label, font=("Roboto", 11),
                         text_color=MUTED).pack(side="left", padx=(8, 4))
            combo.pack(side="left", padx=(0, 4))

        row2 = ctk.CTkFrame(trim_frame, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkButton(row2, text="⚡ Carregar Trimestre do Banco",
                      width=240, height=32, font=("Roboto", 11, "bold"),
                      fg_color=VERDE, hover_color="#059669",
                      command=self._carregar_trimestre).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row2, text="🗑 Limpar", width=80, height=32,
                      font=("Roboto", 11), fg_color=INPUT_BG, hover_color=VERMELHO,
                      command=self._limpar_campos).pack(side="left")

        # SCROLL com todos os inputs
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=(10, 0))

        # ── Bloco SCG ────────────────────────────────────────────────────────
        bloco_scg = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=12)
        bloco_scg.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(bloco_scg, text="💼  SCG — Saldo da Conta Gráfica (com SELIC)",
                     font=("Roboto", 13, "bold"), text_color=ROXO).pack(
            anchor="w", padx=16, pady=(12, 6))

        row_scg = ctk.CTkFrame(bloco_scg, fg_color="transparent")
        row_scg.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row_scg, text="SCG (R$):", font=("Roboto", 11),
                     text_color=MUTED, width=260, anchor="w").pack(side="left")
        self.entry_scg = ctk.CTkEntry(row_scg, placeholder_text="0,00",
                                       font=("Roboto", 14, "bold"), height=40,
                                       justify="right", fg_color=INPUT_BG,
                                       text_color=TEXTO, border_color=ROXO,
                                       border_width=2, width=200)
        self.entry_scg.pack(side="left", padx=(8, 0))
        self.entry_scg.bind("<KeyRelease>", lambda _e: self._recalcular())

        # ── Bloco ΣSR ────────────────────────────────────────────────────────
        bloco_sr = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=12)
        bloco_sr.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(bloco_sr,
                     text="📈  ΣSR — Saldos Remanescentes (atual + anteriores)",
                     font=("Roboto", 13, "bold"), text_color=VERDE).pack(
            anchor="w", padx=16, pady=(12, 6))

        # SR do trimestre atual
        sr_atual = _EntradaSR(bloco_sr, "SR atual (trimestre em cálculo)  R$:")
        sr_atual.pack(fill="x", padx=16, pady=(0, 4))
        sr_atual.bind_recalc(self._recalcular)
        self.entry_sr_atual = sr_atual

        # SRs anteriores (dinâmicos)
        self._sr_entries.clear()
        rotulos = [
            "2º SR anterior (ex: NOV/25–JAN/26)  R$:",
            "1º SR anterior — mês 1 (ex: FEV/26)  R$:",
            "1º SR anterior — mês 2 (ex: MAR/26)  R$:",
            "SR adicional  R$:",
        ]
        for i in range(self._N_SR_ANT):
            e = _EntradaSR(bloco_sr, rotulos[i] if i < len(rotulos) else f"SR extra {i+1}  R$:")
            e.pack(fill="x", padx=16, pady=(0, 4))
            e.bind_recalc(self._recalcular)
            self._sr_entries.append(e)

        # Label saldo total a recuperar
        self.lbl_saldo_total = ctk.CTkLabel(
            bloco_sr, text="Saldo Total a Recuperar:  R$ 0,00",
            font=("Roboto", 12, "bold"), text_color=AMARELO)
        self.lbl_saldo_total.pack(anchor="e", padx=16, pady=(6, 12))

        # ── Bloco VP ────────────────────────────────────────────────────────
        bloco_vp = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=12)
        bloco_vp.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(bloco_vp, text="🔢  VP — Volume Prospectivo Contratado",
                     font=("Roboto", 13, "bold"), text_color=AZUL).pack(
            anchor="w", padx=16, pady=(12, 6))

        row_vp = ctk.CTkFrame(bloco_vp, fg_color="transparent")
        row_vp.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(row_vp, text="VP (m³):", font=("Roboto", 11),
                     text_color=MUTED, width=260, anchor="w").pack(side="left")
        self.entry_vp = ctk.CTkEntry(row_vp, placeholder_text="0,00",
                                      font=("Roboto", 14, "bold"), height=40,
                                      justify="right", fg_color=INPUT_BG,
                                      text_color=TEXTO, border_color=AZUL,
                                      border_width=2, width=200)
        self.entry_vp.pack(side="left", padx=(8, 0))
        self.entry_vp.bind("<KeyRelease>", lambda _e: self._recalcular())

        # ── RESULTADO PR ─────────────────────────────────────────────────────
        res_card = ctk.CTkFrame(scroll, fg_color=ui.COR_REALCE, corner_radius=14)
        res_card.pack(fill="x", pady=(0, 8))

        row_res = ctk.CTkFrame(res_card, fg_color="transparent")
        row_res.pack(fill="x", padx=24, pady=18)

        ctk.CTkLabel(row_res, text="PR  =  (SCG + ΣSR)  /  VP  =",
                     font=("Roboto", 13), text_color=MUTED).pack(side="left")
        self.lbl_pr = ctk.CTkLabel(row_res, text="R$ 0,0000",
                                    font=("Roboto", 26, "bold"), text_color=AMARELO)
        self.lbl_pr.pack(side="left", padx=16)
        self.lbl_aviso = ctk.CTkLabel(row_res, text="",
                                       font=("Roboto", 12, "italic"),
                                       text_color=MUTED, width=240)
        self.lbl_aviso.pack(side="left")

        # ── BOTÕES ───────────────────────────────────────────────────────────
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 8))

        ctk.CTkButton(btn_row, text="💾  Salvar PR no banco",
                      font=("Roboto", 13, "bold"), height=44, width=220,
                      fg_color=ROXO, hover_color="#7c3aed",
                      command=self._salvar_pr).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_row, text="➕  Excel Final (Módulo 9)",
                      font=("Roboto", 12, "bold"), height=44, width=220,
                      fg_color="#6c3483", hover_color="#884ea0",
                      command=self._adicionar_excel_final).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btn_row, text="🔄  Atualizar histórico",
                      font=("Roboto", 12), height=44, width=170,
                      fg_color=INPUT_BG, hover_color=AZUL,
                      command=self._atualizar_historico).pack(side="left")

        # ── DETALHAMENTO TRIMESTRAL (SCG + SR por mês / VP) ──────────────────
        det_card = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=12)
        det_card.pack(fill="x", pady=(0, 8))

        ctk.CTkLabel(det_card,
                     text="📊  Decomposição Trimestral  —  PR = Σ (SCG_m + SR_m) / VP_m",
                     font=("Roboto", 12, "bold"), text_color=AZUL).pack(
            anchor="w", padx=16, pady=(10, 4))

        self.det_box = ctk.CTkTextbox(det_card, font=("Consolas", 11),
                                       fg_color=BG, text_color=TEXTO, height=110)
        self.det_box.pack(fill="x", padx=14, pady=(0, 10))
        self.det_box.configure(state="disabled")

        # ── HISTÓRICO ────────────────────────────────────────────────────────
        hist = ctk.CTkFrame(scroll, fg_color=CARD, corner_radius=12)
        hist.pack(fill="x", pady=(0, 20))

        ctk.CTkLabel(hist, text="📅  Histórico de PR por período",
                     font=("Roboto", 13, "bold"), text_color=MUTED).pack(
            anchor="w", padx=20, pady=(14, 4))
        self.hist_box = ctk.CTkTextbox(hist, font=("Consolas", 11),
                                        fg_color=BG, text_color=MUTED, height=140)
        self.hist_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    # ── LÓGICA ────────────────────────────────────────────────────────────────

    def _carregar_periodos(self):
        periodos = self.servicos.obter_todos_periodos()
        valores = periodos if periodos else [""]
        for combo in (self.combo_m1, self.combo_m2, self.combo_m3):
            combo.configure(values=valores)
        if len(periodos) >= 3:
            self.combo_m1.set(periodos[0])
            self.combo_m2.set(periodos[1])
            self.combo_m3.set(periodos[2])
        elif periodos:
            for combo in (self.combo_m1, self.combo_m2, self.combo_m3):
                combo.set(periodos[0])
        self._atualizar_historico()

    def _gerar_nome_trimestre(self) -> str:
        m1 = self.combo_m1.get().strip()
        m3 = self.combo_m3.get().strip()
        if m1 and m3 and m1 != m3:
            return f"{m1} – {m3}"
        return m1 or m3 or ""

    def _soma_sr(self) -> float:
        total = self.entry_sr_atual.get()
        for e in self._sr_entries:
            total += e.get()
        return total

    def _recalcular(self):
        scg    = _parse(self.entry_scg.get())
        sr_tot = self._soma_sr()
        vp     = _parse(self.entry_vp.get())
        saldo  = scg + sr_tot
        pr     = ServicosPR.calcular_pr(scg, sr_tot, vp)

        self.lbl_saldo_total.configure(
            text=f"Saldo Total a Recuperar:  {ServicosPR.formatar_brl(saldo)}",
            text_color=VERDE if saldo >= 0 else VERMELHO)
        self.lbl_pr.configure(text=ServicosPR.formatar_pr(pr))

        if vp == 0:
            self.lbl_pr.configure(text_color=AMARELO)
            self.lbl_aviso.configure(text="⚠ VP = 0 → PR = 0", text_color=AMARELO)
        elif pr > 0:
            self.lbl_pr.configure(text_color=VERDE)
            self.lbl_aviso.configure(text="▲ Resultado positivo", text_color=VERDE)
        else:
            self.lbl_pr.configure(text_color=VERMELHO)
            self.lbl_aviso.configure(text="▼ Resultado negativo", text_color=VERMELHO)

    def _atualizar_det_box(self, meses: list[dict], pr_final: float):
        """Preenche o textbox de decomposição trimestral."""
        linhas = [
            f"{'Período':<14} {'SCG (R$)':>18} {'SR (R$)':>18} {'VP (m³)':>14} {'Parcela PR':>14}",
            "─" * 82,
        ]
        for m in meses:
            parcela = m["parcela_pr"]
            linhas.append(
                f"{m['periodo']:<14} "
                f"{ServicosPR.formatar_brl(m['scg']):>18} "
                f"{ServicosPR.formatar_brl(m['sr']):>18} "
                f"{ServicosPR.formatar_volume(m['vp']):>14} "
                f"{ServicosPR.formatar_pr(parcela):>14}"
            )
        linhas.append("─" * 82)
        linhas.append(f"{'PR TRIMESTRAL':>64}  {ServicosPR.formatar_pr(pr_final):>14}")

        self.det_box.configure(state="normal")
        self.det_box.delete("1.0", "end")
        self.det_box.insert("end", "\n".join(linhas))
        self.det_box.configure(state="disabled")

    def _carregar_trimestre(self):
        m1 = self.combo_m1.get().strip()
        m2 = self.combo_m2.get().strip()
        m3 = self.combo_m3.get().strip()
        periodos = [p for p in (m1, m2, m3) if p]
        if not periodos:
            messagebox.showwarning("Aviso", "Selecione ao menos um mês.")
            return

        # PR = Σ (SCG_m + SR_m) / VP_m  (fórmula normalizada por mês)
        dados = self.servicos.buscar_dados_trimestral(periodos)

        # Preenche campos com os totais
        self.entry_scg.delete(0, "end")
        self.entry_scg.insert(0, _fmt2(dados["scg"]))
        self.entry_vp.delete(0, "end")
        self.entry_vp.insert(0, _fmt2(dados["vp"]))

        # SR atual = soma dos SRs dos meses do trimestre
        self.entry_sr_atual.set(dados["sr"])

        # Tenta preencher SRs anteriores do banco (trimestres passados)
        db = DatabasePMPV()
        try:
            sr_anteriores = db.listar_sr()
            sr_anteriores = [
                r for r in sr_anteriores
                if r.get("periodo") not in periodos
            ]
        finally:
            db.fechar()

        for i, e in enumerate(self._sr_entries):
            if i < len(sr_anteriores):
                e.set(float(sr_anteriores[i].get("sr") or 0))
            else:
                e.set(0.0)

        # Mostra decomposição mês a mês e atualiza PR com valor normalizado
        self._atualizar_det_box(dados.get("meses", []), dados["pr"])

        # Exibe o PR já calculado pela fórmula normalizada
        self.lbl_pr.configure(
            text=ServicosPR.formatar_pr(dados["pr"]),
            text_color=VERDE if dados["pr"] > 0 else (VERMELHO if dados["pr"] < 0 else AMARELO))
        saldo = dados["scg"] + dados["sr"] + sum(e.get() for e in self._sr_entries)
        self.lbl_saldo_total.configure(
            text=f"Saldo Total a Recuperar:  {ServicosPR.formatar_brl(saldo)}",
            text_color=VERDE if saldo >= 0 else VERMELHO)
        self.lbl_aviso.configure(
            text=f"Trimestre: {self._gerar_nome_trimestre()}",
            text_color=AZUL)

        if dados["scg"] == 0 and dados["sr"] == 0 and dados["vp"] == 0:
            messagebox.showinfo("Sem dados",
                                "Nenhum valor encontrado no banco para os meses selecionados.\n"
                                "Execute SCG e SR e salve no banco primeiro.")
            return

        # Auto-save silencioso: persiste o PR trimestral calculado
        nome_tri = self._gerar_nome_trimestre()
        if nome_tri:
            try:
                self.servicos.salvar_valores(nome_tri, dados["scg"], dados["sr"], dados["vp"])
                self._atualizar_historico()
            except Exception:
                pass

    def _limpar_campos(self):
        self.entry_scg.delete(0, "end")
        self.entry_sr_atual.set(0.0)
        for e in self._sr_entries:
            e.set(0.0)
        self.entry_vp.delete(0, "end")
        self.lbl_pr.configure(text="R$ 0,0000", text_color=AMARELO)
        self.lbl_aviso.configure(text="")
        self.lbl_saldo_total.configure(
            text="Saldo Total a Recuperar:  R$ 0,00", text_color=AMARELO)

    def _salvar_pr(self):
        scg    = _parse(self.entry_scg.get())
        sr_tot = self._soma_sr()
        vp     = _parse(self.entry_vp.get())

        if scg == 0 and sr_tot == 0 and vp == 0:
            messagebox.showwarning("Aviso", "Preencha ao menos um dos valores.")
            return

        nome_sugerido = self._gerar_nome_trimestre()
        periodo = simpledialog.askstring(
            "Nome do trimestre",
            "Nome para salvar este trimestre\n(ex: T1/2026  ou  Nov/2025 – Jan/2026):",
            initialvalue=nome_sugerido, parent=self)
        if not periodo or not periodo.strip():
            return

        periodo = periodo.strip()
        pr = self.servicos.salvar_valores(periodo, scg, sr_tot, vp)

        self._recalcular()
        self._atualizar_historico()

        messagebox.showinfo("Salvo ✅",
            f"Trimestre : {periodo}\n{'─'*34}\n"
            f"  SCG          = {ServicosPR.formatar_brl(scg)}\n"
            f"  SR atual     = {ServicosPR.formatar_brl(self.entry_sr_atual.get())}\n"
            f"  SRs anteriores = {ServicosPR.formatar_brl(sum(e.get() for e in self._sr_entries))}\n"
            f"  ΣSR total    = {ServicosPR.formatar_brl(sr_tot)}\n"
            f"  Saldo total  = {ServicosPR.formatar_brl(scg + sr_tot)}\n"
            f"  VP           = {ServicosPR.formatar_volume(vp)}\n"
            f"{'─'*34}\n"
            f"  PR           = {ServicosPR.formatar_pr(pr)}")

    def _atualizar_historico(self):
        self.hist_box.configure(state="normal")
        self.hist_box.delete("1.0", "end")
        self.hist_box.insert("end", self.servicos.gerar_texto_historico())
        self.hist_box.configure(state="disabled")

    def _adicionar_excel_final(self):
        scg    = _parse(self.entry_scg.get())
        sr_tot = self._soma_sr()
        vp     = _parse(self.entry_vp.get())

        if scg == 0 and sr_tot == 0 and vp == 0:
            messagebox.showwarning("Aviso", "Carregue o trimestre antes de adicionar ao Excel final.")
            return

        nome_sugerido = self._gerar_nome_trimestre()
        periodo = simpledialog.askstring(
            "Nome do trimestre",
            "Nome do trimestre para o Excel final:",
            initialvalue=nome_sugerido, parent=self)
        if not periodo or not periodo.strip():
            return
        periodo = periodo.strip()

        self.servicos.salvar_valores(periodo, scg, sr_tot, vp)
        meta = registrar_execucao_excel_final(etapa="PR", periodo=periodo, parent=self)
        if not meta:
            return
        destino, nome_sessao, periodo_norm, execucao = meta
        arquivo = ExcelConsolidado.exportar(periodo=periodo_norm, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅",
            f"Arquivo criado:\n{arquivo}\nSessão: {nome_sessao}\n"
            f"Período: {periodo_norm}\nExecução #{execucao}")


if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Teste TelaPR")
    root.geometry("1000x850")
    TelaPR(root).pack(fill="both", expand=True)
    root.mainloop()
