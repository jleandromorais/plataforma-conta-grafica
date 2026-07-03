from __future__ import annotations

import re
import tkinter as tk

import customtkinter as ctk

from Src.config import ui_theme as ui
from Src.Database.database import DatabasePMPV
from Src.common.formatting import format_brl, format_brl4, format_brl_compacto

try:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _MPL = True
except ImportError:
    _MPL = False

# ── Paleta local ──────────────────────────────────────────────────────────────
_CARD    = ui.COR_CARD
_CARD2   = ui.COR_CARD_ALT
_FUNDO   = ui.COR_FUNDO
_INPUT   = ui.COR_INPUT
_TEXTO   = ui.COR_TEXTO
_MUTED   = ui.COR_MUTED
_AZUL    = ui.COR_PRIMARIA
_VERDE   = ui.COR_SUCESSO
_VERM    = ui.COR_PERIGO
_AMAR    = ui.COR_DESTAQUE
_ROXO    = ui.COR_ROXO

# Cores de módulo (iguais ao sidebar)
_COR_M1  = "#2980b9"   # PMPV
_COR_M2  = "#16a085"   # Cálculos mensais
_COR_M3  = "#8e44ad"   # Consolidação trimestral

_MESES_ORDEM = {m: i for i, m in enumerate(
    ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
     "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
)}
_MESES_FULL = {
    "Jan": "Janeiro",  "Fev": "Fevereiro", "Mar": "Março",
    "Abr": "Abril",    "Mai": "Maio",       "Jun": "Junho",
    "Jul": "Julho",    "Ago": "Agosto",     "Set": "Setembro",
    "Out": "Outubro",  "Nov": "Novembro",   "Dez": "Dezembro",
}
_PERIODO_VALIDO = re.compile(
    r"^(" + "|".join(_MESES_ORDEM) + r")/(\d{4})$"
)
TODOS_OS_ANOS = "Todos os anos"


def _chave(p: str) -> tuple[int, int]:
    m = _PERIODO_VALIDO.match(p)
    mes, ano = m.groups()
    return (int(ano), _MESES_ORDEM[mes])


_brl = format_brl
_brl_compacto = format_brl_compacto
_pmpv_fmt = format_brl4


def _pct(v: float) -> str:
    return f"{v:+.1f}%".replace(".", ",")


def _mes_full(periodo: str) -> str:
    ab = periodo.split("/")[0] if "/" in periodo else periodo[:3]
    return _MESES_FULL.get(ab, ab)


# ══════════════════════════════════════════════════════════════════════════════

class PainelResumo(ctk.CTkFrame):
    """Dashboard principal: KPIs, painel trimestral e gráficos."""

    def __init__(self, parent=None):
        super().__init__(parent, fg_color="transparent")
        self._consolidacoes: list[dict] = []
        self._pmpvs: list[dict] = []
        # widgets que serão atualizados
        self._kpi_widgets: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        self._build_ui()
        self._carregar_banco()
        self._atualizar()

    # ── CONSTRUÇÃO DA UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Topo: título + filtro de ano ──────────────────────────────────────
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=4, pady=(0, 4))

        ctk.CTkLabel(
            topo, text="📊  Dashboard",
            font=ctk.CTkFont(size=17, weight="bold"), text_color=_TEXTO,
        ).pack(side="left")

        ctk.CTkLabel(topo, text="Ano:", font=ctk.CTkFont(size=12),
                     text_color=_MUTED).pack(side="right", padx=(0, 6))
        self.combo_ano = ctk.CTkComboBox(
            topo, width=150, font=ctk.CTkFont(size=12),
            values=[TODOS_OS_ANOS], command=lambda _: self._atualizar(),
        )
        self.combo_ano.set(TODOS_OS_ANOS)
        self.combo_ano.pack(side="right")
        ctk.CTkButton(
            topo, text="🔄", width=36, height=28,
            font=ctk.CTkFont(size=14), fg_color=_INPUT,
            hover_color=_AZUL, command=self._recarregar,
        ).pack(side="right", padx=(0, 8))

        self.lbl_periodo = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=12), text_color=_MUTED,
        )
        self.lbl_periodo.pack(anchor="w", padx=4, pady=(0, 6))

        # ── Seção 1: KPIs do último mês ───────────────────────────────────────
        self._secao("ÚLTIMO MÊS", _COR_M2)
        grade = ctk.CTkFrame(self, fg_color="transparent")
        grade.pack(fill="x", padx=4, pady=(0, 2))
        campos = [
            ("cgr", "CGR",  "🔍", _COR_M2),
            ("ret", "RET",  "⚡", _COR_M2),
            ("cgf", "CGF",  "📋", _COR_M2),
            ("rp",  "RP",   "📄", _COR_M2),
            ("rpv", "RPV",  "🧾", _COR_M2),
            ("scg", "SCG",  "💼", _COR_M3),
        ]
        for col in range(6):
            grade.grid_columnconfigure(col, weight=1, uniform="kpi")
        for i, (chave, titulo, icon, cor) in enumerate(campos):
            self._kpi_widgets[chave] = self._kpi_card(grade, icon, titulo, cor, i)

        # ── Seção 2: Gráficos ─────────────────────────────────────────────────
        self._secao("EVOLUÇÃO HISTÓRICA", _COR_M1)
        linha_graficos = ctk.CTkFrame(self, fg_color="transparent")
        linha_graficos.pack(fill="x", padx=4, pady=(0, 2))
        linha_graficos.grid_columnconfigure(0, weight=1, uniform="g")
        linha_graficos.grid_columnconfigure(1, weight=1, uniform="g")

        bloco_pmpv = ctk.CTkFrame(linha_graficos, fg_color="transparent")
        bloco_pmpv.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        ctk.CTkLabel(bloco_pmpv, text="📈  PMPV mensal (R$/m³)",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=_TEXTO).pack(anchor="w", pady=(0, 4))
        self.frame_gr_pmpv = ctk.CTkFrame(bloco_pmpv, fg_color=_CARD, corner_radius=10)
        self.frame_gr_pmpv.pack(fill="both", expand=True)

        bloco_scg = ctk.CTkFrame(linha_graficos, fg_color="transparent")
        bloco_scg.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        ctk.CTkLabel(bloco_scg, text="💼  SCG mensal",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=_TEXTO).pack(anchor="w", pady=(0, 4))
        self.frame_gr_scg = ctk.CTkFrame(bloco_scg, fg_color=_CARD, corner_radius=10)
        self.frame_gr_scg.pack(fill="both", expand=True)

        # Gráfico CGR vs CGF
        ctk.CTkLabel(self, text="📊  CGR vs CGF por período",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=_TEXTO).pack(anchor="w", padx=4, pady=(8, 4))
        self.frame_gr_cgrcgf = ctk.CTkFrame(self, fg_color=_CARD, corner_radius=10)
        self.frame_gr_cgrcgf.pack(fill="x", padx=4)

    def _secao(self, titulo: str, cor: str):
        """Faixa separadora de seção com título."""
        f = ctk.CTkFrame(self, fg_color=cor, corner_radius=6, height=28)
        f.pack(fill="x", padx=4, pady=(10, 6))
        f.pack_propagate(False)
        ctk.CTkLabel(f, text=f"  {titulo}",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="white").pack(side="left", padx=6)

    def _kpi_card(self, parent, icon: str, titulo: str, cor: str,
                  col: int) -> tuple[ctk.CTkLabel, ctk.CTkLabel]:
        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=10)
        card.grid(row=0, column=col, padx=5, pady=4, sticky="nsew")

        # tarja colorida no topo
        tarja = ctk.CTkFrame(card, fg_color=cor, corner_radius=0, height=3)
        tarja.pack(fill="x")

        ctk.CTkLabel(card, text=f"{icon} {titulo}",
                     font=ctk.CTkFont(size=11), text_color=_MUTED,
                     ).pack(anchor="w", padx=10, pady=(8, 0))
        lbl_val = ctk.CTkLabel(card, text="—",
                               font=ctk.CTkFont(size=14, weight="bold"),
                               text_color=cor)
        lbl_val.pack(anchor="w", padx=10)
        lbl_var = ctk.CTkLabel(card, text="",
                               font=ctk.CTkFont(size=10), text_color=_MUTED)
        lbl_var.pack(anchor="w", padx=10, pady=(0, 8))
        return lbl_val, lbl_var

    # ── DADOS ─────────────────────────────────────────────────────────────────

    def _carregar_banco(self):
        with DatabasePMPV() as db:
            cons  = db.listar_consolidacao_completa()
            pmpvs = db.listar_pmpv_mensal()

        self._consolidacoes = sorted(
            [c for c in cons if _PERIODO_VALIDO.match(c.get("periodo", ""))],
            key=lambda c: _chave(c["periodo"]),
        )
        self._pmpvs = sorted(
            [p for p in pmpvs if _PERIODO_VALIDO.match(p.get("periodo", ""))],
            key=lambda p: _chave(p["periodo"]),
        )

        anos = sorted(
            {_chave(c["periodo"])[0] for c in self._consolidacoes} |
            {_chave(p["periodo"])[0] for p in self._pmpvs},
            reverse=True,
        )
        vals = [TODOS_OS_ANOS] + [str(a) for a in anos]
        self.combo_ano.configure(values=vals)
        if self.combo_ano.get() not in vals:
            self.combo_ano.set(TODOS_OS_ANOS)

    def _recarregar(self):
        self._carregar_banco()
        self._atualizar()

    def _filtrar(self, itens: list[dict]) -> list[dict]:
        ano = self.combo_ano.get()
        if ano == TODOS_OS_ANOS:
            return itens
        return [i for i in itens if _chave(i["periodo"])[0] == int(ano)]

    # ── ATUALIZAÇÃO GERAL ─────────────────────────────────────────────────────

    def _atualizar(self):
        cons  = self._filtrar(self._consolidacoes)
        pmpvs = self._filtrar(self._pmpvs)

        self._atualizar_kpis(cons)
        self._grafico_linha(self.frame_gr_pmpv, pmpvs,  "pmpv", _pmpv_fmt, _COR_M1)
        self._grafico_linha(self.frame_gr_scg,  cons,   "scg",  _brl_compacto, _COR_M3, linha_zero=True)
        self._grafico_barras(cons)

    # ── KPIs ÚLTIMO MÊS ──────────────────────────────────────────────────────

    def _atualizar_kpis(self, cons: list[dict]):
        atual    = cons[-1] if cons else None
        anterior = cons[-2] if len(cons) >= 2 else None

        if atual:
            self.lbl_periodo.configure(
                text=f"Período mais recente: {atual['periodo']}"
            )
        else:
            self.lbl_periodo.configure(text="Nenhum período calculado ainda.")
            for chave in self._kpi_widgets:
                lv, lvar = self._kpi_widgets[chave]
                lv.configure(text="—"); lvar.configure(text="")
            return

        for chave, (lv, lvar) in self._kpi_widgets.items():
            v_atual = float(atual.get(chave) or 0)
            lv.configure(text=_brl(v_atual))
            if anterior:
                v_ant = float(anterior.get(chave) or 0)
                if v_ant != 0:
                    var = (v_atual - v_ant) / abs(v_ant) * 100
                    seta = "▲" if var >= 0 else "▼"
                    cor  = _VERDE if var >= 0 else _VERM
                    lvar.configure(
                        text=f"{seta} {_pct(var)} vs {anterior['periodo']}",
                        text_color=cor,
                    )
                    continue
            lvar.configure(text="")

    # ── GRÁFICO DE LINHA ─────────────────────────────────────────────────────

    def _grafico_linha(self, frame: ctk.CTkFrame, itens: list[dict],
                       chave: str, fmt, cor: str, linha_zero: bool = False):
        for w in frame.winfo_children():
            w.destroy()

        if not itens:
            ctk.CTkLabel(frame, text="Sem dados.",
                         font=ctk.CTkFont(size=12), text_color=_MUTED,
                         ).pack(padx=14, pady=30)
            return

        if not _MPL:
            self._tabela_fallback(frame, itens, chave, fmt, cor)
            return

        labels  = [i["periodo"] for i in itens]
        valores = [float(i.get(chave) or 0) for i in itens]

        fig = Figure(figsize=(5, 2.5), dpi=100, facecolor=_CARD)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_CARD)

        if linha_zero:
            ax.axhline(0, color=_MUTED, linewidth=0.8, linestyle="--")
            cores_pts = [_VERDE if v >= 0 else _VERM for v in valores]
            for i, (x, y) in enumerate(zip(range(len(labels)), valores)):
                ax.bar(x, y, color=cores_pts[i], alpha=0.25, width=0.6)
            linha_plt, = ax.plot(range(len(labels)), valores, marker="o",
                                 color=cor, linewidth=2)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=30, fontsize=8)
        else:
            linha_plt, = ax.plot(labels, valores, marker="o", color=cor, linewidth=2)

        for spine in ax.spines.values():
            spine.set_color(_MUTED)
        ax.tick_params(axis="x", colors=_MUTED, labelrotation=30, labelsize=8)
        ax.tick_params(axis="y", colors=_MUTED, labelsize=8)
        ax.yaxis.set_major_formatter(lambda v, _: fmt(v))
        ax.grid(True, color=_CARD2, linewidth=0.5)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        anot = ax.annotate("", xy=(0, 0), xytext=(12, 12),
                           textcoords="offset points",
                           bbox=dict(boxstyle="round,pad=0.4", fc=_INPUT, ec=_MUTED),
                           color=_TEXTO, fontsize=9)
        anot.set_visible(False)

        def _hover(event):
            if event.inaxes != ax:
                if anot.get_visible():
                    anot.set_visible(False); canvas.draw_idle()
                return
            cont, info = linha_plt.contains(event)
            if cont and info["ind"]:
                idx = info["ind"][0]
                anot.xy = (idx, valores[idx])
                anot.set_text(f"{labels[idx]}\n{fmt(valores[idx])}")
                anot.set_visible(True); canvas.draw_idle()
            elif anot.get_visible():
                anot.set_visible(False); canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _hover)

    # ── GRÁFICO DE BARRAS CGR vs CGF ─────────────────────────────────────────

    def _grafico_barras(self, cons: list[dict]):
        frame = self.frame_gr_cgrcgf
        for w in frame.winfo_children():
            w.destroy()

        if not cons:
            ctk.CTkLabel(frame, text="Sem dados.",
                         font=ctk.CTkFont(size=12), text_color=_MUTED,
                         ).pack(padx=14, pady=30)
            return

        if not _MPL:
            return

        labels = [i["periodo"] for i in cons]
        cgr    = [float(i.get("cgr") or 0) for i in cons]
        cgf    = [float(i.get("cgf") or 0) for i in cons]

        fig = Figure(figsize=(10, 2.8), dpi=100, facecolor=_CARD)
        ax  = fig.add_subplot(111)
        ax.set_facecolor(_CARD)

        x = range(len(labels))
        w = 0.38
        b_cgr = ax.bar([i - w/2 for i in x], cgr, width=w, label="CGR", color=_AZUL, alpha=0.85)
        b_cgf = ax.bar([i + w/2 for i in x], cgf, width=w, label="CGF", color=_VERDE, alpha=0.85)

        for spine in ax.spines.values():
            spine.set_color(_MUTED)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, fontsize=8)
        ax.tick_params(colors=_MUTED, labelsize=8)
        ax.yaxis.set_major_formatter(lambda v, _: _brl_compacto(v))
        ax.grid(True, axis="y", color=_CARD2, linewidth=0.5)
        ax.legend(facecolor=_CARD, edgecolor=_MUTED, labelcolor=_TEXTO, fontsize=9)
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        anot = ax.annotate("", xy=(0, 0), xytext=(12, 12),
                           textcoords="offset points",
                           bbox=dict(boxstyle="round,pad=0.4", fc=_INPUT, ec=_MUTED),
                           color=_TEXTO, fontsize=9)
        anot.set_visible(False)

        series = [("CGR", b_cgr, cgr), ("CGF", b_cgf, cgf)]

        def _hover(event):
            if event.inaxes != ax:
                if anot.get_visible():
                    anot.set_visible(False); canvas.draw_idle()
                return
            for nome, barras, vals in series:
                for idx, rect in enumerate(barras):
                    if rect.contains(event)[0]:
                        anot.xy = (rect.get_x() + rect.get_width()/2, rect.get_height())
                        anot.set_text(f"{labels[idx]}\n{nome}: {_brl_compacto(vals[idx])}")
                        anot.set_visible(True); canvas.draw_idle()
                        return
            if anot.get_visible():
                anot.set_visible(False); canvas.draw_idle()

        canvas.mpl_connect("motion_notify_event", _hover)

    # ── FALLBACK SEM MATPLOTLIB ───────────────────────────────────────────────

    def _tabela_fallback(self, frame, itens, chave, fmt, cor):
        for i, item in enumerate(itens):
            bg = _CARD if i % 2 == 0 else _CARD2
            linha = ctk.CTkFrame(frame, fg_color=bg, corner_radius=4)
            linha.pack(fill="x", padx=8, pady=(8 if i == 0 else 1,
                                                1 if i < len(itens)-1 else 8))
            ctk.CTkLabel(linha, text=item["periodo"],
                         font=ctk.CTkFont(size=12, weight="bold"),
                         text_color=_TEXTO, width=100, anchor="w",
                         ).pack(side="left", padx=(10, 4), pady=6)
            ctk.CTkLabel(linha, text=fmt(float(item.get(chave) or 0)),
                         font=ctk.CTkFont(size=12), text_color=cor, anchor="e",
                         ).pack(side="left", padx=(4, 10), pady=6)
