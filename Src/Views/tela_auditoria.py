import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from pathlib import Path
from datetime import datetime
import pandas as pd

from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Services.servicos_auditoria import RegrasAuditoria, XMLItem, PIS_COFINS_CGR_RATE
from Src.Services.excel_auditoria import ExcelAuditoria
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.Database.database import DatabasePMPV

# Mapeando variavel de controle para facilitar
PDF_ATIVADO = True # Assumimos True se pdfplumber estiver instalado
OCR_ATIVADO = OCR_ENABLED

class TelaAuditoria(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("Auditoria XML - NF-e e CT-e")
        self.geometry("1300x1050")
        
        self.pasta_selecionada = None
        self.empresas_disponiveis = []
        self.empresas_selecionadas = []
        self.excel_path = None
        self.df_excel = None
        self.resultados = []

        self.valor_total_geral  = 0.0
        self.volume_total_geral = 0.0
        self.valor_total_nfe    = 0.0
        self.volume_total_nfe   = 0.0
        self.valor_total_cte    = 0.0
        self.volume_total_cte   = 0.0
        self.cgr_liquido        = 0.0
        self.consolidacao       = ServicosConsolidacao()

        self.modo_fonte = tk.StringVar(value="XML")

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
        
        # ========== PASSO 3: EXCEL ==========
        frame_excel = ctk.CTkFrame(container)
        frame_excel.pack(fill="x", pady=10)
        
        ctk.CTkLabel(frame_excel, text="📊 Passo 3: Selecione o arquivo Excel de referência",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        btn_excel_frame = ctk.CTkFrame(frame_excel, fg_color="transparent")
        btn_excel_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkButton(btn_excel_frame, text="📄 Selecionar Excel", 
                      command=self.selecionar_excel,
                      fg_color="#27ae60", hover_color="#2ecc71").pack(side="left", padx=5)
        
        self.lbl_excel = ctk.CTkLabel(btn_excel_frame, text="Nenhum arquivo selecionado", text_color="gray")
        self.lbl_excel.pack(side="left", padx=10)
        
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

        self.btn_auditar = ctk.CTkButton(frame_btns, text="⚡ AUDITORIA COMPLETA", command=self.iniciar_auditoria,
                                         font=("Roboto", 14, "bold"), height=42, fg_color="#e74c3c", hover_color="#c0392b", state="disabled")
        self.btn_auditar.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self.btn_somatorio = ctk.CTkButton(frame_btns, text="📊 SÓ SOMATÓRIO", command=self.calcular_somatorio,
                                           font=("Roboto", 13, "bold"), height=42, fg_color="#2980b9", hover_color="#3498db", state="disabled")
        self.btn_somatorio.pack(side="left", expand=True, fill="x", padx=(8, 0))

        self.btn_salvar_scg = ctk.CTkButton(rodape_acoes, text="💾 SALVAR RESULTADO NO SCG", command=self._salvar_cgr_scg,
                                            font=("Roboto", 13, "bold"), height=38, fg_color="#27ae60", hover_color="#1e8449", state="disabled")
        self.btn_salvar_scg.pack(fill="x", pady=(0, 8))
    
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

    # --- SELEÇÃO ---
    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta PAI")
        if pasta:
            self.pasta_selecionada = Path(pasta)
            self.lbl_pasta.configure(text=f"✅ {pasta}", text_color="#27ae60")
            self.empresas_disponiveis = [d.name for d in self.pasta_selecionada.iterdir() if d.is_dir()]
            if not self.empresas_disponiveis:
                messagebox.showwarning("Aviso", "Nenhuma subpasta encontrada!")
                return
            self._criar_checkboxes_empresas()
            self._verificar_habilitacao()
    
    def _criar_checkboxes_empresas(self):
        for cb in self.checkboxes_empresas: cb.destroy()
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
            self.lbl_excel.configure(text=f"✅ {Path(arquivo).name}", text_color="#27ae60")
            try:
                self.df_excel = pd.read_excel(arquivo)
                self.lbl_status.configure(text=f"Excel: {len(self.df_excel)} linhas", text_color="#27ae60")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro:\n{e}")
                return
            self._verificar_habilitacao()
    
    def _verificar_habilitacao(self):
        empresas_sel = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]
        self.btn_somatorio.configure(state="normal" if self.pasta_selecionada else "disabled")
        if self.pasta_selecionada and empresas_sel:
            self.btn_auditar.configure(state="normal")
            if self.excel_path:
                self.lbl_status.configure(
                    text=f"Pronto! {len(empresas_sel)} empresas selecionadas + Excel carregado",
                    text_color="#27ae60"
                )
            else:
                self.lbl_status.configure(
                    text=f"Pronto! {len(empresas_sel)} empresas selecionadas (sem Excel)",
                    text_color="#f39c12"
                )
        else:
            self.btn_auditar.configure(state="disabled")

    # --- LÓGICA DE EXECUÇÃO ---
    def iniciar_auditoria(self):
        self.btn_auditar.configure(state="disabled")
        self.text_resultados.delete("1.0", "end")
        self.resultados.clear()
        empresas = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]
        total_xmls = total_ocr = 0

        for empresa in empresas:
            self.text_resultados.insert("end", f"\n📂 Auditando: {empresa}\n")
            self.update()
            pasta_empresa = self.pasta_selecionada / empresa
            xmls = list({p.resolve() for p in pasta_empresa.rglob("*.xml")})
            pdfs = list({p.resolve() for p in pasta_empresa.rglob("*.pdf")})

            usar_pdf = self.modo_fonte.get() == "PDF"
            sem_xml_forcar_pdf = (not usar_pdf) and (len(xmls) == 0) and (len(pdfs) > 0)

            if not usar_pdf and not sem_xml_forcar_pdf:
                for xml_file in xmls:
                    total_xmls += 1
                    res = self._auditar_xml(xml_file, empresa)
                    if res: self.resultados.append(res)
            else:
                for pdf_file in pdfs:
                    total_ocr += 1
                    dados = RegrasAuditoria.parse_pdf_ocr(pdf_file)
                    if 'erro' in dados: continue
                    vf = dados.get('valor_total', 0.0)
                    self.resultados.append(XMLItem(
                        empresa, dados.get('tipo', 'NF-e'), dados.get('numero', 'N/A'),
                        vf, dados.get('icms', 0.0), dados.get('pis', 0.0), dados.get('cofins', 0.0),
                        dados.get('volume', 0), 'OCR', dados.get('volume_total', 0.0)
                    ))

        self._processar_totais_e_ui(total_xmls, total_ocr)

    def calcular_somatorio(self):
        if not self.pasta_selecionada: return
        self.resultados.clear()
        
        pasta = Path(self.pasta_selecionada)
        xmls = list({p.resolve() for p in pasta.rglob("*.xml")})
        pdfs = list({p.resolve() for p in pasta.rglob("*.pdf")})

        usar_pdf = self.modo_fonte.get() == "PDF"
        if not usar_pdf:
            arquivos_xml = xmls
            pastas_com_xml = {p.parent for p in xmls}
            arquivos_pdf = [p for p in pdfs if p.parent not in pastas_com_xml]
        else:
            arquivos_xml = []
            arquivos_pdf = pdfs

        for xml_path in arquivos_xml:
            res = self._auditar_xml(xml_path, "Múltiplas")
            if res: self.resultados.append(res)
            
        for pdf_path in arquivos_pdf:
             dados = RegrasAuditoria.parse_pdf_ocr(pdf_path)
             if 'erro' not in dados:
                 self.resultados.append(XMLItem("Múltiplas", dados.get('tipo', 'NF-e'), dados.get('numero', 'N/A'),
                        dados.get('valor_total', 0.0), dados.get('icms', 0.0), 0.0, 0.0,
                        dados.get('volume', 0), 'OCR', dados.get('volume_total', 0.0)))
        
        self._processar_totais_e_ui(len(arquivos_xml), len(arquivos_pdf))

    def _auditar_xml(self, xml_path: Path, empresa: str) -> XMLItem:
        tipo = RegrasAuditoria.detectar_tipo_xml(xml_path)
        if tipo == 'nfe': dados = RegrasAuditoria.parse_nfe(xml_path)
        elif tipo == 'cte': dados = RegrasAuditoria.parse_cte(xml_path)
        else: return None
        
        if 'erro' in dados: return None
        
        vol_total = dados.get('volume_total', float(dados.get('volume', 0)))
        return XMLItem(empresa, dados['tipo'], dados['numero'], dados['valor_total'],
                       dados['icms'], dados['pis'], dados['cofins'], int(vol_total), "OK", vol_total)

    def _processar_totais_e_ui(self, n_xmls, n_pdfs):
        nfes = [r for r in self.resultados if r.tipo == 'NF-e']
        ctes = [r for r in self.resultados if r.tipo == 'CT-e']

        self.valor_total_nfe    = sum(r.valor_total for r in nfes)
        self.volume_total_nfe   = sum(r.volume_total for r in nfes)
        self.valor_total_cte    = sum(r.valor_total for r in ctes)
        self.volume_total_cte   = sum(r.volume_total for r in ctes)
        self.valor_total_geral  = self.valor_total_nfe + self.valor_total_cte
        self.volume_total_geral = self.volume_total_nfe + self.volume_total_cte

        icms_total = sum(r.icms for r in self.resultados)
        self.cgr_liquido = RegrasAuditoria.calcular_cgr_liquido(self.valor_total_geral, icms_total)
        self._atualizar_painel_cgr(self.valor_total_geral, icms_total, self.cgr_liquido)

        self.text_resultados.configure(state="normal")
        self.text_resultados.delete("1.0", "end")
        self.text_resultados.insert("end", f"Auditoria Concluída: {n_xmls} XMLs, {n_pdfs} PDFs\n\n")
        self.text_resultados.insert("end", f"CGR Líquido: R$ {self.cgr_liquido:,.2f}\n")
        self.text_resultados.configure(state="disabled")

        self.btn_salvar_scg.configure(state="normal")
        if self.excel_path and messagebox.askyesno("Exportar", "Gerar relatório Excel?"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ExcelAuditoria.gerar_relatorio_auditoria(self.resultados, f"Auditoria_{timestamp}.xlsx")

    def _salvar_cgr_scg(self):
        cgr = getattr(self, 'cgr_liquido', 0.0)
        periodo = simpledialog.askstring("Salvar", "Período (ex: Dez/2025):", initialvalue="Dez/2025")
        if not periodo:
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
                    "cgr_liquido": RegrasAuditoria.calcular_cgr_liquido(r.valor_total, r.icms),
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