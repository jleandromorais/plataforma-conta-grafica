import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
import threading
from queue import Queue, Empty
import pandas as pd

from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Services.comparador_conta_grafica import ComparadorContaGrafica
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem, PIS_COFINS_RATE
from Src.Services.excel_auditoria import ExcelAuditoria
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.common.excel_final_destino import registrar_execucao_excel_final, obter_periodos_trimestre
from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

# Mapeando variavel de controle para facilitar
PDF_ATIVADO = True # Assumimos True se pdfplumber estiver instalado
OCR_ATIVADO = OCR_ENABLED

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
        self.periodo_comparacao_var.trace_add("write", lambda *_: self._verificar_habilitacao())

        self._setup_ui()
    
    def _setup_ui(self):
        header = ctk.CTkFrame(self, height=60, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🔍 Auditoria XML Fiscal", 
                     font=("Roboto", 24, "bold")).pack(side="left", padx=20, pady=10)
        
        # Área rolável: concentra os blocos de configuração e resultados.
        # Em telas menores/escala alta do Windows, isso evita "empurrar" botões para fora.
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=(12, 8))
        
        # ========== PASSO 1: PASTA PAI ==========
        frame_pasta = ctk.CTkFrame(container)
        frame_pasta.pack(fill="x", pady=10)
        
        ctk.CTkLabel(frame_pasta, text="📁 Passo 1: Selecione a pasta PAI com subpastas de empresas",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(frame_pasta, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(btn_frame, text="📂 Selecionar Pasta", 
                      command=self.selecionar_pasta,
                      fg_color="#3498db", hover_color="#2980b9").pack(side="left", padx=5)
        
        self.lbl_pasta = ctk.CTkLabel(btn_frame, text="Nenhuma pasta selecionada", text_color="gray")
        self.lbl_pasta.pack(side="left", padx=10)
        
        # ========== PASSO 2: EMPRESAS ==========
        frame_empresas = ctk.CTkFrame(container)
        frame_empresas.pack(fill="x", pady=10)
        
        ctk.CTkLabel(frame_empresas, text="🏢 Passo 2: Selecione as empresas para auditar",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        self.scroll_empresas = ctk.CTkScrollableFrame(frame_empresas, height=120)
        self.scroll_empresas.pack(fill="x", padx=10, pady=5)
        
        self.checkboxes_empresas = []
        
        # ========== PASSO 3: EXCEL E PERÍODO ==========
        frame_excel = ctk.CTkFrame(container)
        frame_excel.pack(fill="x", pady=10)

        ctk.CTkLabel(frame_excel, text="📊 Passo 3: Selecione o Excel e o período (opcional para comparar)",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=(5, 2))

        frame_tipo_excel = ctk.CTkFrame(frame_excel, fg_color="transparent")
        frame_tipo_excel.pack(fill="x", padx=10, pady=(0, 4))
        ctk.CTkLabel(frame_tipo_excel, text="Tipo:", font=("Roboto", 12)).pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(frame_tipo_excel, text="Conta Gráfica", variable=self.tipo_excel_var,
                           value="conta_grafica", font=("Roboto", 12)).pack(side="left", padx=6)
        ctk.CTkRadioButton(frame_tipo_excel, text="Outra planilha", variable=self.tipo_excel_var,
                           value="outra", font=("Roboto", 12)).pack(side="left", padx=6)

        btn_excel_frame = ctk.CTkFrame(frame_excel, fg_color="transparent")
        btn_excel_frame.pack(fill="x", padx=10, pady=3)
        ctk.CTkButton(btn_excel_frame, text="📄 Selecionar Excel",
                      command=self.selecionar_excel,
                      fg_color="#27ae60", hover_color="#2ecc71").pack(side="left", padx=5)
        self.lbl_excel = ctk.CTkLabel(btn_excel_frame, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_excel.pack(side="left", padx=10)

        frame_periodo_excel = ctk.CTkFrame(frame_excel, fg_color="transparent")
        frame_periodo_excel.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkLabel(frame_periodo_excel, text="Mês/Ano:", font=("Roboto", 12)).pack(side="left", padx=(0, 6))
        self.entry_periodo_comparacao = ctk.CTkEntry(
            frame_periodo_excel,
            placeholder_text="jan26  ou  jan/2026",
            width=190,
            textvariable=self.periodo_comparacao_var,
        )
        self.entry_periodo_comparacao.pack(side="left", padx=4)
        ctk.CTkLabel(frame_periodo_excel, text="(para comparação de notas)",
                     text_color="gray", font=("Roboto", 11)).pack(side="left", padx=4)
        
        # ========== PAINEL: MODO DE LEITURA ==========
        frame_modo = ctk.CTkFrame(container)
        frame_modo.pack(fill="x", pady=(5, 0))

        ctk.CTkLabel(frame_modo, text="📂 Fonte dos dados:",
                     font=("Roboto", 13, "bold")).pack(side="left", padx=(12, 6), pady=8)

        rb_xml = ctk.CTkRadioButton(frame_modo, text="XML", variable=self.modo_fonte, value="XML",
                                    font=("Roboto", 13), command=self._atualizar_badge_modo)
        rb_xml.pack(side="left", padx=6, pady=8)

        rb_pdf = ctk.CTkRadioButton(frame_modo, text="PDF (OCR)", variable=self.modo_fonte, value="PDF",
                                    font=("Roboto", 13), command=self._atualizar_badge_modo,
                                    state="normal" if PDF_ATIVADO else "disabled")
        rb_pdf.pack(side="left", padx=6, pady=8)

        _tess_txt   = "🟢 Tesseract ativo"  if OCR_ATIVADO else "🔴 Tesseract inativo"
        _tess_color = "#27ae60"             if OCR_ATIVADO else "#e74c3c"
        self.lbl_tesseract = ctk.CTkLabel(frame_modo, text=_tess_txt, font=("Roboto", 12, "bold"), 
                                          text_color=_tess_color, fg_color="#2c2c2c", corner_radius=8)
        self.lbl_tesseract.pack(side="right", padx=12, pady=8)

        self.lbl_modo_badge = ctk.CTkLabel(frame_modo, text="Modo: XML", font=("Roboto", 12, "bold"), 
                                           text_color="#3498db", fg_color="#2c2c2c", corner_radius=8)
        self.lbl_modo_badge.pack(side="right", padx=6, pady=8)

        # ========== ÁREA DE STATUS ==========
        frame_status = ctk.CTkFrame(container, fg_color="#1a1a1a")
        frame_status.pack(fill="x", pady=10)
        
        self.lbl_status = ctk.CTkLabel(frame_status, text="Aguardando seleções...",
                                       font=("Roboto", 14), text_color="#f39c12")
        self.lbl_status.pack(pady=15)
        self.progress_auditoria = ctk.CTkProgressBar(frame_status, mode="indeterminate")
        self.progress_auditoria.pack(fill="x", padx=14, pady=(0, 12))
        self.progress_auditoria.set(0)
        
        # ========== PAINEL CGR ==========
        frame_cgr = ctk.CTkFrame(container, fg_color="#0d1b2a", corner_radius=10)
        frame_cgr.pack(fill="x", pady=(8, 2))

        ctk.CTkLabel(frame_cgr, text="CGR APURADO", font=("Roboto", 11, "bold"), text_color="#7fb3d3").pack(side="left", padx=(14, 6), pady=8)
        self.lbl_cgr_bruto = ctk.CTkLabel(frame_cgr, text="Σ Bruto: —", font=("Consolas", 12), text_color="#aaaaaa")
        self.lbl_cgr_bruto.pack(side="left", padx=10, pady=8)
        self.lbl_cgr_icms = ctk.CTkLabel(frame_cgr, text="ICMS: —", font=("Consolas", 12), text_color="#e67e22")
        self.lbl_cgr_icms.pack(side="left", padx=10, pady=8)
        self.lbl_cgr_liquido = ctk.CTkLabel(frame_cgr, text="CGR Líquido: —", font=("Roboto", 14, "bold"), text_color="#2ecc71")
        self.lbl_cgr_liquido.pack(side="right", padx=18, pady=8)

        # ========== ÁREA DE RESULTADOS ==========
        frame_resultados = ctk.CTkFrame(container)
        frame_resultados.pack(fill="both", expand=False, pady=(4, 10), padx=0)
        
        ctk.CTkLabel(frame_resultados, text="📋 Resultados da Auditoria", font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        self.text_resultados = ctk.CTkTextbox(frame_resultados, height=150, font=("Consolas", 11))
        self.text_resultados.pack(fill="both", expand=False, padx=10, pady=5)

        # ========== BOTÕES DE AÇÃO (RODAPÉ FIXO) ==========
        # Ficam fora do container rolável para permanecerem sempre visíveis.
        rodape_acoes = ctk.CTkFrame(self, fg_color="transparent")
        rodape_acoes.pack(fill="x", padx=20, pady=(0, 12))

        frame_btns = ctk.CTkFrame(rodape_acoes, fg_color="transparent")
        frame_btns.pack(fill="x", pady=(0, 6))

        self.btn_auditar = ctk.CTkButton(frame_btns, text="📊 EXECUTAR AUDITORIA", command=self.iniciar_auditoria,
                                         font=("Roboto", 14, "bold"), height=42, fg_color="#1a5276", hover_color="#2e86c1", state="disabled")
        self.btn_auditar.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.btn_somatorio = ctk.CTkButton(frame_btns, text="📊 SÓ SOMATÓRIO", command=self.calcular_somatorio,
                                           font=("Roboto", 13, "bold"), height=42, fg_color="#2980b9", hover_color="#3498db", state="disabled")
        self.btn_somatorio.pack(side="left", expand=True, fill="x", padx=(8, 0))

        self.btn_salvar_scg = ctk.CTkButton(rodape_acoes, text="💾 SALVAR RESULTADO NO SCG", command=self._salvar_cgr_scg,
                                            font=("Roboto", 13, "bold"), height=38, fg_color="#27ae60", hover_color="#1e8449", state="disabled")
        self.btn_salvar_scg.pack(fill="x", pady=(0, 8))

        self.btn_excel_final = ctk.CTkButton(
            rodape_acoes,
            text="➕ Adicionar ao Excel Final (Módulo 9)",
            command=self._adicionar_excel_final,
            font=("Roboto", 13, "bold"),
            height=38,
            fg_color="#6c3483",
            hover_color="#884ea0",
            state="disabled",
        )
        self.btn_excel_final.pack(fill="x", pady=(0, 8))
    
    # --- HELPERS ---
    def _atualizar_badge_modo(self):
        modo = self.modo_fonte.get()
        if modo == "XML":
            self.lbl_modo_badge.configure(text="Modo: XML", text_color="#3498db")
        else:
            cor = "#27ae60" if OCR_ATIVADO else "#e74c3c"
            aviso = "" if OCR_ATIVADO else " ⚠️ sem OCR"
            self.lbl_modo_badge.configure(text=f"Modo: PDF{aviso}", text_color=cor)

    def _atualizar_painel_cgr(self, bruto: float, icms: float, liquido: float):
        self.lbl_cgr_bruto.configure(text=f"Σ Bruto: R$ {bruto:,.2f}")
        self.lbl_cgr_icms.configure(text=f"ICMS: R$ {icms:,.2f}")
        self.lbl_cgr_liquido.configure(text=f"CGR Líquido: R$ {liquido:,.2f}")

    def _periodo_normalizado(self) -> str:
        from Src.common.periodos import normalizar_periodo

        periodo_str = self.periodo_comparacao_var.get().strip()
        return normalizar_periodo(periodo_str) if periodo_str else ""

    # --- SELEÇÃO ---
    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta PAI")
        if pasta:
            self.pasta_selecionada = Path(pasta)
            self.lbl_pasta.configure(text=f"⏳ Lendo pastas em: {pasta}", text_color="#f39c12")
            self.lbl_status.configure(text="Carregando empresas da pasta selecionada...", text_color="#f39c12")
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
            self.lbl_excel.configure(text=f"⏳ Carregando {Path(arquivo).name}...", text_color="#f39c12")
            self.lbl_status.configure(text="Lendo arquivo Excel em segundo plano...", text_color="#f39c12")
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
                    self.lbl_pasta.configure(text=f"⚠️ {pasta}", text_color="#f39c12")
                    self.lbl_status.configure(text="Nenhuma subpasta encontrada.", text_color="#f39c12")
                    messagebox.showwarning("Aviso", "Nenhuma subpasta encontrada!")
                else:
                    self.lbl_pasta.configure(text=f"✅ {pasta}", text_color="#27ae60")
                    self.lbl_status.configure(
                        text=f"{len(self.empresas_disponiveis)} empresa(s) carregadas",
                        text_color="#27ae60",
                    )
                    self._criar_checkboxes_empresas()
                self._verificar_habilitacao()
            elif tipo == "empresas_error":
                self.lbl_status.configure(text="Erro ao ler pasta selecionada", text_color="#e74c3c")
                messagebox.showerror("Erro", f"Falha ao carregar pastas:\n{msg[1]}")
            elif tipo == "excel_ok":
                _, arquivo, df = msg
                self.df_excel = df
                self.lbl_excel.configure(text=f"✅ {Path(arquivo).name}", text_color="#27ae60")
                self.lbl_status.configure(text=f"Excel: {len(self.df_excel)} linhas", text_color="#27ae60")
                self._verificar_habilitacao()
            elif tipo == "excel_error":
                self.excel_path = None
                self.df_excel = None
                self.lbl_excel.configure(text="Nenhum arquivo selecionado", text_color="gray")
                self.lbl_status.configure(text="Erro ao carregar Excel", text_color="#e74c3c")
                messagebox.showerror("Erro", f"Falha ao ler o Excel:\n{msg[1]}")

        if self._thread_carregamento and self._thread_carregamento.is_alive():
            self.after(80, self._poll_fila_carregamento)
    
    def _verificar_habilitacao(self):
        if self._processando_auditoria:
            self.btn_auditar.configure(state="disabled")
            self.btn_somatorio.configure(state="disabled")
            return

        empresas_sel = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]
        periodo_ok = bool(self._periodo_normalizado())
        excel_ok = self.df_excel is not None
        self.btn_somatorio.configure(state="normal" if self.pasta_selecionada else "disabled")
        if self.pasta_selecionada and empresas_sel:
            self.btn_auditar.configure(state="normal")
            if excel_ok and periodo_ok:
                self.lbl_status.configure(
                    text=(
                        f"Pronto para auditar: {len(empresas_sel)} empresa(s). "
                        "Comparação de divergências habilitada."
                    ),
                    text_color="#27ae60",
                )
            elif excel_ok and not periodo_ok:
                self.lbl_status.configure(
                    text=(
                        "Auditoria habilitada. Preencha Mês/Ano válido para incluir "
                        "divergências no Excel."
                    ),
                    text_color="#f39c12",
                )
            else:
                self.lbl_status.configure(
                    text="Auditoria habilitada (sem comparação com Excel).",
                    text_color="#f39c12",
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
        self.lbl_status.configure(text="Iniciando auditoria...", text_color="#f39c12")
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
            self.btn_somatorio.configure(state="disabled")
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

                sem_xml_forcar_pdf = (not usar_pdf) and (len(xmls) == 0) and (len(pdfs) > 0)
                arquivos_proc = 0

                if not usar_pdf and not sem_xml_forcar_pdf:
                    for xml_file in xmls:
                        total_xmls += 1
                        arquivos_proc += 1
                        res = self._auditar_xml(xml_file, empresa)
                        if res:
                            resultados.append(res)
                        if arquivos_proc % 25 == 0:
                            self._fila_auditoria.put(("status", f"📂 {empresa}: {arquivos_proc}/{len(xmls)} XMLs"))
                else:
                    for pdf_file in pdfs:
                        total_ocr += 1
                        arquivos_proc += 1
                        dados = RegrasAuditoria.parse_pdf_ocr(pdf_file)
                        if "erro" not in dados:
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
                            self._fila_auditoria.put(("status", f"📂 {empresa}: {arquivos_proc}/{len(pdfs)} PDFs"))

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
                self.lbl_status.configure(text=msg[1], text_color="#f39c12")
            elif tipo == "done":
                _, resultados, total_xmls, total_ocr = msg
                self.resultados = resultados
                self._alterar_estado_processamento(False)
                self.lbl_status.configure(text="✅ Auditoria concluída", text_color="#27ae60")
                self._processar_totais_e_ui(total_xmls, total_ocr)
                return
            elif tipo == "error":
                self._alterar_estado_processamento(False)
                self.lbl_status.configure(text="❌ Erro na auditoria", text_color="#e74c3c")
                messagebox.showerror("Erro", f"Falha ao processar auditoria:\n{msg[1]}")
                return

        if self._processando_auditoria:
            self.after(120, self._poll_fila_auditoria)

    def calcular_somatorio(self):
        if not self.pasta_selecionada or self._processando_auditoria:
            return

        self._alterar_estado_processamento(True)
        self.resultados.clear()
        self.text_resultados.configure(state="normal")
        self.text_resultados.delete("1.0", "end")
        self.text_resultados.insert("end", "⏳ Calculando somatório em segundo plano...\n")
        self.text_resultados.configure(state="disabled")
        self.lbl_status.configure(text="Iniciando somatório...", text_color="#f39c12")

        usar_pdf = self.modo_fonte.get() == "PDF"
        self._thread_auditoria = threading.Thread(
            target=self._worker_somatorio,
            args=(usar_pdf,),
            daemon=True,
        )
        self._thread_auditoria.start()
        self.after(120, self._poll_fila_auditoria)

    def _worker_somatorio(self, usar_pdf: bool):
        try:
            pasta = Path(self.pasta_selecionada)
            self._fila_auditoria.put(("status", "🔍 Varrendo arquivos..."))
            xmls = list({p.resolve() for p in pasta.rglob("*.xml")})
            pdfs = list({p.resolve() for p in pasta.rglob("*.pdf")})

            if not usar_pdf:
                arquivos_xml = xmls
                pastas_com_xml = {p.parent for p in xmls}
                arquivos_pdf = [p for p in pdfs if p.parent not in pastas_com_xml]
            else:
                arquivos_xml = []
                arquivos_pdf = pdfs

            resultados: list[XMLItem] = []
            total_xmls = 0
            total_ocr = 0

            for idx, xml_path in enumerate(arquivos_xml, 1):
                total_xmls += 1
                # No somatório, manter empresa agregada evita quebrar a deduplicação
                # quando o arquivo está em subpastas diferentes da mesma empresa.
                res = self._auditar_xml(xml_path, "Múltiplas")
                if res:
                    resultados.append(res)
                if idx % 30 == 0:
                    self._fila_auditoria.put(("status", f"📄 XMLs: {idx}/{len(arquivos_xml)}"))

            for idx, pdf_path in enumerate(arquivos_pdf, 1):
                total_ocr += 1
                dados = RegrasAuditoria.parse_pdf_ocr(pdf_path)
                if "erro" not in dados:
                    resultados.append(
                        XMLItem(
                            "Múltiplas",
                            dados.get("tipo", "NF-e"),
                            dados.get("numero", "N/A"),
                            dados.get("valor_total", 0.0),
                            dados.get("icms", 0.0),
                            dados.get("icms_taxa", 0.0),
                            dados.get("pis", 0.0),
                            dados.get("cofins", 0.0),
                            dados.get("volume", 0),
                            "OCR",
                            dados.get("volume_total", 0.0),
                        )
                    )
                if idx % 10 == 0:
                    self._fila_auditoria.put(("status", f"📄 PDFs: {idx}/{len(arquivos_pdf)}"))

            self._fila_auditoria.put(("done", resultados, total_xmls, total_ocr))
        except Exception as e:
            self._fila_auditoria.put(("error", str(e)))

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

        # Cálculo por documento (mesma lógica validada contra planilha Arch)
        bruto_total = sum(r.valor_total for r in self.resultados)
        icms_total_all = sum(r.valor_total * r.icms_taxa for r in self.resultados)
        self.cgr_liquido = sum(
            RegrasAuditoria.calcular_s_tributos(r.valor_total, r.icms_taxa)
            for r in self.resultados
        )
        self._atualizar_painel_cgr(self.valor_total_geral, icms_total_all, self.cgr_liquido)

        self.text_resultados.configure(state="normal")
        self.text_resultados.delete("1.0", "end")
        self.text_resultados.insert("end", f"Auditoria Concluída: {n_xmls} XMLs, {n_pdfs} PDFs\n\n")
        self.text_resultados.insert("end", f"CGR Líquido: R$ {self.cgr_liquido:,.2f}\n")
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
                    text_color="#e67e22",
                )
            else:
                self.lbl_status.configure(
                    text=f"✅ {tipo_label} ({comp.periodo}) | confirmadas: {comp.qtd_em_ambas} | divergências: {n_div}",
                    text_color="#27ae60" if comp.qtd_em_ambas > 0 else "#e67e22",
                )
            return True
        except Exception as e:
            self.comparacao_notas = None
            self.lbl_status.configure(text="⚠️ Falha ao comparar notas com o Excel", text_color="#f39c12")
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
                text_color="#27ae60",
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
                                   f"Salvar Auditoria XML no banco de dados?\n\n"
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
                db = DatabasePMPV()
                db.salvar_auditoria_itens(periodo, itens_dict)
                db.fechar()
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
        cgr = getattr(self, 'cgr_liquido', 0.0)
        if cgr == 0.0 and not self.resultados:
            messagebox.showwarning("Aviso", "Execute a auditoria antes de adicionar ao Excel final.")
            return

        periodo_salvar = self._periodo_normalizado()
        if not periodo_salvar:
            meses_auto = obter_periodos_trimestre()
            periodo_salvar = meses_auto[-1] if meses_auto else ""
        if not periodo_salvar:
            messagebox.showwarning(
                "Período não encontrado",
                "Não foi possível determinar o período automaticamente.\n"
                "Selecione o período de comparação na tela antes de adicionar ao Excel Final.",
                parent=self,
            )
            return

        try:
            periodo_salvar = periodo_salvar.strip()
            self.consolidacao.salvar_cgr(periodo_salvar, cgr)

            if self.resultados:
                itens_dict = [
                    {
                        "empresa": r.empresa,
                        "tipo": r.tipo,
                        "numero": r.numero,
                        "valor_total": r.valor_total,
                        "icms": r.icms,
                        "pis": r.pis,
                        "cofins": r.cofins,
                        "volume_total": r.volume_total,
                        "cgr_liquido": RegrasAuditoria.calcular_s_tributos(r.valor_total, r.icms_taxa),
                    }
                    for r in self.resultados
                ]
                db = DatabasePMPV()
                try:
                    db.salvar_auditoria_itens(periodo_salvar, itens_dict)
                finally:
                    db.fechar()

            meta_execucao = registrar_execucao_excel_final(etapa="Auditoria XML", periodo=periodo_salvar, parent=self)
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
            messagebox.showinfo("Excel final gerado ✅",
                f"Arquivo: {arquivo}\n"
                f"Trimestre: {meses_txt}\n"
                f"Execução #{execucao}")

        except Exception as e:
            messagebox.showerror("Erro — Módulo 9", f"Falha ao adicionar ao Excel Final:\n\n{e}")