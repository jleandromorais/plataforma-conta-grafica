import re
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime, date

from Src.config import ui_theme as ui
from Src.Services.servicos_cgf import ServicosCGF
from Src.Database.database import DatabasePMPV
from Src.common.excel_final_destino import (
    registrar_execucao_excel_final,
    obter_periodos_trimestre,
)
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# ── Detecção de período pelo nome do arquivo/pasta ──────────────────────────
_MESES_DETECT_CGF = {
    "JANEIRO":1,"JAN":1,"FEVEREIRO":2,"FEV":2,"MARÇO":3,"MARCO":3,"MAR":3,
    "ABRIL":4,"ABR":4,"MAIO":5,"MAI":5,"JUNHO":6,"JUN":6,
    "JULHO":7,"JUL":7,"AGOSTO":8,"AGO":8,"SETEMBRO":9,"SET":9,
    "OUTUBRO":10,"OUT":10,"NOVEMBRO":11,"NOV":11,"DEZEMBRO":12,"DEZ":12,
}
_ABREVS_CGF = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]

def _periodo_do_caminho_cgf(caminho: str) -> str:
    """Extrai 'Jan/2026' do nome do ficheiro ou pasta."""
    tokens = re.split(r'[\s\-_\./\\]+', Path(caminho).stem.upper())
    tokens += re.split(r'[\s\-_\./\\]+', Path(caminho).parent.name.upper())
    mes_num = 0
    for tok in reversed(tokens):
        if tok in _MESES_DETECT_CGF:
            mes_num = _MESES_DETECT_CGF[tok]
            break
    if not mes_num:
        return ""
    anos = re.findall(r'\b(20\d{2})\b', caminho)
    ano = int(anos[-1]) if anos else date.today().year
    return f"{_ABREVS_CGF[mes_num - 1]}/{ano}"


class TelaCGF(ctk.CTkFrame):

    _MESES_ABREV = ["Jan","Fev","Mar","Abr","Mai","Jun",
                    "Jul","Ago","Set","Out","Nov","Dez"]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.servicos = ServicosCGF()

        # Estado
        self.selected_files   = []
        self.volume_final_cgf = 0.0
        self.cgf_rs           = 0.0
        self._ultimo_resultado_cgf = {}

        # Variáveis de mapeamento de colunas
        self.col_fat_volume  = ctk.StringVar(value="Volume Faturado")
        self.col_fat_consumo = ctk.StringVar(value="Produto")
        self.val_fat_consumo = ctk.StringVar(value="consumo proprio")
        self.col_fat_cfop    = ctk.StringVar(value="CFOP")
        self.col_canc_volume = ctk.StringVar(value="Volume Canc/Deneg")
        self.col_dev_volume  = ctk.StringVar(value="Volume Devolução")

        self.pmpv_manual = ctk.StringVar(value="")

        self._setup_ui()

    # ──────────────────────────────────────────────────────────────────────────
    # UI principal
    # ──────────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=ui.COR_HEADER)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="Sistema CGF",
            font=ui.FONTE_TITULO, text_color=ui.COR_TEXTO_TITULO
        ).pack(side="left", padx=ui.ESP_LG, pady=ui.ESP_LG)

        ctk.CTkLabel(
            header, text="Cálculo de Volume Faturado — Faturada − Canceladas − Devoluções − Consumo Próprio",
            font=ui.FONTE_SUBTITULO, text_color=ui.COR_TEXTO_SUBTITULO
        ).pack(side="left", padx=ui.ESP_SM)

        # CONTAINER PRINCIPAL
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)

        # PAINEL ESQUERDO
        left = ctk.CTkFrame(main, width=400, corner_radius=15)
        left.pack(side="left", fill="both", padx=(0, 10), pady=0)
        left.pack_propagate(False)

        ctk.CTkLabel(
            left, text="Arquivos do Mês",
            font=("Roboto", 20, "bold")
        ).pack(pady=(20, 6), padx=20, anchor="w")

        self.lbl_arquivos = ctk.CTkLabel(
            left, text="Nenhum arquivo selecionado",
            font=("Roboto", 12), wraplength=350, text_color="#808080"
        )
        self.lbl_arquivos.pack(pady=(0, 6), padx=20)

        ctk.CTkButton(
            left, text="Selecionar Arquivos",
            command=self.select_files,
            height=40, font=("Roboto", 14, "bold"),
            fg_color="#2196F3", hover_color="#1976D2"
        ).pack(pady=(0, 4), padx=20, fill="x")

        ctk.CTkButton(
            left, text="Limpar",
            command=self.clear_files,
            height=32, font=("Roboto", 12),
            fg_color="#555", hover_color="#777"
        ).pack(pady=(0, 4), padx=20, fill="x")

        self._setup_seletor_periodo(left)

        ctk.CTkButton(
            left, text="PROCESSAR ARQUIVOS",
            command=self.calculate_total,
            height=50, font=("Roboto", 16, "bold"),
            fg_color="#4CAF50", hover_color="#45a049"
        ).pack(pady=20, padx=20, fill="x")

        # PAINEL DIREITO
        right = ctk.CTkFrame(main, corner_radius=15)
        right.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(
            right, text="Resultados",
            font=("Roboto", 20, "bold")
        ).pack(pady=(20, 10), padx=20, anchor="w")

        self.tabview = ctk.CTkTabview(right)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)

        self.tabview.add("Resumo")
        self.tabview.add("Configuração")
        self.tabview.add("Logs")

        self._build_aba_resumo()
        self._build_aba_config()
        self._build_aba_logs()

        # RODAPÉ
        footer = ctk.CTkFrame(self, height=100, corner_radius=15, fg_color="#1a1a2e")
        footer.pack(fill="x", padx=20, pady=(0, 20))
        footer.pack_propagate(False)

        result_frame = ctk.CTkFrame(footer, fg_color="transparent")
        result_frame.pack(side="left", padx=30, pady=20)

        ctk.CTkLabel(
            result_frame, text="VOLUME FINAL CGF:",
            font=("Roboto", 14)
        ).pack(anchor="w")

        self.result_label = ctk.CTkLabel(
            result_frame, text="0,0000 m³",
            font=("Roboto", 28, "bold"), text_color="#00d9ff"
        )
        self.result_label.pack(anchor="w")

        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(side="right", padx=30, pady=20)

        self.btn_salvar_scg = ctk.CTkButton(
            btn_frame, text="💾 Salvar CGF no Banco",
            command=self._salvar_cgf_scg,
            width=200, height=40,
            font=("Roboto", 13, "bold"),
            fg_color="#27ae60", hover_color="#229954"
        )
        self.btn_salvar_scg.pack(side="left", padx=8)

        self.btn_excel_final = ctk.CTkButton(
            btn_frame, text="➕ Adicionar ao Excel Final (Módulo 9)",
            command=self._adicionar_excel_final,
            width=280, height=40,
            font=("Roboto", 13, "bold"),
            fg_color="#2980b9", hover_color="#1a6fa8"
        )
        self.btn_excel_final.pack(side="left", padx=8)

    # ──────────────────────────────────────────────────────────────────────────
    # Aba Resumo
    # ──────────────────────────────────────────────────────────────────────────
    def _build_aba_resumo(self):
        tab = self.tabview.tab("Resumo")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Card: Volume Final CGF
        card_vol = ctk.CTkFrame(scroll, fg_color="#12122a", corner_radius=12)
        card_vol.pack(fill="x", padx=4, pady=(8, 6))

        ctk.CTkLabel(
            card_vol, text="Volume Final CGF",
            font=("Roboto", 13, "bold"), text_color="#a0a0a0"
        ).pack(anchor="w", padx=16, pady=(12, 2))

        self.lbl_volume_card = ctk.CTkLabel(
            card_vol, text="--- m³",
            font=("Roboto", 28, "bold"), text_color="#00d9ff"
        )
        self.lbl_volume_card.pack(anchor="w", padx=16, pady=(0, 6))

        # Detalhes do cálculo
        self.lbl_detalhes = ctk.CTkLabel(
            card_vol, text="Aguardando processamento...",
            font=("Roboto", 11), text_color="#606080", justify="left"
        )
        self.lbl_detalhes.pack(anchor="w", padx=16, pady=(0, 12))

        # Card: CGF em R$ (PMPV)
        card_rs = ctk.CTkFrame(scroll, fg_color="#0f2744", corner_radius=12)
        card_rs.pack(fill="x", padx=4, pady=(0, 6))

        ctk.CTkLabel(
            card_rs, text="CGF em R$  —  Volume × PMPV",
            font=("Roboto", 13, "bold"), text_color=ui.COR_PRIMARIA
        ).pack(anchor="w", padx=16, pady=(12, 6))

        pmpv_row = ctk.CTkFrame(card_rs, fg_color="transparent")
        pmpv_row.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            pmpv_row, text="PMPV (R$/m³):",
            font=("Roboto", 12), text_color="#a0a0a0", width=110, anchor="w"
        ).pack(side="left")

        self.pmpv_entry = ctk.CTkEntry(
            pmpv_row, textvariable=self.pmpv_manual,
            font=("Roboto", 12), width=130
        )
        self.pmpv_entry.pack(side="left", padx=(0, 10))
        self.pmpv_entry.bind("<KeyRelease>", lambda _e: self._atualizar_cgf_rs())

        ctk.CTkButton(
            pmpv_row, text="⚡ Carregar do banco",
            command=lambda: self._carregar_pmpv_banco(silencioso=False),
            width=150, height=32,
            font=("Roboto", 11, "bold"),
            fg_color="#2196F3", hover_color="#1976D2"
        ).pack(side="left")

        self.lbl_cgf_rs = ctk.CTkLabel(
            card_rs, text="CGF em R$:  ---",
            font=("Roboto", 18, "bold"), text_color=ui.COR_SUCESSO
        )
        self.lbl_cgf_rs.pack(anchor="w", padx=16, pady=(0, 12))

        # Card: Volume Prospectivo
        card_vp = ctk.CTkFrame(scroll, fg_color="#12122a", corner_radius=12)
        card_vp.pack(fill="x", padx=4, pady=(0, 6))

        ctk.CTkLabel(
            card_vp, text="Volume Prospectivo (VP)",
            font=("Roboto", 13, "bold"), text_color="#a0a0a0"
        ).pack(anchor="w", padx=16, pady=(12, 4))

        vp_row = ctk.CTkFrame(card_vp, fg_color="transparent")
        vp_row.pack(fill="x", padx=16, pady=(0, 12))

        self.lbl_vp_mensal = ctk.CTkLabel(
            vp_row, text="Mensal: ---",
            font=("Roboto", 13, "bold"), text_color=ui.COR_PRIMARIA
        )
        self.lbl_vp_mensal.pack(side="left", padx=(0, 30))

        self.lbl_vp_trimestral = ctk.CTkLabel(
            vp_row, text="Trimestral: ---",
            font=("Roboto", 13, "bold"), text_color=ui.COR_DESTAQUE
        )
        self.lbl_vp_trimestral.pack(side="left")

    # ──────────────────────────────────────────────────────────────────────────
    # Aba Configuração
    # ──────────────────────────────────────────────────────────────────────────
    def _build_aba_config(self):
        tab = self.tabview.tab("Configuração")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4, pady=4)

        def _secao(txt):
            ctk.CTkLabel(
                scroll, text=txt,
                font=("Roboto", 13, "bold"), text_color="#00d9ff"
            ).pack(anchor="w", pady=(12, 4), padx=8)

        def _campo(label, var):
            row = ctk.CTkFrame(scroll, fg_color="transparent")
            row.pack(fill="x", pady=4, padx=8)
            ctk.CTkLabel(
                row, text=label, font=("Roboto", 12),
                width=180, anchor="w"
            ).pack(side="left")
            ctk.CTkEntry(
                row, textvariable=var, font=("Roboto", 12), width=220
            ).pack(side="left")

        _secao("NF Faturada")
        _campo("Coluna volume faturado:", self.col_fat_volume)
        _campo("Coluna consumo próprio:", self.col_fat_consumo)
        _campo("Valor consumo próprio:", self.val_fat_consumo)
        _campo("Coluna CFOP (opcional):", self.col_fat_cfop)

        _secao("Canceladas / Denegadas")
        _campo("Coluna volume canceladas:", self.col_canc_volume)

        _secao("Devoluções")
        _campo("Coluna volume devoluções:", self.col_dev_volume)

        ctk.CTkLabel(
            scroll,
            text="Os nomes de arquivo devem conter as palavras:\n"
                 "  • 'faturada' ou 'complementar' → NF Faturada\n"
                 "  • 'cancelad' ou 'denegad'       → Canceladas\n"
                 "  • 'devolu'                       → Devoluções",
            font=("Roboto", 11), text_color="#606080", justify="left"
        ).pack(anchor="w", padx=8, pady=(16, 4))

    # ──────────────────────────────────────────────────────────────────────────
    # Aba Logs
    # ──────────────────────────────────────────────────────────────────────────
    def _build_aba_logs(self):
        tab = self.tabview.tab("Logs")
        self.log_text = ctk.CTkTextbox(tab, font=("Consolas", 11))
        self.log_text.pack(fill="both", expand=True, padx=6, pady=6)
        self._log("Sistema CGF iniciado. Selecione os arquivos e clique em PROCESSAR.")

    # ──────────────────────────────────────────────────────────────────────────
    # SELETOR DE PERÍODO — idêntico ao tela_ret.py
    # ──────────────────────────────────────────────────────────────────────────
    def _setup_seletor_periodo(self, parent):
        agora = datetime.now()
        self._mes_sel  = agora.month
        self._ano_sel  = agora.year
        self._btns_mes = {}
        self._periodo_manual = False

        ctk.CTkLabel(
            parent, text="Período de Referência",
            font=("Roboto", 13, "bold")
        ).pack(pady=(14, 4), padx=20, anchor="w")

        card = ctk.CTkFrame(parent, fg_color="#12122a", corner_radius=10)
        card.pack(fill="x", padx=14, pady=(0, 8))

        ano_row = ctk.CTkFrame(card, fg_color="transparent")
        ano_row.pack(pady=(10, 6), padx=14)

        ctk.CTkButton(
            ano_row, text="◀", width=32, height=28,
            fg_color="#1a3a5c", hover_color="#2e6da4",
            font=("Roboto", 13, "bold"),
            command=self._ano_anterior
        ).pack(side="left", padx=(0, 6))

        self.lbl_ano = ctk.CTkLabel(
            ano_row, text=str(self._ano_sel),
            font=("Roboto", 18, "bold"), width=70, text_color="#00d9ff"
        )
        self.lbl_ano.pack(side="left")

        ctk.CTkButton(
            ano_row, text="▶", width=32, height=28,
            fg_color="#1a3a5c", hover_color="#2e6da4",
            font=("Roboto", 13, "bold"),
            command=self._ano_proximo
        ).pack(side="left", padx=(6, 0))

        grade = ctk.CTkFrame(card, fg_color="transparent")
        grade.pack(padx=10, pady=(0, 10))

        for i, abrev in enumerate(self._MESES_ABREV):
            num = i + 1
            btn = ctk.CTkButton(
                grade, text=abrev, width=72, height=32,
                font=("Roboto", 12, "bold"),
                command=lambda m=num: self._selecionar_mes(m)
            )
            btn.grid(row=i // 3, column=i % 3, padx=4, pady=3)
            self._btns_mes[num] = btn

        self.lbl_periodo_sel = ctk.CTkLabel(
            card, text="", font=("Roboto", 12, "bold"), text_color="#f1c40f"
        )
        self.lbl_periodo_sel.pack(pady=(0, 8))

        self._atualizar_visual_meses()

    def _selecionar_mes(self, mes: int):
        self._mes_sel = mes
        self._periodo_manual = True
        self._atualizar_visual_meses()

    def _ano_anterior(self):
        self._ano_sel -= 1
        self.lbl_ano.configure(text=str(self._ano_sel))
        self._atualizar_visual_meses()

    def _ano_proximo(self):
        self._ano_sel += 1
        self.lbl_ano.configure(text=str(self._ano_sel))
        self._atualizar_visual_meses()

    def _atualizar_visual_meses(self):
        for num, btn in self._btns_mes.items():
            if num == self._mes_sel:
                btn.configure(fg_color="#2196F3", hover_color="#1976D2", text_color="white")
            else:
                btn.configure(fg_color="#1e2a3a", hover_color="#2e3f55", text_color="#a0c4e0")
        periodo = f"{self._MESES_ABREV[self._mes_sel - 1]}/{self._ano_sel}"
        self.lbl_periodo_sel.configure(text=f"✔ {periodo}")

    @property
    def entry_periodo(self):
        class _FakePeriodo:
            def __init__(self_, val): self_._v = val
            def get(self_): return self_._v
            def strip(self_): return self_._v
        return _FakePeriodo(
            f"{self._MESES_ABREV[self._mes_sel - 1]}/{self._ano_sel}"
        )

    @property
    def periodo_cgf(self):
        return self.entry_periodo

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────
    def _log(self, mensagem: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{timestamp}] {mensagem}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _atualizar_cgf_rs(self):
        try:
            pmpv = float(self.pmpv_manual.get().replace(",", ".").strip())
        except ValueError:
            pmpv = 0.0
        vol = self.volume_final_cgf
        self.cgf_rs = vol * pmpv
        if vol > 0 and pmpv > 0:
            self.lbl_cgf_rs.configure(
                text=f"CGF em R$:  R$ {self.cgf_rs:,.2f}",
                text_color=ui.COR_SUCESSO
            )
        else:
            self.lbl_cgf_rs.configure(
                text="CGF em R$:  --- (informe o PMPV)" if vol > 0 else "CGF em R$:  ---",
                text_color="#606080"
            )

    def _auto_detectar_periodo(self, caminho: str):
        if self._periodo_manual:
            return
        periodo_det = _periodo_do_caminho_cgf(caminho)
        if not periodo_det:
            return
        try:
            abrev, ano_str = periodo_det.split("/")
            mes_num = self._MESES_ABREV.index(abrev) + 1
            self._mes_sel = mes_num
            self._ano_sel = int(ano_str)
            self.lbl_ano.configure(text=str(self._ano_sel))
            self._atualizar_visual_meses()
            self._log(f"[AUTO] Período detectado: {periodo_det}")
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────────────
    # Ações
    # ──────────────────────────────────────────────────────────────────────────
    def select_files(self):
        paths = filedialog.askopenfilenames(
            title="Selecione as planilhas de NF",
            filetypes=[("Excel", "*.xlsx *.xls"), ("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if not paths:
            return
        self.selected_files = list(paths)
        self._periodo_manual = False

        nomes = [Path(p).name for p in self.selected_files]
        self.lbl_arquivos.configure(
            text="\n".join(f"📄 {n}" for n in nomes[:6]) +
                 (f"\n... +{len(nomes)-6} arquivo(s)" if len(nomes) > 6 else ""),
            text_color="#4CAF50"
        )
        self._log(f"{len(self.selected_files)} arquivo(s) selecionado(s).")

        for p in self.selected_files:
            self._auto_detectar_periodo(p)
            break

    def clear_files(self):
        self.selected_files = []
        self.lbl_arquivos.configure(
            text="Nenhum arquivo selecionado", text_color="#808080"
        )
        self.volume_final_cgf = 0.0
        self.cgf_rs = 0.0
        self.result_label.configure(text="0,0000 m³")
        self.lbl_volume_card.configure(text="--- m³")
        self.lbl_detalhes.configure(text="Aguardando processamento...")
        self._log("Lista de arquivos limpa.")

    def calculate_total(self):
        if not self.selected_files:
            messagebox.showwarning("Aviso", "Selecione ao menos um arquivo.")
            return

        fat_vol_col  = self.col_fat_volume.get().strip()
        fat_cons_col = self.col_fat_consumo.get().strip()
        fat_cons_val = self.val_fat_consumo.get().strip()
        canc_vol_col = self.col_canc_volume.get().strip()
        dev_vol_col  = self.col_dev_volume.get().strip()

        if not fat_vol_col:
            messagebox.showerror("Erro", "Informe a coluna de volume da NF Faturada.")
            return

        self.log_text.configure(state="normal")
        self.log_text.delete("0.0", "end")
        self.log_text.configure(state="disabled")
        self._log("INICIANDO PROCESSAMENTO " + "─" * 30)

        resultado = self.servicos.processar_arquivos(
            self.selected_files, fat_vol_col, fat_cons_col,
            fat_cons_val, canc_vol_col, dev_vol_col
        )
        self._ultimo_resultado_cgf = resultado

        for linha in resultado["logs"]:
            self._log(linha)

        self.volume_final_cgf = resultado["volume_final"]
        vol_fmt = f"{self.volume_final_cgf:,.4f} m³"

        self.result_label.configure(text=vol_fmt)
        self.lbl_volume_card.configure(text=vol_fmt)

        fat  = resultado.get("volume_faturado", 0.0)
        canc = resultado.get("volume_canceladas", 0.0)
        dev  = resultado.get("volume_devolucoes", 0.0)
        cons = resultado.get("volume_consumo_proprio", 0.0)
        self.lbl_detalhes.configure(
            text=f"(+) Faturado:       {fat:,.4f} m³\n"
                 f"(-) Canceladas:     {canc:,.4f} m³\n"
                 f"(-) Devoluções:     {dev:,.4f} m³\n"
                 f"(-) Cons. Próprio:  {cons:,.4f} m³"
        )

        self._atualizar_cgf_rs()
        # Só carrega PMPV do banco se o usuário não digitou nada
        if not self.pmpv_manual.get().strip():
            self._carregar_pmpv_banco(silencioso=True)
        self.tabview.set("Resumo")
        self._log("Processamento concluído.")

    def _carregar_pmpv_banco(self, silencioso: bool = False):
        periodo = self.entry_periodo.get()
        if not periodo:
            if not silencioso:
                messagebox.showwarning("Aviso", "Selecione o período de referência.")
            return
        try:
            pmpv = self.servicos.buscar_pmpv(periodo)
            if pmpv is None:
                if not silencioso:
                    messagebox.showwarning("Não encontrado", f"Nenhum PMPV salvo para '{periodo}'.")
            else:
                self.pmpv_manual.set(f"{pmpv:.4f}")
                self._atualizar_cgf_rs()
        except Exception as e:
            if not silencioso:
                messagebox.showerror("Erro", f"Erro ao acessar BD: {e}")
        self._carregar_vp_banco(periodo, silencioso=True)

    def _carregar_vp_banco(self, periodo: str, silencioso: bool = True):
        try:
            db = DatabasePMPV()
            try:
                sr_row = db.buscar_sr(periodo)
            finally:
                db.fechar()
            vp_mensal = float(sr_row["vp"]) if sr_row and sr_row.get("vp") else None
            if vp_mensal is not None:
                self.lbl_vp_mensal.configure(
                    text=f"Mensal: {vp_mensal:,.0f} m³".replace(",", ".")
                )
                self.lbl_vp_trimestral.configure(
                    text=f"Trimestral (×3): {vp_mensal * 3:,.0f} m³".replace(",", ".")
                )
            else:
                self.lbl_vp_mensal.configure(text="Mensal: sem dados")
                self.lbl_vp_trimestral.configure(text="Trimestral: sem dados")
        except Exception:
            pass

    def _salvar_cgf_scg(self):
        if self.volume_final_cgf == 0.0:
            messagebox.showwarning("Aviso", "Execute o cálculo de volume antes de salvar.")
            return

        if self.cgf_rs == 0.0:
            resp = messagebox.askyesno(
                "PMPV não informado",
                "Deseja salvar apenas o volume (sem multiplicar pelo PMPV)?"
            )
            if not resp:
                return
            valor_salvar = self.volume_final_cgf
        else:
            valor_salvar = self.cgf_rs

        periodo = self.entry_periodo.get()

        tipo_label = "Volume × PMPV" if self.cgf_rs > 0 else "Volume bruto"
        if not messagebox.askyesno(
            "Confirmar salvamento",
            f"Salvar CGF no banco de dados?\n\n"
            f"Período: {periodo}\n"
            f"Tipo: {tipo_label}\n"
            f"Valor: {valor_salvar:,.2f}\n"
            f"Volume Final: {self.volume_final_cgf:,.4f} m³"
        ):
            return

        try:
            rpv = self.servicos.salvar_cgf(periodo, valor_salvar)
            resumo = self._ultimo_resultado_cgf
            db = DatabasePMPV()
            try:
                db.salvar_cgf_resumo(
                    periodo,
                    resumo.get("volume_faturado", 0.0),
                    resumo.get("volume_canceladas", 0.0),
                    resumo.get("volume_devolucoes", 0.0),
                    resumo.get("volume_consumo_proprio", 0.0),
                    resumo.get("volume_final", self.volume_final_cgf),
                )
            finally:
                db.fechar()
            tipo = "R$ (Volume × PMPV)" if self.cgf_rs > 0 else "volume bruto (sem PMPV)"
            messagebox.showinfo(
                "CGF Salvo ✅",
                f"Período: {periodo}\n"
                f"CGF ({tipo}): {valor_salvar:,.2f}\n"
                f"RPV = R$ {rpv:,.2f}"
            )
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gravar no BD: {e}")

    def _adicionar_excel_final(self):
        if self.volume_final_cgf == 0.0:
            messagebox.showwarning("Aviso", "Execute o cálculo de volume antes de adicionar ao Excel final.")
            return

        if self.cgf_rs == 0.0:
            resp = messagebox.askyesno(
                "PMPV não informado",
                "Deseja usar apenas o volume (sem PMPV) para salvar no módulo 9?"
            )
            if not resp:
                return
            valor_salvar = self.volume_final_cgf
        else:
            valor_salvar = self.cgf_rs

        periodo = self.entry_periodo.get()

        try:
            self.servicos.salvar_cgf(periodo, valor_salvar)
            resumo = self._ultimo_resultado_cgf
            db = DatabasePMPV()
            try:
                db.salvar_cgf_resumo(
                    periodo,
                    resumo.get("volume_faturado", 0.0),
                    resumo.get("volume_canceladas", 0.0),
                    resumo.get("volume_devolucoes", 0.0),
                    resumo.get("volume_consumo_proprio", 0.0),
                    resumo.get("volume_final", self.volume_final_cgf),
                )
            finally:
                db.fechar()

            meta_execucao = registrar_execucao_excel_final(
                etapa="CGF", periodo=periodo, parent=self
            )
            if not meta_execucao:
                return
            destino, nome_sessao, periodo_norm, execucao = meta_execucao
            meses_tri = obter_periodos_trimestre(periodo_norm)
            arquivo = ExcelConsolidado.exportar(
                periodo=periodo_norm,
                nome_arquivo=destino,
                periodos_trimestre=meses_tri,
            )
            meses_txt = " | ".join(meses_tri) if meses_tri else periodo_norm
            messagebox.showinfo(
                "Excel Final gerado ✅",
                f"Arquivo: {arquivo}\n"
                f"Trimestre: {meses_txt}\n"
                f"Execução #{execucao}"
            )
        except Exception as e:
            messagebox.showerror("Erro — Módulo 9", f"Falha ao adicionar ao Excel Final:\n\n{e}")
