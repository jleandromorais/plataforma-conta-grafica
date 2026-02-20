import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

# Configuração Visual
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ==========================================
# CLASSES DE DADOS
# ==========================================

class XMLItem:
    """Representa um item auditado de XML fiscal"""
    def __init__(self, empresa: str, tipo: str, numero: str, valor_total: float, 
                 icms: float, pis: float, cofins: float, volume: int, status: str,volume_total:float):
        self.empresa = empresa
        self.tipo = tipo  # NF-e ou CT-e
        self.numero = numero
        self.valor_total = valor_total
        self.icms = icms
        self.pis = pis
        self.cofins = cofins
        self.volume = volume
        self.status = status
        self.volume_total = volume_total

# ==========================================
# FUNÇÕES DE PARSE XML
# ==========================================

def parse_nfe(xml_path: Path) -> Dict:
    """Extrai dados de uma NF-e.

    Valor : total/ICMSTot/vNF  (padrão SEFAZ, igual em todas as empresas)
    Volume: soma de qCom nos itens onde uCom = M3 — campo mais confiável para
            gás natural. vol/qVol representa volumes de embalagem (caixas,
            paletes) e está incorreto para gás.
    Fallback 1 → vol/qVol  (caso não haja itens M3)
    Fallback 2 → vol/pesoL (último recurso)
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}

        numero     = root.find('.//nfe:ide/nfe:nNF', ns)
        valor_tag  = root.find('.//nfe:total/nfe:ICMSTot/nfe:vNF', ns)
        # vNFTot inclui IBS/CBS (tributos 2026); se presente, usar como total
        valor_ext  = root.find('.//nfe:total/nfe:vNFTot', ns)
        icms       = root.find('.//nfe:total/nfe:ICMSTot/nfe:vICMS', ns)
        pis        = root.find('.//nfe:total/nfe:ICMSTot/nfe:vPIS', ns)
        cofins     = root.find('.//nfe:total/nfe:ICMSTot/nfe:vCOFINS', ns)

        # Volume M3: soma qCom dos itens cujo uCom é metro cúbico
        UNIDADES_M3 = {'M3', 'M³', 'M 3', 'M3.'}
        vol_m3 = 0.0
        for det in root.findall('.//nfe:det', ns):
            u_com = det.find('nfe:prod/nfe:uCom', ns)
            q_com = det.find('nfe:prod/nfe:qCom', ns)
            if u_com is not None and q_com is not None:
                if u_com.text.strip().upper() in UNIDADES_M3:
                    try:
                        vol_m3 += float(q_com.text)
                    except Exception:
                        pass

        # Fallback 1: vol/qVol
        if vol_m3 == 0.0:
            for vol in root.findall('.//nfe:vol', ns):
                q_vol = vol.find('nfe:qVol', ns)
                if q_vol is not None and q_vol.text:
                    try:
                        vol_m3 += float(q_vol.text)
                    except Exception:
                        pass

        # Fallback 2: pesoL do <vol>
        if vol_m3 == 0.0:
            peso = root.find('.//nfe:vol/nfe:pesoL', ns)
            if peso is not None and peso.text:
                try:
                    vol_m3 = float(peso.text)
                except Exception:
                    pass

        valor = (float(valor_ext.text) if valor_ext is not None else
                 float(valor_tag.text) if valor_tag is not None else 0.0)

        return {
            'tipo': 'NF-e',
            'numero': numero.text if numero is not None else 'N/A',
            'valor_total': valor,
            'icms':   float(icms.text)   if icms   is not None else 0.0,
            'pis':    float(pis.text)    if pis    is not None else 0.0,
            'cofins': float(cofins.text) if cofins is not None else 0.0,
            'volume_total': vol_m3,
            'volume': int(vol_m3),  # retrocompatibilidade
        }
    except Exception as e:
        return {'erro': str(e)}

def parse_cte(xml_path: Path) -> Dict:
    """Extrai dados de um CT-e.

    Valor : vPrest/vTPrest  (padrão SEFAZ para CT-e)
    Volume: infQ/qCarga onde cUnid='00' (M3) tem prioridade.
            Tabela cUnid CT-e: 00=M3, 01=KG, 02=TON, 03=Un, 04=L, 05=MMBTU
            Se não houver M3, usa o primeiro qCarga > 0 disponível.
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        ns = {'cte': 'http://www.portalfiscal.inf.br/cte'}

        numero      = root.find('.//cte:ide/cte:nCT', ns)
        valor_total = root.find('.//cte:vPrest/cte:vTPrest', ns)
        icms        = root.find('.//cte:ICMS//cte:vICMS', ns)
        pis         = root.find('.//cte:vPIS', ns)
        cofins      = root.find('.//cte:vCOFINS', ns)

        # Volume: prioridade para cUnid='00' (M3)
        vol_m3 = 0.0
        unid_encontrada = ''

        for infQ in root.findall('.//cte:infQ', ns):
            c_unid  = infQ.find('cte:cUnid', ns)
            q_carga = infQ.find('cte:qCarga', ns)
            if c_unid is not None and q_carga is not None and c_unid.text == '00':
                try:
                    v = float(q_carga.text)
                    if v > 0:
                        vol_m3 = v
                        unid_encontrada = 'M3'
                        break
                except Exception:
                    pass

        # Fallback: qualquer infQ com qCarga > 0
        if vol_m3 == 0.0:
            for infQ in root.findall('.//cte:infQ', ns):
                q_carga = infQ.find('cte:qCarga', ns)
                c_unid  = infQ.find('cte:cUnid', ns)
                tp_med  = infQ.find('cte:tpMed', ns)
                if q_carga is not None:
                    try:
                        v = float(q_carga.text)
                        if v > 0:
                            vol_m3 = v
                            unid_encontrada = (tp_med.text if tp_med is not None else
                                               c_unid.text if c_unid is not None else '?')
                            break
                    except Exception:
                        pass

        return {
            'tipo': 'CT-e',
            'numero': numero.text if numero is not None else 'N/A',
            'valor_total': float(valor_total.text) if valor_total is not None else 0.0,
            'icms':   float(icms.text)   if icms   is not None else 0.0,
            'pis':    float(pis.text)    if pis    is not None else 0.0,
            'cofins': float(cofins.text) if cofins is not None else 0.0,
            'volume_total': vol_m3,
            'unidade_volume': unid_encontrada,
            'volume': int(vol_m3),  # retrocompatibilidade
        }
    except Exception as e:
        return {'erro': str(e)}

def detectar_tipo_xml(xml_path: Path) -> str:
    """Detecta se é NF-e ou CT-e pelo conteúdo"""
    try:
        with open(xml_path, 'r', encoding='utf-8') as f:
            conteudo = f.read(500)  # Lê só o início
            if 'nfeProc' in conteudo or 'NFe' in conteudo:
                return 'nfe'
            elif 'cteProc' in conteudo or 'CTe' in conteudo:
                return 'cte'
    except:
        pass
    return 'desconhecido'

# ==========================================
# INTERFACE GRÁFICA
# ==========================================

class AppAuditoriaXML(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("Auditoria XML - NF-e e CT-e")
        self.geometry("1300x850")
        
        # Variáveis de controle
        self.pasta_selecionada = None
        self.empresas_disponiveis = []
        self.empresas_selecionadas = []
        self.excel_path = None
        self.df_excel = None
        self.resultados = []

        # Somatórios — disponíveis após a auditoria para cálculos posteriores
        self.valor_total_geral  = 0.0   # soma valor de TODOS os documentos
        self.volume_total_geral = 0.0   # soma volume de TODOS os documentos
        self.valor_total_nfe    = 0.0   # soma valor somente das NF-e
        self.volume_total_nfe   = 0.0   # soma volume somente das NF-e
        self.valor_total_cte    = 0.0   # soma valor somente dos CT-e
        self.volume_total_cte   = 0.0   # soma volume somente dos CT-e
        
        self._setup_ui()
    
    def _setup_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, height=60, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="🔍 Auditoria XML Fiscal", 
                     font=("Roboto", 24, "bold")).pack(side="left", padx=20, pady=10)
        
        # CONTAINER PRINCIPAL
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=20)
        
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
        
        self.lbl_pasta = ctk.CTkLabel(btn_frame, text="Nenhuma pasta selecionada", 
                                      text_color="gray")
        self.lbl_pasta.pack(side="left", padx=10)
        
        # ========== PASSO 2: EMPRESAS ==========
        frame_empresas = ctk.CTkFrame(container)
        frame_empresas.pack(fill="x", pady=10)
        
        ctk.CTkLabel(frame_empresas, text="🏢 Passo 2: Selecione as empresas para auditar",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # Frame com scroll para empresas
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
        
        self.lbl_excel = ctk.CTkLabel(btn_excel_frame, text="Nenhum arquivo selecionado",
                                      text_color="gray")
        self.lbl_excel.pack(side="left", padx=10)
        
        # ========== ÁREA DE STATUS ==========
        frame_status = ctk.CTkFrame(container, fg_color="#1a1a1a")
        frame_status.pack(fill="x", pady=10)
        
        self.lbl_status = ctk.CTkLabel(frame_status, text="Aguardando seleções...",
                                       font=("Roboto", 14), text_color="#f39c12")
        self.lbl_status.pack(pady=15)
        
        # ========== BOTÕES DE AÇÃO (lado a lado) ==========
        frame_btns = ctk.CTkFrame(container, fg_color="transparent")
        frame_btns.pack(fill="x", pady=20)

        # Botão 1: Auditoria completa (precisa pasta + empresas + Excel)
        self.btn_auditar = ctk.CTkButton(frame_btns, text="⚡ AUDITORIA COMPLETA",
                                         command=self.iniciar_auditoria,
                                         font=("Roboto", 15, "bold"),
                                         height=50,
                                         fg_color="#e74c3c", hover_color="#c0392b",
                                         state="disabled")
        self.btn_auditar.pack(side="left", expand=True, fill="x", padx=(0, 8))

        # Botão 2: Só somatório (precisa só da pasta)
        self.btn_somatorio = ctk.CTkButton(frame_btns, text="📊 SÓ SOMATÓRIO\n(Valor e Volume das NFs/CTes)",
                                           command=self.calcular_somatorio,
                                           font=("Roboto", 13, "bold"),
                                           height=50,
                                           fg_color="#2980b9", hover_color="#3498db",
                                           state="disabled")
        self.btn_somatorio.pack(side="left", expand=True, fill="x", padx=(8, 0))

        # Botão 3: Salvar resultado no SCG (habilitado após auditoria ou somatório)
        self.btn_salvar_scg = ctk.CTkButton(
            container, text="💾 SALVAR RESULTADO NO SCG",
            command=self._salvar_cgr_scg,
            font=("Roboto", 13, "bold"),
            height=40,
            fg_color="#27ae60", hover_color="#1e8449",
            state="disabled",
        )
        self.btn_salvar_scg.pack(fill="x", pady=(0, 5))

        # ========== ÁREA DE RESULTADOS ==========
        frame_resultados = ctk.CTkFrame(container)
        frame_resultados.pack(fill="both", expand=True, pady=10)
        
        ctk.CTkLabel(frame_resultados, text="📋 Resultados da Auditoria",
                     font=("Roboto", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        self.text_resultados = ctk.CTkTextbox(frame_resultados, height=200,
                                              font=("Consolas", 11))
        self.text_resultados.pack(fill="both", expand=True, padx=10, pady=5)
    
    # ==========================================
    # FUNÇÕES DE SELEÇÃO
    # ==========================================
    
    def selecionar_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta PAI com empresas")
        if pasta:
            self.pasta_selecionada = Path(pasta)
            self.lbl_pasta.configure(text=f"✅ {pasta}", text_color="#27ae60")
            
            # Detectar subpastas (empresas)
            self.empresas_disponiveis = [d.name for d in self.pasta_selecionada.iterdir() 
                                         if d.is_dir()]
            
            if not self.empresas_disponiveis:
                messagebox.showwarning("Aviso", "Nenhuma subpasta de empresa encontrada!")
                return
            
            self._criar_checkboxes_empresas()
            self._verificar_habilitacao()
    
    def _criar_checkboxes_empresas(self):
        # Limpar checkboxes antigos
        for cb in self.checkboxes_empresas:
            cb.destroy()
        self.checkboxes_empresas.clear()
        
        # Criar novos
        for empresa in self.empresas_disponiveis:
            var = tk.BooleanVar(value=True)
            cb = ctk.CTkCheckBox(self.scroll_empresas, text=empresa, variable=var,
                                 command=self._verificar_habilitacao)
            cb.pack(anchor="w", padx=10, pady=3)
            self.checkboxes_empresas.append((empresa, var, cb))
    
    def selecionar_excel(self):
        arquivo = filedialog.askopenfilename(
            title="Selecione o Excel de referência",
            filetypes=[("Excel", "*.xlsx *.xls")]
        )
        if arquivo:
            self.excel_path = arquivo
            self.lbl_excel.configure(text=f"✅ {Path(arquivo).name}", text_color="#27ae60")
            
            # Carregar Excel
            try:
                self.df_excel = pd.read_excel(arquivo)
                self.lbl_status.configure(text=f"Excel carregado: {len(self.df_excel)} linhas",
                                         text_color="#27ae60")
            except Exception as e:
                messagebox.showerror("Erro", f"Erro ao carregar Excel:\n{e}")
                return
            
            self._verificar_habilitacao()
    
    def _verificar_habilitacao(self):
        empresas_sel = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]

        # Somatório: precisa só da pasta
        if self.pasta_selecionada:
            self.btn_somatorio.configure(state="normal")
        else:
            self.btn_somatorio.configure(state="disabled")

        # Auditoria completa: precisa de pasta + empresas + excel
        if self.pasta_selecionada and empresas_sel and self.excel_path:
            self.btn_auditar.configure(state="normal")
            self.lbl_status.configure(text=f"Pronto! {len(empresas_sel)} empresas selecionadas",
                                     text_color="#27ae60")
        else:
            self.btn_auditar.configure(state="disabled")
    
    # ==========================================
    # LÓGICA DE AUDITORIA
    # ==========================================
    
    def iniciar_auditoria(self):
        self.btn_auditar.configure(state="disabled")
        self.text_resultados.delete("1.0", "end")
        self.text_resultados.insert("1.0", "🔄 Iniciando auditoria...\n")
        self.resultados.clear()
        
        # Empresas selecionadas
        empresas = [emp for emp, var, _ in self.checkboxes_empresas if var.get()]
        
        total_xmls = 0
        
        for empresa in empresas:
            self.text_resultados.insert("end", f"\n📂 Auditando: {empresa}\n")
            self.text_resultados.see("end")
            self.update()
            
            pasta_empresa = self.pasta_selecionada / empresa
            xmls = list(pasta_empresa.rglob("*.xml")) + list(pasta_empresa.rglob("*.XML"))
            
            self.text_resultados.insert("end", f"   Encontrados: {len(xmls)} XMLs\n")
            
            for xml_file in xmls:
                total_xmls += 1
                resultado = self._auditar_xml(xml_file, empresa)
                if resultado:
                    self.resultados.append(resultado)
        
        # Resumo
        self.text_resultados.insert("end", f"\n{'='*50}\n")
        self.text_resultados.insert("end", f"✅ Auditoria concluída!\n")
        self.text_resultados.insert("end", f"   Total de XMLs: {total_xmls}\n")
        self.text_resultados.insert("end", f"   Processados: {len(self.resultados)}\n")
        
        erros = sum(1 for r in self.resultados if r.status != "OK")
        self.text_resultados.insert("end", f"   Erros/Divergências: {erros}\n")

        
        # ===== SOMATÓRIOS — prontos para cálculos posteriores =====
        nfes = [r for r in self.resultados if r.tipo == 'NF-e']
        ctes = [r for r in self.resultados if r.tipo == 'CT-e']

        self.valor_total_nfe    = sum(r.valor_total           for r in nfes)
        self.volume_total_nfe   = sum(getattr(r, 'volume', 0) for r in nfes)
        self.valor_total_cte    = sum(r.valor_total           for r in ctes)
        self.volume_total_cte   = sum(getattr(r, 'volume', 0) for r in ctes)
        self.valor_total_geral  = self.valor_total_nfe  + self.valor_total_cte
        self.volume_total_geral = self.volume_total_nfe + self.volume_total_cte

        self.text_resultados.insert("end", f"\n{'='*50}\n")
        self.text_resultados.insert("end", f"📄 NF-e  → Valor: R$ {self.valor_total_nfe:,.2f}  |  Volume: {self.volume_total_nfe:,.0f}\n")
        self.text_resultados.insert("end", f"🚚 CT-e  → Valor: R$ {self.valor_total_cte:,.2f}  |  Volume: {self.volume_total_cte:,.0f}\n")
        self.text_resultados.insert("end", f"{'─'*50}\n")
        self.text_resultados.insert("end", f"📊 TOTAL → Valor: R$ {self.valor_total_geral:,.2f}  |  Volume: {self.volume_total_geral:,.0f}\n")
        
        self.btn_auditar.configure(state="normal")
        self.btn_salvar_scg.configure(state="normal")

        # Perguntar se quer gerar relatório
        if messagebox.askyesno("Concluído", "Deseja gerar o relatório em Excel?"):
            self._gerar_relatorio()
    
    # ------------------------------------------------------------------
    # SOMATÓRIO RÁPIDO — não precisa de Excel nem de empresas selecionadas
    # ------------------------------------------------------------------
    def calcular_somatorio(self):
        """Lê todos os XMLs da pasta e exibe o somatório de valor e volume por tipo."""
        if not self.pasta_selecionada:
            messagebox.showwarning("Atenção", "Selecione uma pasta com XMLs primeiro.")
            return

        pasta = Path(self.pasta_selecionada)
        xmls = list(pasta.rglob("*.xml"))
        if not xmls:
            messagebox.showinfo("Sem arquivos", "Nenhum arquivo XML encontrado na pasta selecionada.")
            return

        self.lbl_status.configure(text=f"Calculando somatório de {len(xmls)} XML(s)…", text_color="#f39c12")
        self.update()

        val_nfe = vol_nfe = 0.0
        val_cte = vol_cte = 0.0
        erros = 0

        for xml_path in xmls:
            try:
                tipo = detectar_tipo_xml(xml_path)
                if tipo == 'nfe':
                    dados = parse_nfe(xml_path)
                    val_nfe += float(dados.get('valor_total', 0) or 0)
                    vol_nfe += float(dados.get('volume_total', 0) or 0)
                elif tipo == 'cte':
                    dados = parse_cte(xml_path)
                    val_cte += float(dados.get('valor_total', 0) or 0)
                    vol_cte += float(dados.get('volume_total', 0) or 0)
            except Exception:
                erros += 1

        # Salva nos atributos para reutilização futura
        self.valor_total_nfe    = val_nfe
        self.volume_total_nfe   = vol_nfe
        self.valor_total_cte    = val_cte
        self.volume_total_cte   = vol_cte
        self.valor_total_geral  = val_nfe + val_cte
        self.volume_total_geral = vol_nfe + vol_cte

        self.lbl_status.configure(text="Somatório calculado!", text_color="#27ae60")
        self.btn_salvar_scg.configure(state="normal")

        aviso_erros = f"\n\n⚠️ {erros} arquivo(s) não puderam ser lidos." if erros else ""

        msg = (
            f"📊  SOMATÓRIO — {len(xmls)} XML(s) processados{aviso_erros}\n"
            f"{'─' * 45}\n\n"
            f"  📄  NF-e\n"
            f"       Valor Total : R$ {val_nfe:>18,.2f}\n"
            f"       Volume Total:     {vol_nfe:>18,.2f}\n\n"
            f"  🚚  CT-e\n"
            f"       Valor Total : R$ {val_cte:>18,.2f}\n"
            f"       Volume Total:     {vol_cte:>18,.2f}\n\n"
            f"{'─' * 45}\n"
            f"  🔢  TOTAL GERAL\n"
            f"       Valor Total : R$ {self.valor_total_geral:>18,.2f}\n"
            f"       Volume Total:     {self.volume_total_geral:>18,.2f}"
        )
        messagebox.showinfo("Somatório Final", msg)

    def _auditar_xml(self, xml_path: Path, empresa: str) -> XMLItem:
        """Audita um XML individual"""
        tipo = detectar_tipo_xml(xml_path)
        
        if tipo == 'nfe':
            dados = parse_nfe(xml_path)
        elif tipo == 'cte':
            dados = parse_cte(xml_path)
        else:
            return XMLItem(empresa, "ERRO", xml_path.name, 0.0, 0.0, 0.0, 0.0, 0, "ERRO_PARSE", 0.0)
        
        if 'erro' in dados:
            return XMLItem(empresa, "ERRO", xml_path.name, 0.0, 0.0, 0.0, 0.0, 0, "ERRO_PARSE", 0.0)
        
        # Comparar com Excel (simplificado - assumindo coluna 'Numero' no Excel)
        # Na prática, você precisa fazer o match correto com suas colunas
        status = "OK"
        
        # Aqui você faria a comparação real com self.df_excel
        # Exemplo: buscar linha no Excel com mesmo número e comparar valores
        
        vol_total = dados.get('volume_total', float(dados.get('volume', 0)))
        return XMLItem(
            empresa=empresa,
            tipo=dados['tipo'],
            numero=dados['numero'],
            valor_total=dados['valor_total'],
            icms=dados['icms'],
            pis=dados['pis'],
            cofins=dados['cofins'],
            volume=int(vol_total),
            status=status,
            volume_total=vol_total
        )
    
    # ------------------------------------------------------------------
    def _salvar_cgr_scg(self):
        """Salva o valor total CGR no banco de consolidação SCG."""
        from tkinter import simpledialog
        from database import DatabasePMPV

        if self.valor_total_geral == 0.0:
            messagebox.showwarning("Aviso", "Execute a auditoria ou o somatório antes de salvar.")
            return

        periodo = simpledialog.askstring(
            "Salvar CGR no SCG",
            "Digite o período (ex: Dez/2025):",
            initialvalue="Dez/2025",
        )
        if not periodo:
            return

        db = DatabasePMPV()
        db.atualizar_cgr(periodo, self.valor_total_geral)
        rpv = db.calcular_e_salvar_rpv(periodo)
        db.fechar()

        val_fmt = f"R$ {self.valor_total_geral:,.2f}"
        rpv_fmt = f"R$ {rpv:,.2f}"
        messagebox.showinfo(
            "CGR Salvo ✅",
            f"Período  : {periodo}\n"
            f"CGR salvo: {val_fmt}\n"
            f"RPV = CGR − CGF = {rpv_fmt}\n\n"
            f"Acesse o módulo SCG para ver o resultado final.",
        )

    # ==========================================
    # GETTERS — use estes em outros cálculos
    # ==========================================

    def obter_totais(self) -> Tuple[float, float]:
        """Retorna (valor_total_geral, volume_total_geral)."""
        return (self.valor_total_geral, self.volume_total_geral)

    def obter_valor_total(self) -> float:
        """Somatório do VALOR de todos os documentos (NF-e + CT-e)."""
        return self.valor_total_geral

    def obter_volume_total(self) -> float:
        """Somatório do VOLUME de todos os documentos (NF-e + CT-e)."""
        return self.volume_total_geral

    def obter_totais_nfe(self) -> Tuple[float, float]:
        """Retorna (valor_total_nfe, volume_total_nfe) — só NF-e."""
        return (self.valor_total_nfe, self.volume_total_nfe)

    def obter_totais_cte(self) -> Tuple[float, float]:
        """Retorna (valor_total_cte, volume_total_cte) — só CT-e."""
        return (self.valor_total_cte, self.volume_total_cte)

    def _gerar_relatorio(self):
        """Gera relatório Excel"""
        wb = Workbook()
        ws = wb.active
        ws.title = "Auditoria"
        
        # Cabeçalho
        headers = ["Empresa", "Tipo", "Número", "Valor Total", "ICMS", "PIS", 
                   "COFINS", "Volume", "Status"]
        
        for col, header in enumerate(headers, 1):
            cell = ws.cell(1, col, header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        
        # Dados
        for row, item in enumerate(self.resultados, 2):
            ws.cell(row, 1, item.empresa)
            ws.cell(row, 2, item.tipo)
            ws.cell(row, 3, item.numero)
            ws.cell(row, 4, item.valor_total)
            ws.cell(row, 5, item.icms)
            ws.cell(row, 6, item.pis)
            ws.cell(row, 7, item.cofins)
            ws.cell(row, 8, item.volume)
            ws.cell(row, 9, item.status)
            
            # Colorir status
            status_cell = ws.cell(row, 9)
            if item.status == "OK":
                status_cell.fill = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
            else:
                status_cell.fill = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
        
        # Salvar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"Auditoria_XML_{timestamp}.xlsx"
        wb.save(nome_arquivo)
        
        # ===== SALVAR CGR NO BANCO =====
        cgr_total = sum(item.valor_total for item in self.resultados)
        
        periodo = simpledialog.askstring("Período CGR", 
                                        "Digite o período (ex: Q1 2026):",
                                        initialvalue="Q1 2026")
        
        if periodo:
            from database import DatabasePMPV
            db = DatabasePMPV()
            
            if not db.buscar_consolidacao(periodo):
                db.criar_periodo_consolidacao(periodo, "Auditoria XML")
            
            db.atualizar_cgr(periodo, cgr_total)
            db.fechar()
            
            messagebox.showinfo("CGR Salvo", 
                               f"CGR: R$ {cgr_total:,.2f}\nPeríodo: {periodo}\n\n"
                               f"Relatório: {nome_arquivo}")
        else:
            messagebox.showinfo("Sucesso", f"Relatório salvo:\n{nome_arquivo}")

if __name__ == "__main__":
    app = AppAuditoriaXML()
    app.mainloop()
