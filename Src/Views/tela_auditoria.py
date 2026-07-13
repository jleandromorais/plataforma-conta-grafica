import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
import threading
import unicodedata
from queue import Queue, Empty
import pandas as pd

from Src.config import ui_theme as ui
from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Services.comparador_conta_grafica import ComparadorContaGrafica, _normalizar_numero_nota
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem, PIS_COFINS_RATE
from Src.Services.excel_auditoria import ExcelAuditoria
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.common.excel_final_destino import registrar_execucao_excel_final, obter_periodos_trimestre
from Src.common.formatting import format_brl as _fmt_brl
from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

_MESES_DETECT = {
    "JANEIRO":1,"JAN":1,"FEVEREIRO":2,"FEV":2,"MARÇO":3,"MARCO":3,"MAR":3,
    "ABRIL":4,"ABR":4,"MAIO":5,"MAI":5,"JUNHO":6,"JUN":6,
    "JULHO":7,"JUL":7,"AGOSTO":8,"AGO":8,"SETEMBRO":9,"SET":9,
    "OUTUBRO":10,"OUT":10,"NOVEMBRO":11,"NOV":11,"DEZEMBRO":12,"DEZ":12,
}
_MESES_ABREV = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

def _extrair_periodo_do_caminho(caminho: str) -> str:
    """Detecta 'Jan/2026' a partir do nome das pastas no caminho."""
    import re
    from datetime import date
    partes = Path(caminho).parts
    tokens = []
    for p in partes:
        tokens.extend(re.split(r'[\s\-_\.]+', p.upper()))
    mes_num = 0
    for tok in reversed(tokens):          # testa do mais específico para o mais genérico
        if tok in _MESES_DETECT:
            mes_num = _MESES_DETECT[tok]
            break
    if not mes_num:
        return ""
    anos = re.findall(r'\b(20\d{2})\b', caminho)
    ano = int(anos[-1]) if anos else date.today().year
    return f"{_MESES_ABREV[mes_num - 1]}/{ano}"

# Mapeando variavel de controle para facilitar
PDF_ATIVADO = True # Assumimos True se pdfplumber estiver instalado
OCR_ATIVADO = OCR_ENABLED

_EMPRESAS_CGR_TRANSPORTE = ('TAG', 'MASTERGAS')

def _empresa_integra_cgr(nome_empresa: str) -> bool:
    """CT-e da TAG e da Mastergás são custo de gás/transporte via gasoduto
    e integram o CGR (a planilha oficial não trata como frete comum)."""
    import re
    nome_norm = unicodedata.normalize("NFKD", nome_empresa or "").encode("ascii", "ignore").decode("ascii").upper()
    return any(re.search(rf'\b{empresa}\b', nome_norm) for empresa in _EMPRESAS_CGR_TRANSPORTE)

class TelaAuditoria(ctk.CTkFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.pasta_selecionada = None
        self.empresas_disponiveis = []
        self.empresas_selecionadas = []
        self.excel_path = None
        self.df_excel = None
        self.comparacao_notas = None
        self.resultados = []

        self.valor_total_geral  = 0.0
        self.volume_total_geral = 0.0
        self.valor_total_nfe    = 0.0
        self.volume_total_nfe   = 0.0
        self.valor_total_cte    = 0.0
        self.volume_total_cte   = 0.0
        self.cgr_liquido        = 0.0
        self.consolidacao       = ServicosConsolidacao()
        self._fila_auditoria = Queue()
        self._thread_auditoria: threading.Thread | None = None
        self._processando_auditoria = False
        self._fila_carregamento = Queue()
        self._thread_carregamento: threading.Thread | None = None

        self.modo_fonte = tk.StringVar(value="XML")
        self.tipo_excel_var = tk.StringVar(value="conta_grafica")
        self.periodo_comparacao_var = tk.StringVar(value="")
        self._periodo_norm_execucao = ""
        self._setup_ui()
    
    # ── seletor de mês ────────────────────────────────────────────────────────
    _MESES_GRID = ["Jan","Fev","Mar","Abr","Mai","Jun",
                   "Jul","Ago","Set","Out","Nov","Dez"]

    def _build_mes_picker(self, parent):
        """Grade 4×3 de botões de mês + spinner de ano."""
        from datetime import date as _date
        self._ano_picker = _date.today().year
        self._mes_btn: dict[str, ctk.CTkButton] = {}

        # controle de ano
        linha_ano = ctk.CTkFrame(parent, fg_color="transparent")
        linha_ano.pack(fill="x", padx=12, pady=(8, 6))
        ctk.CTkButton(linha_ano, text="◀", width=28, height=28,
                      fg_color=ui.COR_INPUT, hover_color=ui.COR_NEUTRA_HOVER,
                      command=lambda: self._mudar_ano(-1)).pack(side="left")
        self.lbl_ano_picker = ctk.CTkLabel(
            linha_ano, text=str(self._ano_picker),
            font=ctk.CTkFont(size=14, weight="bold"), text_color=ui.COR_TEXTO)
        self.lbl_ano_picker.pack(side="left", expand=True)
        ctk.CTkButton(linha_ano, text="▶", width=28, height=28,
                      fg_color=ui.COR_INPUT, hover_color=ui.COR_NEUTRA_HOVER,
                      command=lambda: self._mudar_ano(+1)).pack(side="right")

        # grade de meses
        grade = ctk.CTkFrame(parent, fg_color="transparent")
        grade.pack(fill="x", padx=10, pady=(0, 10))
        for col in range(4):
            grade.grid_columnconfigure(col, weight=1, uniform="mp")
        for idx, mes in enumerate(self._MESES_GRID):
            r, c = divmod(idx, 4)
            btn = ctk.CTkButton(
                grade, text=mes, height=30, font=ctk.CTkFont(size=12),
                fg_color=ui.COR_INPUT, hover_color=ui.COR_PRIMARIA_HOVER,
                text_color=ui.COR_TEXTO, corner_radius=6,
                command=lambda m=mes: self._selecionar_mes(m),
            )
            btn.grid(row=r, column=c, padx=3, pady=3, sticky="ew")
            self._mes_btn[mes] = btn

        self._aplicar_sel_mes()

    def _mudar_ano(self, delta: int):
        self._ano_picker += delta
        self.lbl_ano_picker.configure(text=str(self._ano_picker))
        self._aplicar_sel_mes()

    def _selecionar_mes(self, mes: str):
        periodo = f"{mes}/{self._ano_picker}"
        self.periodo_comparacao_var.set(periodo)
        self._aplicar_sel_mes()

    def _aplicar_sel_mes(self):
        atual = self.periodo_comparacao_var.get().strip()
        for mes, btn in self._mes_btn.items():
            esperado = f"{mes}/{self._ano_picker}"
            if atual == esperado:
                btn.configure(fg_color=ui.COR_PRIMARIA, text_color="white",
                              font=ctk.CTkFont(size=12, weight="bold"))
            else:
                btn.configure(fg_color=ui.COR_INPUT, text_color=ui.COR_TEXTO,
                              font=ctk.CTkFont(size=12))

    def _setup_ui(self):
        # ── Header ───────────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=ui.COR_HEADER)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="🔍  Auditoria CGR",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=ui.COR_TEXTO_TITULO,
        ).pack(side="left", padx=ui.ESP_LG, pady=ui.ESP_MD)

        # badges no header
        _tess_txt   = "🟢 Tesseract" if OCR_ATIVADO else "🔴 Tesseract"
        _tess_fg    = "#1a6b3c"      if OCR_ATIVADO else "#7b1a1a"
        _tess_color = ui.COR_SUCESSO if OCR_ATIVADO else ui.COR_PERIGO
        self.lbl_tesseract = ctk.CTkLabel(
            header, text=f"  {_tess_txt}  ", font=ctk.CTkFont(size=11, weight="bold"),
            text_color="white", fg_color=_tess_fg, corner_radius=6,
        )
        self.lbl_tesseract.pack(side="right", padx=(0, 14))
        self.lbl_modo_badge = ctk.CTkLabel(
            header, text="  XML  ", font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white", fg_color=ui.COR_PRIMARIA, corner_radius=6,
        )
        self.lbl_modo_badge.pack(side="right", padx=(0, 6))

        # ── Layout: esquerda fixa | direita expansível ────────────────────────
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True)
        corpo.grid_columnconfigure(0, weight=0, minsize=310)
        corpo.grid_columnconfigure(1, weight=1)
        corpo.grid_rowconfigure(0, weight=1)

        # ── COLUNA ESQUERDA ───────────────────────────────────────────────────
        painel_esq = ctk.CTkScrollableFrame(corpo, fg_color=ui.COR_HEADER,
                                            width=310, corner_radius=0)
        painel_esq.grid(row=0, column=0, sticky="nsew")

        def _bloco(titulo: str, cor: str, icon: str = ""):
            """Card com header colorido e corpo escuro."""
            card = ctk.CTkFrame(painel_esq, fg_color=ui.COR_CARD, corner_radius=10)
            card.pack(fill="x", padx=10, pady=(8, 0))
            topo = ctk.CTkFrame(card, fg_color=cor, corner_radius=10, height=32)
            topo.pack(fill="x")
            topo.pack_propagate(False)
            ctk.CTkLabel(topo, text=f" {icon}  {titulo}" if icon else f" {titulo}",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color="white").pack(side="left", padx=8, pady=6)
            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="x", padx=8, pady=(6, 10))
            return body

        # ── Seletor de mês (NOVA SEÇÃO) ───────────────────────────────────────
        f_mes = _bloco("Mês da Auditoria", ui.COR_PRIMARIA, "📅")
        self.lbl_mes_selecionado = ctk.CTkLabel(
            f_mes, text="Nenhum mês selecionado",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=ui.COR_MUTED,
        )
        self.lbl_mes_selecionado.pack(anchor="w", padx=10, pady=(0, 4))
        self._build_mes_picker(f_mes)
        # Entry oculto mas mantido para compatibilidade com _periodo_normalizado
        self.entry_periodo_comparacao = ctk.CTkEntry(
            f_mes, textvariable=self.periodo_comparacao_var,
            placeholder_text="ou digitar: jan/2026", height=28,
            font=ctk.CTkFont(size=11),
        )
        self.entry_periodo_comparacao.pack(fill="x", padx=10, pady=(2, 10))
        # Atualiza label quando período muda
        self.periodo_comparacao_var.trace_add("write", lambda *_: self._on_periodo_change())

        # ── Pasta ─────────────────────────────────────────────────────────────
        f_pasta = _bloco("Pasta com XML / PDF", ui.COR_NEUTRA, "📁")
        ctk.CTkButton(f_pasta, text="📂  Selecionar Pasta", command=self.selecionar_pasta,
                      fg_color=ui.COR_NEUTRA, hover_color=ui.COR_NEUTRA_HOVER, height=32,
                      ).pack(fill="x", padx=10, pady=(4, 4))
        self.lbl_pasta = ctk.CTkLabel(f_pasta, text="Nenhuma pasta selecionada",
                                      text_color=ui.COR_MUTED, font=ctk.CTkFont(size=10),
                                      wraplength=250, justify="left")
        self.lbl_pasta.pack(anchor="w", padx=10, pady=(0, 10))

        # ── Fonte XML / PDF ───────────────────────────────────────────────────
        f_modo = _bloco("Fonte dos arquivos", ui.COR_NEUTRA, "📂")
        linha_rb = ctk.CTkFrame(f_modo, fg_color="transparent")
        linha_rb.pack(fill="x", padx=10, pady=(4, 10))
        ctk.CTkRadioButton(linha_rb, text="XML", variable=self.modo_fonte, value="XML",
                           font=ctk.CTkFont(size=12), command=self._atualizar_badge_modo,
                           ).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(linha_rb, text="PDF (OCR)", variable=self.modo_fonte, value="PDF",
                           font=ctk.CTkFont(size=12), command=self._atualizar_badge_modo,
                           state="normal" if PDF_ATIVADO else "disabled",
                           ).pack(side="left")

        # ── Empresas ──────────────────────────────────────────────────────────
        f3 = _bloco("Empresas detectadas", ui.COR_SUCESSO, "🏢")
        self.checkboxes_empresas = []
        self.scroll_empresas = ctk.CTkScrollableFrame(f3, height=110, fg_color="transparent")
        self.scroll_empresas.pack(fill="x", padx=6, pady=(4, 10))

        # ── Excel (opcional) ──────────────────────────────────────────────────
        f4 = _bloco("Excel comparação  (opcional)", ui.COR_AVISO, "📊")
        linha_tipo = ctk.CTkFrame(f4, fg_color="transparent")
        linha_tipo.pack(fill="x", padx=10, pady=(4, 4))
        ctk.CTkRadioButton(linha_tipo, text="Conta Gráfica", variable=self.tipo_excel_var,
                           value="conta_grafica", font=ctk.CTkFont(size=11),
                           ).pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(linha_tipo, text="Outra planilha", variable=self.tipo_excel_var,
                           value="outra", font=ctk.CTkFont(size=11),
                           ).pack(side="left")
        ctk.CTkButton(f4, text="📄  Selecionar Excel", command=self.selecionar_excel,
                      fg_color=ui.COR_AVISO, hover_color=ui.COR_AVISO_HOVER, height=32,
                      text_color="#1a1a1a",
                      ).pack(fill="x", padx=10, pady=(0, 4))
        self.lbl_excel = ctk.CTkLabel(f4, text="Nenhum arquivo selecionado",
                                      text_color=ui.COR_MUTED, font=ctk.CTkFont(size=10),
                                      wraplength=250, justify="left")
        self.lbl_excel.pack(anchor="w", padx=10, pady=(0, 10))

        # ── COLUNA DIREITA ────────────────────────────────────────────────────
        painel_dir = ctk.CTkFrame(corpo, fg_color="transparent")
        painel_dir.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=8)
        painel_dir.grid_rowconfigure(3, weight=1)
        painel_dir.grid_columnconfigure(0, weight=1)

        # Status
        frame_status = ctk.CTkFrame(painel_dir, fg_color=ui.COR_CARD, corner_radius=10)
        frame_status.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        linha_st = ctk.CTkFrame(frame_status, fg_color="transparent")
        linha_st.pack(fill="x", padx=14, pady=(10, 4))
        self.lbl_status = ctk.CTkLabel(
            linha_st, text="⏳  Aguardando configurações...",
            font=ctk.CTkFont(size=13), text_color=ui.COR_AVISO, anchor="w",
        )
        self.lbl_status.pack(side="left", fill="x", expand=True)
        self.lbl_periodo_status = ctk.CTkLabel(
            linha_st, text="", font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white", fg_color=ui.COR_PRIMARIA, corner_radius=6,
        )
        self.lbl_periodo_status.pack(side="right")
        self.progress_auditoria = ctk.CTkProgressBar(
            frame_status, mode="indeterminate",
            progress_color=ui.COR_PRIMARIA, fg_color=ui.COR_INPUT,
        )
        self.progress_auditoria.pack(fill="x", padx=14, pady=(0, 10))
        self.progress_auditoria.set(0)

        # Painel CGR — 3 cards
        frame_cgr = ctk.CTkFrame(painel_dir, fg_color=ui.COR_CARD, corner_radius=10)
        frame_cgr.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        # topo do card CGR
        topo_cgr = ctk.CTkFrame(frame_cgr, fg_color=ui.COR_PRIMARIA,
                                 corner_radius=10, height=36)
        topo_cgr.pack(fill="x")
        topo_cgr.pack_propagate(False)
        ctk.CTkLabel(topo_cgr, text="  CGR APURADO",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="white").pack(side="left", padx=10, pady=8)
        self.lbl_cgr_periodo_titulo = ctk.CTkLabel(
            topo_cgr, text="", font=ctk.CTkFont(size=11),
            text_color="white", fg_color="#1a4a8a", corner_radius=4,
        )
        self.lbl_cgr_periodo_titulo.pack(side="right", padx=10)

        linha_cgr = ctk.CTkFrame(frame_cgr, fg_color="transparent")
        linha_cgr.pack(fill="x", padx=10, pady=10)
        for col in range(3):
            linha_cgr.grid_columnconfigure(col, weight=1, uniform="cgr")

        def _cgr_card(parent, col, icon, label, cor_val, cor_fundo):
            c = ctk.CTkFrame(parent, fg_color=cor_fundo, corner_radius=10)
            c.grid(row=0, column=col, padx=4, sticky="ew")
            ctk.CTkLabel(c, text=icon, font=ctk.CTkFont(size=18)).pack(pady=(10, 0))
            ctk.CTkLabel(c, text=label, font=ctk.CTkFont(size=10),
                         text_color=ui.COR_MUTED).pack()
            lbl = ctk.CTkLabel(c, text="—", font=ctk.CTkFont(size=14, weight="bold"),
                               text_color=cor_val)
            lbl.pack(pady=(2, 10))
            return lbl

        self.lbl_cgr_bruto   = _cgr_card(linha_cgr, 0, "📦", "Bruto total",   ui.COR_TEXTO,  ui.COR_INPUT)
        self.lbl_cgr_icms    = _cgr_card(linha_cgr, 1, "🏛️", "ICMS deduzido", ui.COR_AVISO,  ui.COR_INPUT)
        self.lbl_cgr_liquido = _cgr_card(linha_cgr, 2, "✅", "CGR Líquido",   ui.COR_SUCESSO, ui.COR_INPUT)

        ctk.CTkLabel(
            frame_cgr,
            text=("⚠️ Valores calculados a partir dos XML/PDF processados — pequenas "
                  "diferenças de centavos por arredondamento ou leitura via OCR podem "
                  "ocorrer. Sempre confira contra a planilha oficial antes de fechar o período."),
            font=ctk.CTkFont(size=10),
            text_color=ui.COR_MUTED,
            wraplength=520,
            justify="left",
        ).pack(fill="x", padx=14, pady=(0, 10))

        # ── Painel trimestral ─────────────────────────────────────────────────
        frame_tri = ctk.CTkFrame(painel_dir, fg_color=ui.COR_CARD, corner_radius=10)
        frame_tri.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        topo_tri = ctk.CTkFrame(frame_tri, fg_color="#8e44ad", corner_radius=10, height=34)
        topo_tri.pack(fill="x")
        topo_tri.pack_propagate(False)
        self.lbl_tri_header = ctk.CTkLabel(
            topo_tri, text="  📆  Soma Trimestral",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white")
        self.lbl_tri_header.pack(side="left", padx=10, pady=8)
        self.lbl_tri_periodo = ctk.CTkLabel(
            topo_tri, text="", font=ctk.CTkFont(size=11),
            text_color="white", fg_color="#5b2c6f", corner_radius=4,
        )
        self.lbl_tri_periodo.pack(side="right", padx=10)

        linha_tri = ctk.CTkFrame(frame_tri, fg_color="transparent")
        linha_tri.pack(fill="x", padx=10, pady=8)
        for col in range(4):
            linha_tri.grid_columnconfigure(col, weight=1, uniform="tri")

        self._tri_title_labels: list[ctk.CTkLabel] = []
        self._tri_labels: list[ctk.CTkLabel] = []

        def _tri_card(parent, col, titulo_fixo, cor_fundo, cor_val):
            c = ctk.CTkFrame(parent, fg_color=cor_fundo, corner_radius=8)
            c.grid(row=0, column=col, padx=3, sticky="ew")
            lbl_titulo = ctk.CTkLabel(c, text=titulo_fixo, font=ctk.CTkFont(size=10),
                                      text_color=ui.COR_MUTED)
            lbl_titulo.pack(pady=(8, 0))
            lbl_val = ctk.CTkLabel(c, text="—", font=ctk.CTkFont(size=13, weight="bold"),
                                   text_color=cor_val)
            lbl_val.pack(pady=(2, 8))
            return lbl_titulo, lbl_val

        for col, (tit, fg, cor) in enumerate([
            ("—",          ui.COR_INPUT, ui.COR_TEXTO),
            ("—",          ui.COR_INPUT, ui.COR_TEXTO),
            ("—",          ui.COR_INPUT, ui.COR_TEXTO),
            ("∑ Trimestre",ui.COR_INPUT, "#c39bd3"),
        ]):
            lt, lv = _tri_card(linha_tri, col, tit, fg, cor)
            self._tri_title_labels.append(lt)
            self._tri_labels.append(lv)

        # Resultados
        frame_res = ctk.CTkFrame(painel_dir, fg_color=ui.COR_CARD, corner_radius=10)
        frame_res.grid(row=3, column=0, sticky="nsew")
        frame_res.grid_rowconfigure(1, weight=1)
        frame_res.grid_columnconfigure(0, weight=1)

        topo_res = ctk.CTkFrame(frame_res, fg_color=ui.COR_NEUTRA, corner_radius=10, height=34)
        topo_res.grid(row=0, column=0, sticky="ew")
        topo_res.grid_propagate(False)
        ctk.CTkLabel(topo_res, text="📋  Resultado detalhado",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="white").pack(side="left", padx=12, pady=8)

        self.text_resultados = ctk.CTkTextbox(
            frame_res, font=("Consolas", 11),
            fg_color=ui.COR_FUNDO, text_color=ui.COR_TEXTO,
        )
        self.text_resultados.grid(row=1, column=0, sticky="nsew", padx=6, pady=(4, 6))

        # ── Rodapé fixo ───────────────────────────────────────────────────────
        rodape = ctk.CTkFrame(self, fg_color=ui.COR_HEADER, corner_radius=0, height=56)
        rodape.pack(fill="x", side="bottom")
        rodape.pack_propagate(False)

        self.btn_excel_final = ctk.CTkButton(
            rodape, text="➕  Excel Final",
            command=self._adicionar_excel_final,
            font=ctk.CTkFont(size=12, weight="bold"), height=36,
            fg_color=ui.COR_ROXO, hover_color=ui.COR_ROXO_HOVER, state="disabled",
        )
        self.btn_excel_final.pack(side="right", padx=(6, 14), pady=10)

        self.btn_salvar_scg = ctk.CTkButton(
            rodape, text="💾  Salvar no SCG",
            command=self._salvar_cgr_scg,
            font=ctk.CTkFont(size=12, weight="bold"), height=36,
            fg_color=ui.COR_SUCESSO, hover_color=ui.COR_SUCESSO_HOVER, state="disabled",
        )
        self.btn_salvar_scg.pack(side="right", padx=6, pady=10)

        self.btn_auditar = ctk.CTkButton(
            rodape, text="▶  EXECUTAR AUDITORIA",
            command=self.iniciar_auditoria,
            font=ctk.CTkFont(size=13, weight="bold"), height=36,
            fg_color=ui.COR_PRIMARIA, hover_color=ui.COR_PRIMARIA_HOVER, state="disabled",
        )
        self.btn_auditar.pack(side="right", padx=6, pady=10)

        # período no canto esquerdo do rodapé
        self.lbl_rodape_periodo = ctk.CTkLabel(
            rodape, text="Mês: não selecionado",
            font=ctk.CTkFont(size=12), text_color=ui.COR_MUTED,
        )
        self.lbl_rodape_periodo.pack(side="left", padx=16)
    
    # --- HELPERS ---
    _MESES_ABREV_MAP = {
        "Jan":1,"Fev":2,"Mar":3,"Abr":4,"Mai":5,"Jun":6,
        "Jul":7,"Ago":8,"Set":9,"Out":10,"Nov":11,"Dez":12,
    }
    _MESES_IDX_MAP = {v: k for k, v in {"Jan":1,"Fev":2,"Mar":3,"Abr":4,"Mai":5,"Jun":6,
                                          "Jul":7,"Ago":8,"Set":9,"Out":10,"Nov":11,"Dez":12}.items()}

    def _trimestre_de(self, periodo: str) -> list[str]:
        """Retorna os 3 períodos do trimestre a que pertence o período dado."""
        if not periodo or "/" not in periodo:
            return []
        mes_ab, ano = periodo.split("/")
        n = self._MESES_ABREV_MAP.get(mes_ab)
        if not n:
            return []
        # trimestres: 1-3, 4-6, 7-9, 10-12
        ini = ((n - 1) // 3) * 3 + 1
        return [f"{self._MESES_IDX_MAP[i]}/{ano}" for i in range(ini, ini + 3)]

    def _atualizar_painel_trimestral(self, periodo: str):
        """Busca CGR dos 3 meses do trimestre no banco e popula os cards."""
        def _fmt(v):
            return "—" if v is None else _fmt_brl(v)

        meses = self._trimestre_de(periodo)
        if not meses:
            for lbl in self._tri_labels:
                lbl.configure(text="—", text_color=ui.COR_MUTED)
            self.lbl_tri_periodo.configure(text="")
            return

        m1, m2, m3 = [m.split("/")[0] for m in meses]
        self.lbl_tri_header.configure(
            text=f"  📆  Soma Trimestral  —  {m1} · {m2} · {m3}"
        )
        self.lbl_tri_periodo.configure(
            text=f"  {meses[0]}  ·  {meses[1]}  ·  {meses[2]}  "
        )

        valores: list[float | None] = []
        try:
            with DatabasePMPV() as db:
                for m in meses:
                    rows = db.listar_consolidacao_completa(periodo=m)
                    if rows:
                        valores.append(float(rows[0].get("cgr") or 0))
                    else:
                        valores.append(None)
        except Exception:
            valores = [None, None, None]

        soma = sum(v for v in valores if v is not None)
        n_prec = sum(1 for v in valores if v is None)

        for i, (lbl_t, lbl_v, m, v) in enumerate(
            zip(self._tri_title_labels[:3], self._tri_labels[:3], meses, valores)
        ):
            lbl_t.configure(text=m)
            if v is None:
                lbl_v.configure(text="pendente", text_color=ui.COR_MUTED)
            else:
                lbl_v.configure(text=_fmt(v), text_color=ui.COR_TEXTO)

        cor_soma = "#c39bd3" if n_prec > 0 else ui.COR_SUCESSO
        sufixo = f"  ({3 - n_prec}/3)" if n_prec > 0 else ""
        self._tri_labels[3].configure(text=_fmt(soma) + sufixo, text_color=cor_soma)

    def _on_periodo_change(self):
        """Sincroniza todos os labels de período quando o usuário seleciona mês."""
        periodo = self.periodo_comparacao_var.get().strip()
        if periodo:
            self.lbl_mes_selecionado.configure(
                text=f"📅  {periodo}", text_color=ui.COR_PRIMARIA,
            )
            self.lbl_periodo_status.configure(text=f"  {periodo}  ")
            self.lbl_cgr_periodo_titulo.configure(text=f"  {periodo}  ")
            self.lbl_rodape_periodo.configure(
                text=f"Mês: {periodo}", text_color=ui.COR_TEXTO,
            )
            self._atualizar_painel_trimestral(periodo)
        else:
            self.lbl_mes_selecionado.configure(
                text="Nenhum mês selecionado", text_color=ui.COR_MUTED,
            )
            self.lbl_periodo_status.configure(text="")
            self.lbl_cgr_periodo_titulo.configure(text="")
            self.lbl_rodape_periodo.configure(
                text="Mês: não selecionado", text_color=ui.COR_MUTED,
            )
            for lbl in self._tri_labels:
                lbl.configure(text="—", text_color=ui.COR_MUTED)
            for lbl_t in self._tri_title_labels[:3]:
                lbl_t.configure(text="—")
            self.lbl_tri_header.configure(text="  📆  Soma Trimestral")
            self.lbl_tri_periodo.configure(text="")
        self._aplicar_sel_mes()
        self._verificar_habilitacao()

    def _atualizar_badge_modo(self):
        modo = self.modo_fonte.get()
        if modo == "XML":
            self.lbl_modo_badge.configure(text="  XML  ", fg_color=ui.COR_PRIMARIA)
        else:
            cor = ui.COR_SUCESSO if OCR_ATIVADO else ui.COR_PERIGO
            txt = "  PDF  " if OCR_ATIVADO else "  PDF ⚠️  "
            self.lbl_modo_badge.configure(text=txt, fg_color=cor)

    def _atualizar_painel_cgr(self, bruto: float, icms: float, liquido: float):
        _fmt = _fmt_brl
        self.lbl_cgr_bruto.configure(text=_fmt(bruto))
        self.lbl_cgr_icms.configure(text=_fmt(icms))
        self.lbl_cgr_liquido.configure(text=_fmt(liquido))

    def _periodo_normalizado(self) -> str:
        from Src.common.periodos import normalizar_periodo

        periodo_str = self.periodo_comparacao_var.get().strip()
        return normalizar_periodo(periodo_str) if periodo_str else ""

    # --- SELEÇÃO ---
    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta PAI")
        if pasta:
            self.pasta_selecionada = Path(pasta)
            self.lbl_pasta.configure(text=f"⏳ Lendo pastas em: {pasta}", text_color=ui.COR_AVISO)
            self.lbl_status.configure(text="Carregando empresas da pasta selecionada...", text_color=ui.COR_AVISO)

            # Auto-detectar mês/ano pelo nome da pasta
            periodo_detectado = _extrair_periodo_do_caminho(pasta)
            if periodo_detectado and not self.periodo_comparacao_var.get().strip():
                self.periodo_comparacao_var.set(periodo_detectado)

            self._thread_carregamento = threading.Thread(
                target=self._worker_carregar_empresas,
                args=(self.pasta_selecionada,),
                daemon=True,
            )
            self._thread_carregamento.start()
            self.after(80, self._poll_fila_carregamento)
    
    def _criar_checkboxes_empresas(self):
        for _, _, cb in self.checkboxes_empresas:
            cb.destroy()
        self.checkboxes_empresas.clear()
        for empresa in self.empresas_disponiveis:
            var = tk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(self.scroll_empresas, text=empresa, variable=var, command=self._verificar_habilitacao)
            cb.pack(anchor="w", padx=10, pady=3)
            self.checkboxes_empresas.append((empresa, var, cb))
    
    def selecionar_excel(self):
        arquivo = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls")])
        if arquivo:
            self.excel_path = arquivo
            self.df_excel = None
            self.lbl_excel.configure(text=f"⏳ Carregando {Path(arquivo).name}...", text_color=ui.COR_AVISO)
            self.lbl_status.configure(text="Lendo arquivo Excel em segundo plano...", text_color=ui.COR_AVISO)
            self._thread_carregamento = threading.Thread(
                target=self._worker_carregar_excel,
                args=(arquivo,),
                daemon=True,
            )
            self._thread_carregamento.start()
            self.after(80, self._poll_fila_carregamento)

    def _worker_carregar_empresas(self, pasta: Path):
        try:
            empresas = sorted([d.name for d in pasta.iterdir() if d.is_dir()])
            self._fila_carregamento.put(("empresas_ok", pasta, empresas))
        except Exception as e:
            self._fila_carregamento.put(("empresas_error", str(e)))

    def _worker_carregar_excel(self, arquivo: str):
        try:
            planilhas = pd.read_excel(arquivo, sheet_name=None)
            frames = []
            for nome_aba, df_aba in planilhas.items():
                if df_aba is None or df_aba.empty:
                    continue
                df_tmp = df_aba.copy()
                df_tmp["__sheet_name__"] = str(nome_aba)
                frames.append(df_tmp)
            if not frames:
                raise ValueError("A planilha selecionada não contém abas com dados.")
            df = pd.concat(frames, ignore_index=True, sort=False)
            self._fila_carregamento.put(("excel_ok", arquivo, df))
        except Exception as e:
            self._fila_carregamento.put(("excel_error", str(e)))

    def _poll_fila_carregamento(self):
        recebeu_msg = False
        while True:
            try:
                msg = self._fila_carregamento.get_nowait()
                recebeu_msg = True
            except Empty:
                break

            tipo = msg[0]
            if tipo == "empresas_ok":
                _, pasta, empresas = msg
                self.empresas_disponiveis = empresas
                if not self.empresas_disponiveis:
                    self.lbl_pasta.configure(text=f"⚠️ {pasta}", text_color=ui.COR_AVISO)
                    self.lbl_status.configure(text="Nenhuma subpasta encontrada.", text_color=ui.COR_AVISO)
                    messagebox.showwarning("Aviso", "Nenhuma subpasta encontrada!")
                else:
                    self.lbl_pasta.configure(text=f"✅ {pasta}", text_color=ui.COR_SUCESSO)
                    self.lbl_status.configure(
                        text=f"{len(self.empresas_disponiveis)} empresa(s) carregadas",
                        text_color=ui.COR_SUCESSO,
                    )
                    self._criar_checkboxes_empresas()
                self._verificar_habilitacao()
            elif tipo == "empresas_error":
                self.lbl_status.configure(text="Erro ao ler pasta selecionada", text_color=ui.COR_PERIGO)
                messagebox.showerror("Erro", f"Falha ao carregar pastas:\n{msg[1]}")
            elif tipo == "excel_ok":
                _, arquivo, df = msg
                self.df_excel = df
                self.lbl_excel.configure(text=f"✅ {Path(arquivo).name}", text_color=ui.COR_SUCESSO)
                self.lbl_status.configure(text=f"Excel: {len(self.df_excel)} linhas", text_color=ui.COR_SUCESSO)
                self._verificar_habilitacao()
            elif tipo == "excel_error":
                self.excel_path = None
                self.df_excel = None
                self.lbl_excel.configure(text="Nenhum arquivo selecionado", text_color="gray")
                self.lbl_status.configure(text="Erro ao carregar Excel", text_color=ui.COR_PERIGO)
                messagebox.showerror("Erro", f"Falha ao ler o Excel:\n{msg[1]}")

        if self._thread_carregamento and self._thread_carregamento.is_alive():
            self.after(80, self._poll_fila_carregamento)
    
    def _verificar_habilitacao(self):
        if self._processando_auditoria:
            self.btn_auditar.configure(state="disabled")
            return

        empresas_sel = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]
        periodo_ok = bool(self._periodo_normalizado())
        excel_ok = self.df_excel is not None
        if self.pasta_selecionada and empresas_sel:
            self.btn_auditar.configure(state="normal")
            if excel_ok and periodo_ok:
                self.lbl_status.configure(
                    text=(
                        f"Pronto para auditar: {len(empresas_sel)} empresa(s). "
                        "Comparação de divergências habilitada."
                    ),
                    text_color=ui.COR_SUCESSO,
                )
            elif excel_ok and not periodo_ok:
                self.lbl_status.configure(
                    text=(
                        "Auditoria habilitada. Preencha Mês/Ano válido para incluir "
                        "divergências no Excel."
                    ),
                    text_color=ui.COR_AVISO,
                )
            else:
                self.lbl_status.configure(
                    text="Auditoria habilitada (sem comparação com Excel).",
                    text_color=ui.COR_AVISO,
                )
        else:
            self.btn_auditar.configure(state="disabled")

    # --- LÓGICA DE EXECUÇÃO ---
    def iniciar_auditoria(self):
        if self._processando_auditoria:
            return

        empresas = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]
        if not self.pasta_selecionada or not empresas:
            messagebox.showwarning("Aviso", "Selecione uma pasta e ao menos uma empresa.")
            return

        self._periodo_norm_execucao = self._periodo_normalizado()

        self._alterar_estado_processamento(True)
        self.text_resultados.delete("1.0", "end")
        self.resultados.clear()
        self.lbl_status.configure(text="Iniciando auditoria...", text_color=ui.COR_AVISO)
        self.text_resultados.insert("end", "⏳ Processando em segundo plano...\n")
        self.text_resultados.insert("end", "Isso evita travamentos da interface durante a leitura dos arquivos.\n")

        usar_pdf = self.modo_fonte.get() == "PDF"
        self._thread_auditoria = threading.Thread(
            target=self._worker_auditoria,
            args=(empresas, usar_pdf),
            daemon=True,
        )
        self._thread_auditoria.start()
        self.after(120, self._poll_fila_auditoria)

    def _alterar_estado_processamento(self, processando: bool):
        self._processando_auditoria = processando
        if processando:
            self.btn_auditar.configure(state="disabled")
            self.btn_salvar_scg.configure(state="disabled")
            self.progress_auditoria.start()
        else:
            self.progress_auditoria.stop()
            self.progress_auditoria.set(0)
            self._verificar_habilitacao()

    def _worker_auditoria(self, empresas: list[str], usar_pdf: bool):
        try:
            resultados: list[XMLItem] = []
            total_xmls = 0
            total_ocr = 0

            for idx, empresa in enumerate(empresas, start=1):
                self._fila_auditoria.put(("status", f"📂 Auditando {empresa} ({idx}/{len(empresas)})..."))
                pasta_empresa = self.pasta_selecionada / empresa
                xmls = list({p.resolve() for p in pasta_empresa.rglob("*.xml")})
                pdfs = list({p.resolve() for p in pasta_empresa.rglob("*.pdf")})

                arquivos_proc = 0
                notas_via_xml: set[str] = set()
                valores_via_xml: set[float] = set()

                if not usar_pdf:
                    for xml_file in xmls:
                        total_xmls += 1
                        arquivos_proc += 1
                        res = self._auditar_xml(xml_file, empresa)
                        if res:
                            resultados.append(res)
                            notas_via_xml.add(_normalizar_numero_nota(res.numero))
                            valores_via_xml.add(round(res.valor_total, 2))
                        if arquivos_proc % 25 == 0:
                            self._fila_auditoria.put(("status", f"📂 {empresa}: {arquivos_proc}/{len(xmls)} XMLs"))

                # Todo PDF da pasta é lido via OCR (mesmo com XMLs presentes),
                # para nunca descartar notas que só existem em PDF. A duplicata
                # com o que já veio de XML só é descartada quando o número OU o
                # valor total extraído do PDF batem com um XML já processado.
                pdfs_para_ocr = pdfs
                for pdf_file in pdfs_para_ocr:
                    total_ocr += 1
                    arquivos_proc += 1
                    dados = RegrasAuditoria.parse_pdf_ocr(pdf_file)
                    if "erro" not in dados:
                        nota_pdf_norm = _normalizar_numero_nota(dados.get("numero", ""))
                        valor_pdf = round(float(dados.get("valor_total", 0.0) or 0.0), 2)
                        if not usar_pdf and (
                            (nota_pdf_norm and nota_pdf_norm in notas_via_xml)
                            or (valor_pdf and valor_pdf in valores_via_xml)
                        ):
                            continue  # já capturada via XML
                        vf = dados.get("valor_total", 0.0)
                        resultados.append(
                            XMLItem(
                                empresa,
                                dados.get("tipo", "NF-e"),
                                dados.get("numero", "N/A"),
                                vf,
                                dados.get("icms", 0.0),
                                dados.get("icms_taxa", 0.0),
                                dados.get("pis", 0.0),
                                dados.get("cofins", 0.0),
                                dados.get("volume", 0),
                                "OCR",
                                dados.get("volume_total", 0.0),
                            )
                        )
                    if arquivos_proc % 10 == 0:
                        self._fila_auditoria.put(("status", f"📂 {empresa}: {arquivos_proc}/{len(pdfs_para_ocr)} PDFs"))

            self._fila_auditoria.put(("done", resultados, total_xmls, total_ocr))
        except Exception as e:
            self._fila_auditoria.put(("error", str(e)))

    def _poll_fila_auditoria(self):
        while True:
            try:
                msg = self._fila_auditoria.get_nowait()
            except Empty:
                break

            tipo = msg[0]
            if tipo == "status":
                self.lbl_status.configure(text=msg[1], text_color=ui.COR_AVISO)
            elif tipo == "done":
                _, resultados, total_xmls, total_ocr = msg
                self.resultados = resultados
                self._alterar_estado_processamento(False)
                self.lbl_status.configure(text="✅ Auditoria concluída", text_color=ui.COR_SUCESSO)
                self._processar_totais_e_ui(total_xmls, total_ocr)
                return
            elif tipo == "error":
                self._alterar_estado_processamento(False)
                self.lbl_status.configure(text="❌ Erro na auditoria", text_color=ui.COR_PERIGO)
                messagebox.showerror("Erro", f"Falha ao processar auditoria:\n{msg[1]}")
                return

        if self._processando_auditoria:
            self.after(120, self._poll_fila_auditoria)

    def _auditar_xml(self, xml_path: Path, empresa: str) -> XMLItem:
        tipo = RegrasAuditoria.detectar_tipo_xml(xml_path)
        if tipo == 'nfe': dados = RegrasAuditoria.parse_nfe(xml_path)
        elif tipo == 'cte': dados = RegrasAuditoria.parse_cte(xml_path)
        else: return None
        
        if 'erro' in dados: return None
        
        vol_total = dados.get('volume_total', float(dados.get('volume', 0)))
        return XMLItem(empresa, dados['tipo'], dados['numero'], dados['valor_total'],
                       dados['icms'], dados.get('icms_taxa', 0.0), dados['pis'], dados['cofins'], int(vol_total), "OK", vol_total)

    def _processar_totais_e_ui(self, n_xmls, n_pdfs):
        # Deduplicar por (empresa, tipo, numero) — segurança contra XMLs repetidos
        visto = set()
        unicos = []
        for r in self.resultados:
            chave = (r.empresa, r.tipo, r.numero)
            if chave not in visto:
                visto.add(chave)
                unicos.append(r)
        self.resultados = unicos

        nfes = [r for r in self.resultados if r.tipo == 'NF-e']
        ctes = [r for r in self.resultados if r.tipo == 'CT-e']

        self.valor_total_nfe    = sum(r.valor_total for r in nfes)
        self.volume_total_nfe   = sum(r.volume_total for r in nfes)
        self.valor_total_cte    = sum(r.valor_total for r in ctes)
        self.volume_total_cte   = sum(r.volume_total for r in ctes)
        self.valor_total_geral  = self.valor_total_nfe + self.valor_total_cte
        self.volume_total_geral = self.volume_total_nfe + self.volume_total_cte

        # Cálculo por documento (mesma lógica validada contra planilha Arch).
        # CGR considera NF-e (compra de gás) + CT-e da TAG e da Mastergás
        # (custo de gás/transporte via gasoduto, que a planilha oficial trata
        # como parte do CGR). CT-e das demais transportadoras é frete e não
        # integra o CGR.
        itens_cgr = [r for r in self.resultados if r.tipo == 'NF-e' or _empresa_integra_cgr(r.empresa)]
        bruto_total = sum(r.valor_total for r in itens_cgr)
        icms_total_all = sum(r.valor_total * r.icms_taxa for r in itens_cgr)
        self.cgr_liquido = sum(
            RegrasAuditoria.calcular_s_tributos(r.valor_total, r.icms_taxa)
            for r in itens_cgr
        )
        self._atualizar_painel_cgr(self.valor_total_geral, icms_total_all, self.cgr_liquido)

        _fmt = _fmt_brl
        def _sep(c="─", n=62): return c * n

        self.text_resultados.configure(state="normal")
        self.text_resultados.delete("1.0", "end")

        self.text_resultados.insert("end", f"{'▐ AUDITORIA CGR CONCLUÍDA':^62}\n")
        self.text_resultados.insert("end", f"{_sep('═')}\n")
        self.text_resultados.insert("end", f"  Arquivos lidos : {n_xmls} XML  |  {n_pdfs} PDF\n")
        self.text_resultados.insert("end", f"  Notas únicas   : {len(self.resultados)}\n")
        self.text_resultados.insert("end", f"  CGR Líquido    : {_fmt(self.cgr_liquido)}\n")
        self.text_resultados.insert("end", f"{_sep('═')}\n\n")

        # ── Por empresa ──────────────────────────────────────────────────────
        from collections import defaultdict
        por_empresa: dict[str, list] = defaultdict(list)
        for r in self.resultados:
            por_empresa[r.empresa].append(r)

        for emp, itens in sorted(por_empresa.items()):
            nfes_e = [i for i in itens if i.tipo == "NF-e"]
            ctes_e = [i for i in itens if i.tipo == "CT-e"]
            val_e  = sum(i.valor_total for i in itens)
            cgr_e  = sum(RegrasAuditoria.calcular_s_tributos(i.valor_total, i.icms_taxa) for i in itens)
            self.text_resultados.insert("end", f"┌─ {emp}\n")
            self.text_resultados.insert("end", f"│  NF-e: {len(nfes_e):>4} notas"
                                               f"   CT-e: {len(ctes_e):>3} notas"
                                               f"   Total: {_fmt(val_e)}\n")
            self.text_resultados.insert("end", f"│  CGR líquido: {_fmt(cgr_e)}\n")
            self.text_resultados.insert("end", f"└{_sep()}\n\n")

        self.text_resultados.insert("end", f"\n")
        comparou = self._comparar_com_conta_grafica()
        if comparou and self.comparacao_notas:
            comp = self.comparacao_notas
            n_div = len(comp.notas_apenas_nossa) + len(comp.notas_apenas_conta_grafica)
            self.text_resultados.insert("end", f"\n{'='*50}\n")
            self.text_resultados.insert("end", f"COMPARAÇÃO  ({comp.periodo})\n")
            self.text_resultados.insert("end", f"{'='*50}\n")

            # Diagnóstico de abas
            abas = getattr(comp, "sheets_excel", [])
            abas_match = getattr(comp, "sheets_periodo_match", [])
            if abas:
                self.text_resultados.insert("end", f"Abas na planilha: {', '.join(abas)}\n")
            if abas_match:
                self.text_resultados.insert("end", f"Aba usada: {', '.join(abas_match)}\n")
            elif abas:
                self.text_resultados.insert(
                    "end",
                    f"⚠️  NENHUMA aba corresponde a '{comp.periodo}'!\n"
                    f"   Verifique se o arquivo correto foi selecionado.\n",
                )

            self.text_resultados.insert("end", f"\nNotas em ambas (confirmadas): {comp.qtd_em_ambas}\n")
            self.text_resultados.insert("end", f"Só na auditoria (não na planilha): {len(comp.notas_apenas_nossa)}\n")
            self.text_resultados.insert("end", f"Só na planilha (não na auditoria): {len(comp.notas_apenas_conta_grafica)}\n")
            self.text_resultados.insert("end", f"Total divergências: {n_div}\n")
            self._exibir_divergencias_no_texto(comp)
            if comp.avisos:
                self.text_resultados.insert("end", "\nAlertas:\n")
                for aviso in comp.avisos:
                    self.text_resultados.insert("end", f"  • {aviso}\n")
        else:
            self.text_resultados.insert(
                "end",
                "\nComparação não executada. "
                "Selecione um Excel e informe Mês/Ano válido (ex: jan26) para comparar divergências.\n",
            )
        self.text_resultados.configure(state="disabled")

        self.btn_salvar_scg.configure(state="normal")
        self.btn_excel_final.configure(state="normal")
        self._gerar_e_salvar_excel()

    def _exibir_divergencias_no_texto(self, comp, limite: int = 25):
        self.text_resultados.insert("end", "\nDivergências detalhadas:\n")

        self.text_resultados.insert("end", "\n1) Notas só na auditoria:\n")
        if comp.notas_apenas_nossa:
            for item in comp.notas_apenas_nossa[:limite]:
                self.text_resultados.insert(
                    "end",
                    f"- {item.get('numero', '')} | {item.get('empresa', '')} | {item.get('tipo', '')}\n",
                )
            restante_nossa = len(comp.notas_apenas_nossa) - limite
            if restante_nossa > 0:
                self.text_resultados.insert("end", f"- ... e mais {restante_nossa} nota(s)\n")
        else:
            self.text_resultados.insert("end", "- Nenhuma\n")

        self.text_resultados.insert("end", "\n2) Notas só no Excel selecionado:\n")
        if comp.notas_apenas_conta_grafica:
            for item in comp.notas_apenas_conta_grafica[:limite]:
                self.text_resultados.insert(
                    "end",
                    f"- {item.get('numero', '')} | linha {item.get('linha_excel', '')}\n",
                )
            restante_excel = len(comp.notas_apenas_conta_grafica) - limite
            if restante_excel > 0:
                self.text_resultados.insert("end", f"- ... e mais {restante_excel} nota(s)\n")
        else:
            self.text_resultados.insert("end", "- Nenhuma\n")

    def _comparar_com_conta_grafica(self) -> bool:
        self.comparacao_notas = None
        if self.df_excel is None:
            return False

        periodo = self._periodo_norm_execucao or self._periodo_normalizado()

        if not periodo:
            return False

        tipo_label = "Conta Gráfica" if self.tipo_excel_var.get() == "conta_grafica" else "Planilha"
        try:
            self.comparacao_notas = ComparadorContaGrafica.comparar(
                resultados=self.resultados,
                df_excel=self.df_excel,
                periodo=periodo,
            )
            comp = self.comparacao_notas
            n_div = len(comp.notas_apenas_nossa) + len(comp.notas_apenas_conta_grafica)
            abas_match = getattr(comp, "sheets_periodo_match", [])
            abas_todas = getattr(comp, "sheets_excel", [])

            if not abas_match and abas_todas:
                self.lbl_status.configure(
                    text=f"⚠️ Aba '{periodo}' NÃO encontrada na planilha | abas: {', '.join(abas_todas[:4])}",
                    text_color=ui.COR_AVISO,
                )
            else:
                self.lbl_status.configure(
                    text=f"✅ {tipo_label} ({comp.periodo}) | confirmadas: {comp.qtd_em_ambas} | divergências: {n_div}",
                    text_color=ui.COR_SUCESSO if comp.qtd_em_ambas > 0 else "#e67e22",
                )
            return True
        except Exception as e:
            self.comparacao_notas = None
            self.lbl_status.configure(text="⚠️ Falha ao comparar notas com o Excel", text_color=ui.COR_AVISO)
            messagebox.showwarning(
                "Comparação indisponível",
                f"Não foi possível comparar com a planilha selecionada:\n{e}",
            )
            return False

    def _gerar_e_salvar_excel(self):
        if not self.resultados:
            return
        import os
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(os.getcwd(), f"Auditoria_{timestamp}.xlsx")
        try:
            ExcelAuditoria.gerar_relatorio_auditoria(
                self.resultados,
                path,
                cgr_total=self.cgr_liquido,
                comparacao=self.comparacao_notas,
            )
            self.lbl_status.configure(
                text=f"✅ Excel salvo: Auditoria_{timestamp}.xlsx",
                text_color=ui.COR_SUCESSO,
            )
        except Exception as e:
            messagebox.showerror("Erro ao Exportar", f"Falha ao gerar o Excel:\n{e}")

    def _salvar_cgr_scg(self):
        cgr = getattr(self, 'cgr_liquido', 0.0)
        periodo = self._periodo_normalizado()
        if not periodo:
            periodo = simpledialog.askstring("Salvar", "Período (ex: Dez/2025):", initialvalue="Dez/2025")
        if not periodo:
            return

        n_itens = len(self.resultados) if self.resultados else 0
        if not messagebox.askyesno("Confirmar salvamento",
                                   f"Salvar Auditoria CGR no banco de dados?\n\n"
                                   f"Período: {periodo}\n"
                                   f"CGR Líquido: R$ {cgr:,.2f}\n"
                                   f"Itens: {n_itens}"):
            return

        dados = self.consolidacao.salvar_cgr(periodo, cgr)
        rpv = dados["rpv"]

        # Salva os itens detalhados no banco principal
        if self.resultados:
            icms_total = sum(r.icms for r in self.resultados)
            itens_dict = [
                {
                    "empresa":     r.empresa,
                    "tipo":        r.tipo,
                    "numero":      r.numero,
                    "valor_total": r.valor_total,
                    "icms":        r.icms,
                    "pis":         r.pis,
                    "cofins":      r.cofins,
                    "volume_total": r.volume_total,
                    "cgr_liquido": RegrasAuditoria.calcular_s_tributos(r.valor_total, r.icms_taxa),
                }
                for r in self.resultados
            ]
            try:
                with DatabasePMPV() as db:
                    db.salvar_auditoria_itens(periodo, itens_dict)
            except Exception as e:
                messagebox.showwarning("Aviso BD", f"CGR salvo no SCG, mas erro ao salvar itens:\n{e}")

        messagebox.showinfo(
            "Salvo ✅",
            f"Período: {periodo}\n"
            f"CGR salvo: R$ {cgr:,.2f}\n"
            f"RPV calculado: R$ {rpv:,.2f}\n\n"
            f"{len(self.resultados)} item(ns) salvo(s) no banco."
        )

    def _adicionar_excel_final(self):
        if not self.resultados:
            messagebox.showwarning("Aviso", "Execute a auditoria antes de exportar o Excel final.")
            return

        periodo_salvar = self._periodo_normalizado()
        if not periodo_salvar:
            messagebox.showwarning(
                "Período não selecionado",
                "Selecione o mês/ano antes de exportar o Excel Final.",
                parent=self,
            )
            return

        # Precisa de Excel de comparação carregado
        if self.df_excel is None:
            messagebox.showwarning(
                "Excel de comparação não selecionado",
                "Selecione o Excel da Conta Gráfica antes de exportar.\n"
                "Use o campo 'Excel comparação (opcional)' no painel esquerdo.",
                parent=self,
            )
            return

        try:
            periodo_salvar = periodo_salvar.strip()

            # Executa (ou re-executa) a comparação agora, para garantir dados frescos
            self.lbl_status.configure(text="Comparando notas com o Excel...", text_color=ui.COR_AVISO)
            self.update_idletasks()

            from Src.Services.comparador_conta_grafica import ComparadorContaGrafica
            comparacao = ComparadorContaGrafica.comparar(
                resultados=self.resultados,
                df_excel=self.df_excel,
                periodo=periodo_salvar,
            )
            self.comparacao_notas = comparacao

            # Pede ao usuário onde salvar
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_sugerido = f"Auditoria_Comparacao_{periodo_salvar.replace('/', '-')}_{timestamp}.xlsx"
            destino = filedialog.asksaveasfilename(
                title="Salvar Excel de Auditoria com Divergências",
                initialfile=nome_sugerido,
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                parent=self,
            )
            if not destino:
                return

            cgr = getattr(self, 'cgr_liquido', 0.0)
            ExcelAuditoria.gerar_relatorio_auditoria(
                self.resultados,
                destino,
                cgr_total=cgr,
                comparacao=comparacao,
            )

            n_div = len(comparacao.notas_apenas_nossa) + len(comparacao.notas_apenas_conta_grafica)
            self.lbl_status.configure(
                text=f"✅ Excel salvo com comparação | {comparacao.qtd_em_ambas} confirmadas | {n_div} divergências",
                text_color=ui.COR_SUCESSO,
            )

            import os, subprocess
            os.startfile(destino)

        except Exception as e:
            messagebox.showerror("Erro ao exportar", f"Falha ao gerar o Excel:\n\n{e}")