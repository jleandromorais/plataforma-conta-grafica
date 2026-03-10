import os
import sys
import sqlite3
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import datetime
from pathlib import Path

from Src.Services.servicos_ret import RegrasRET
from Src.Services.excel_ret import ExcelRET
from Src.Database.database import DatabasePMPV

_APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))

class TelaRET(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("Sistema RET - Processamento de PDFs")
        self.geometry("1400x900")
        
        self.pasta_selecionada = None
        self.dados_processados = []
        self.resultados = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color="#1a1a2e")
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header, 
            text="Sistema RET Master", 
            font=("Roboto", 32, "bold"),
            text_color="#00d9ff"
        ).pack(side="left", padx=30, pady=20)
        
        ctk.CTkLabel(
            header, 
            text="Processamento Automatizado de Encargos", 
            font=("Roboto", 14),
            text_color="#a0a0a0"
        ).pack(side="left", padx=10)
        
        # CONTAINER PRINCIPAL
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)
        
        # PAINEL ESQUERDO - Seleção
        left = ctk.CTkFrame(main, width=400, corner_radius=15)
        left.pack(side="left", fill="both", padx=(0, 10), pady=0)
        left.pack_propagate(False)
        
        ctk.CTkLabel(
            left, 
            text="Seleção de Pasta", 
            font=("Roboto", 20, "bold")
        ).pack(pady=(20, 10), padx=20, anchor="w")
        
        self.lbl_pasta = ctk.CTkLabel(
            left, 
            text="Nenhuma pasta selecionada",
            font=("Roboto", 12),
            wraplength=350,
            text_color="#808080"
        )
        self.lbl_pasta.pack(pady=10, padx=20)
        
        ctk.CTkButton(
            left,
            text="Selecionar Pasta",
            command=self.selecionar_pasta,
            height=40,
            font=("Roboto", 14, "bold"),
            fg_color="#2196F3",
            hover_color="#1976D2"
        ).pack(pady=10, padx=20, fill="x")
        
        # BOTÃO PROCESSAR
        ctk.CTkButton(
            left,
            text="PROCESSAR PDFs",
            command=self.processar,
            height=50,
            font=("Roboto", 16, "bold"),
            fg_color="#4CAF50",
            hover_color="#45a049"
        ).pack(pady=30, padx=20, fill="x")
        
        # PAINEL DIREITO - Resultados
        right = ctk.CTkFrame(main, corner_radius=15)
        right.pack(side="right", fill="both", expand=True)
        
        ctk.CTkLabel(
            right, 
            text="Resultados do Processamento", 
            font=("Roboto", 20, "bold")
        ).pack(pady=(20, 10), padx=20, anchor="w")
        
        # TABELA DE RESULTADOS
        self.tabview = ctk.CTkTabview(right)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tabview.add("Resumo")
        self.tabview.add("Dados Detalhados")
        self.tabview.add("Logs")
        self.tabview.add("Sem Valores")
        
        # ABA RESUMO
        self.frame_resumo = ctk.CTkScrollableFrame(self.tabview.tab("Resumo"))
        self.frame_resumo.pack(fill="both", expand=True)
        
        self.lbl_stats = ctk.CTkLabel(
            self.frame_resumo,
            text="Aguardando processamento...",
            font=("Roboto", 14),
            justify="left"
        )
        self.lbl_stats.pack(pady=20, padx=20, anchor="w")
        
        # ABA DADOS DETALHADOS
        self.frame_dados = ctk.CTkScrollableFrame(self.tabview.tab("Dados Detalhados"))
        self.frame_dados.pack(fill="both", expand=True)
        
        # ABA LOGS
        self.txt_logs = ctk.CTkTextbox(
            self.tabview.tab("Logs"),
            font=("Consolas", 11)
        )
        self.txt_logs.pack(fill="both", expand=True, padx=10, pady=10)
        
        # ABA SEM VALORES
        self.txt_sem_valores = ctk.CTkTextbox(
            self.tabview.tab("Sem Valores"),
            font=("Consolas", 11)
        )
        self.txt_sem_valores.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_sem_valores.insert("end", "Nenhum processamento realizado.\nSelecione a pasta e clique em PROCESSAR PDFs.")
        
        # RODAPÉ
        footer = ctk.CTkFrame(self, height=100, corner_radius=15, fg_color="#1a1a2e")
        footer.pack(fill="x", padx=20, pady=(0, 20))
        footer.pack_propagate(False)
        
        # RESULTADO TOTAL
        result_frame = ctk.CTkFrame(footer, fg_color="transparent")
        result_frame.pack(side="left", padx=30, pady=20)
        
        ctk.CTkLabel(
            result_frame,
            text="TOTAL GERAL:",
            font=("Roboto", 14)
        ).pack(anchor="w")
        
        self.lbl_total = ctk.CTkLabel(
            result_frame,
            text="R$ 0,00",
            font=("Roboto", 28, "bold"),
            text_color="#00d9ff"
        )
        self.lbl_total.pack(anchor="w")
        
        # BOTÕES DE AÇÃO
        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(side="right", padx=30, pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="Salvar no Banco",
            command=self.salvar_db,
            width=140,
            height=35,
            fg_color="#9C27B0",
            hover_color="#7B1FA2"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="Exportar Excel",
            command=self.exportar_excel,
            width=140,
            height=35,
            fg_color="#FF9800",
            hover_color="#F57C00"
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="💾 Salvar RET",
            command=self._salvar_ret_scg,
            width=140,
            height=35,
            fg_color="#27ae60",
            hover_color="#229954"
        ).pack(side="left", padx=5)
    
    def log(self, mensagem):
        """Adiciona mensagem ao log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_logs.insert("end", f"[{timestamp}] {mensagem}\n")
        self.txt_logs.see("end")
        self.update()
    
    def selecionar_pasta(self):
        """Seleciona pasta para processamento"""
        pasta = filedialog.askdirectory(title="Selecione a Pasta Principal (RET)")
        
        if pasta:
            self.pasta_selecionada = pasta
            self.lbl_pasta.configure(
                text=f"Pasta: {pasta}",
                text_color="#4CAF50"
            )
            self.log(f"Pasta selecionada: {pasta}")
            
    def processar(self):
        if not self.pasta_selecionada:
            messagebox.showwarning("Aviso", "Selecione uma pasta primeiro!")
            return
        
        self.log("="*60)
        self.log("INICIANDO PROCESSAMENTO")
        self.log("="*60)
        
        self.dados_processados = []
        arquivos_processados = 0
        ignorados_nf = 0

        for raiz, _, ficheiros in os.walk(self.pasta_selecionada):
            partes_raiz = [p.upper() for p in Path(raiz).parts]
            if any('NOTAS FISCAIS' in p or 'NOTA FISCAL' in p for p in partes_raiz):
                ignorados_nf += len([f for f in ficheiros if f.lower().endswith('.pdf')])
                continue

            for ficheiro in ficheiros:
                if ficheiro.lower().endswith('.pdf'):
                    caminho_completo = os.path.join(raiz, ficheiro)

                    tipo_nota = RegrasRET.extrair_tipo_nota(caminho_completo)
                    if tipo_nota == 'NF':
                        ignorados_nf += 1
                        self.log(f"   [NF] Ignorado (Nota Fiscal): {ficheiro}")
                        continue

                    self.log(f"[PDF] Processando: {ficheiro}")

                    # Chama o nosso novo serviço de regras passando o log!
                    dados_pdf = RegrasRET.extrair_dados_pdf(caminho_completo, log_callback=self.log)

                    if dados_pdf['valores_encontrados']:
                        self.dados_processados.append(dados_pdf)
                        self.log(f"   [OK] {len(dados_pdf['valores_encontrados'])} valores")
                    else:
                        self.dados_processados.append(dados_pdf)
                        self.log(f"   [AVISO] Sem valores")

                    arquivos_processados += 1

        if ignorados_nf:
            self.log(f"\n[INFO] {ignorados_nf} PDF(s) em 'Notas Fiscais' ignorados (fora do escopo do RET).")
        
        self._mostrar_resultados(arquivos_processados)
    
    def _mostrar_resultados(self, total_arquivos):
        self._mostrar_sem_valores()
        
        if not self.dados_processados:
            messagebox.showwarning("Aviso", "Nenhum PDF foi processado! Verifique a pasta e os tipos de encargo selecionados.")
            return
        
        # O cálculo oficial agora vem do ficheiro de regras
        calc = RegrasRET.calcular_ret(self.dados_processados)
        com_valores = len([d for d in self.dados_processados if d['valor_total'] > 0])

        ret_fmt2 = f"R$ {calc['ret']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        self.lbl_total.configure(text=ret_fmt2)

        resumo_tipos = {}
        for d in self.dados_processados:
            tipo = d['tipo_encargo']
            if tipo not in resumo_tipos:
                resumo_tipos[tipo] = {'count': 0, 'total': 0}
            resumo_tipos[tipo]['count'] += 1
            resumo_tipos[tipo]['total'] += d['valor_total']

        for widget in self.frame_resumo.winfo_children():
            widget.destroy()

        eat_bruto_fmt = f"R$ {calc['eat_bruto']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        stats_text = f"""
ESTATÍSTICAS DO PROCESSAMENTO

Total de PDFs: {total_arquivos}
PDFs com valores: {com_valores}
Σ EAT (bruto): {eat_bruto_fmt}
EC = RET (líquido): {ret_fmt2}

RESUMO POR TIPO:
"""
        for tipo, stats in resumo_tipos.items():
            total_tipo_fmt = f"R$ {stats['total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            stats_text += f"\n{tipo}:\n"
            stats_text += f"  - Arquivos: {stats['count']}\n"
            stats_text += f"  - Total: {total_tipo_fmt}\n"

        def brl6(v):
            partes = f"{v:,.6f}".split('.')
            dec = partes[1].rstrip('0')
            dec = dec if len(dec) >= 2 else dec.ljust(2, '0')
            inteiro = partes[0].replace(',', 'X').replace('.', ',').replace('X', '.')
            return f"R$ {inteiro},{dec}"

        aliq_pct = calc['pis_cofins_rate'] * 100
        ret_text = f"""
{'='*56}
CÁLCULO EC / RET  [precisão: 6 casas decimais]
{'='*56}

  Σ pasta EAT (bruto)           {brl6(calc['eat_bruto']):>22s}
  × (1 − {aliq_pct:.2f}% PIS/COFINS)            × {1 - calc['pis_cofins_rate']:.4f}
  {'─'*56}
  EC  (pasta EAT líquida)       {brl6(calc['eat_bruto'] * (1 - calc['pis_cofins_rate'])):>22s}
"""
        if calc['ec_docs_total'] > 0:
            ret_text += f"  (+) Σ pasta EC (docs.)        {brl6(calc['ec_docs_total']):>22s}\n"
            ret_text += f"  {'─'*56}\n"

        ret_text += f"""  EC  =  RET                    {brl6(calc['ret']):>22s}
{'='*56}
"""
        if calc['outros_docs']:
            ret_text += f"\n  [INFO] Documentos fora das pastas EAT/EC ({len(calc['outros_docs'])}):\n"
            for d in calc['outros_docs'][:10]:
                ret_text += f"    • {d['arquivo']}  tipo={d['tipo_encargo']}\n"
            if len(calc['outros_docs']) > 10:
                ret_text += f"    ... e mais {len(calc['outros_docs']) - 10} arquivo(s)\n"

        if calc['eat_docs']:
            ret_text += f"\n  DETALHES PASTA EAT ({len(calc['eat_docs'])} docs):\n"
            for d in calc['eat_docs']:
                ret_text += f"    • {d['arquivo']:<45s}  {brl6(d['valor_total'])}\n"

        stats_text += ret_text

        ctk.CTkLabel(
            self.frame_resumo,
            text=stats_text,
            font=("Consolas", 13),
            justify="left"
        ).pack(pady=20, padx=20, anchor="w")
        
        self._mostrar_dados_detalhados()
        
        self.log("="*60)
        self.log(f"PROCESSAMENTO CONCLUÍDO - {total_arquivos} arquivos")
        self.log("="*60)

        messagebox.showinfo(
            "Sucesso",
            f"Processados {total_arquivos} PDFs!\n"
            f"Σ EAT (bruto): {eat_bruto_fmt}\n"
            f"EC = RET:       {ret_fmt2}"
        )
    
    def _mostrar_dados_detalhados(self):
        for widget in self.frame_dados.winfo_children():
            widget.destroy()
        
        header = ctk.CTkFrame(self.frame_dados, fg_color="#2c3e50")
        header.pack(fill="x", pady=(0, 5))
        
        colunas = [
            ("Tipo", 80), ("Empresa", 150), ("Nota", 80),
            ("Nº", 100), ("Vencimento", 100), ("Valor Total", 120),
            ("QT", 80), ("Valor Unit.", 100)
        ]
        
        for txt, w in colunas:
            ctk.CTkLabel(header, text=txt, width=w, font=("Roboto", 11, "bold")).pack(side="left", padx=2)
        
        total_regs = len(self.dados_processados)
        if total_regs > 500:
            ctk.CTkLabel(self.frame_dados, text=f"⚠ Exibindo 500 de {total_regs} registros.",
                         text_color="#f39c12", font=("Roboto", 11)).pack(anchor="w", padx=10)

        for d in self.dados_processados[:500]:
            row = ctk.CTkFrame(self.frame_dados, fg_color="#34495e")
            row.pack(fill="x", pady=1)
            valores = [
                (d['tipo_encargo'],          80),
                (d['empresa'],              150),
                (d['nota_tipo'],             80),
                (d['numero_nd'],            100),
                (d['data_vencimento'],      100),
                (f"{d['valor_total']:.2f}", 120),
                (f"{d['quantidade']:.2f}",   80),
                (f"{d['valor_unitario']:.2f}", 100),
            ]
            
            for val, w in valores:
                ctk.CTkLabel(row, text=str(val), width=w, font=("Roboto", 10)).pack(side="left", padx=2)
    
    def _mostrar_sem_valores(self):
        self.txt_sem_valores.delete("1.0", "end")
        if not self.dados_processados:
            self.txt_sem_valores.insert("end", "Nenhum processamento realizado.\nSelecione a pasta e clique em PROCESSAR PDFs.")
            return
        sem_valores = [d for d in self.dados_processados if not d.get('valores_encontrados') or d.get('valor_total', 0) == 0]
        if not sem_valores:
            self.txt_sem_valores.insert("end", "Nenhum arquivo sem valores.\n\nTodos os PDFs processados tiveram pelo menos um valor extraído.")
            return
        self.txt_sem_valores.insert("end", f"ARQUIVOS SEM VALORES ({len(sem_valores)})\n")
        self.txt_sem_valores.insert("end", "PDFs lidos nos quais não foi possível extrair valores (valor total = 0):\n")
        self.txt_sem_valores.insert("end", "=" * 60 + "\n\n")
        for i, d in enumerate(sem_valores, 1):
            arquivo = d.get("arquivo", "")
            caminho = d.get("caminho", "")
            tipo = d.get("tipo_encargo", "")
            self.txt_sem_valores.insert("end", f"{i:4}. [{tipo}] {arquivo}\n")
            self.txt_sem_valores.insert("end", f"      Nenhum valor extraído\n")
            self.txt_sem_valores.insert("end", f"      {caminho}\n\n")
        self.txt_sem_valores.see("1.0")
    
    def salvar_db(self):
        if not self.dados_processados:
            messagebox.showwarning("Aviso", "Processe os PDFs primeiro!")
            return

        try:
            db_path = os.path.join(_APP_DIR, 'RET_dados.db')
            conexao = sqlite3.connect(db_path)
            cursor = conexao.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dados_ret (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tipo_encargo TEXT, empresa TEXT, nota_tipo TEXT, numero_nd TEXT,
                    data_vencimento TEXT, valor_total REAL, quantidade REAL,
                    valor_unitario REAL, arquivo TEXT, caminho TEXT, data_processamento TEXT
                )
            ''')

            for d in self.dados_processados:
                cursor.execute('''
                    INSERT INTO dados_ret (
                        tipo_encargo, empresa, nota_tipo, numero_nd,
                        data_vencimento, valor_total, quantidade, valor_unitario,
                        arquivo, caminho, data_processamento
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    d['tipo_encargo'], d['empresa'], d['nota_tipo'], d['numero_nd'],
                    d['data_vencimento'], d['valor_total'], d['quantidade'], d['valor_unitario'],
                    d['arquivo'], d['caminho'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))

            conexao.commit()
            conexao.close()
            self.log(f"[OK] Dados salvos em: {db_path}")

            resposta = messagebox.askyesno(
                "Backup do Banco de Dados",
                f"Dados salvos com sucesso!\nLocal do banco: {db_path}\n\n"
                "Deseja salvar uma cópia de backup em outra pasta?"
            )
            if resposta:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = filedialog.asksaveasfilename(
                    title="Salvar cópia do banco de dados",
                    initialfile=f"RET_dados_backup_{timestamp}.db",
                    defaultextension=".db",
                    filetypes=[("Banco de dados SQLite", "*.db"), ("Todos os arquivos", "*.*")],
                    initialdir=self.pasta_selecionada or os.path.expanduser("~"),
                )
                if backup_path:
                    import shutil
                    shutil.copy2(db_path, backup_path)
                    self.log(f"[OK] Backup salvo em: {backup_path}")
                    messagebox.showinfo("Backup Salvo", f"Cópia salva em:\n{backup_path}")
            else:
                messagebox.showinfo("Sucesso", f"Dados salvos no banco!\n{db_path}")

        except Exception as e:
            self.log(f"[ERRO] Falha ao salvar: {e}")
            messagebox.showerror("Erro", f"Erro ao salvar: {e}")
    
    def exportar_excel(self):
        if not self.dados_processados:
            messagebox.showwarning("Aviso", "Processe os PDFs primeiro!")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_path = filedialog.asksaveasfilename(
                title="Salvar relatório Excel",
                initialfile=f"RET_Relatorio_{timestamp}.xlsx",
                defaultextension=".xlsx",
                filetypes=[("Planilha Excel", "*.xlsx"), ("Todos os arquivos", "*.*")],
                initialdir=self.pasta_selecionada or os.path.expanduser("~"),
            )
            if not excel_path: return
            
            calc_ret = RegrasRET.calcular_ret(self.dados_processados)
            ExcelRET.gerar_relatorio_completo(self.dados_processados, calc_ret, excel_path)
            
            self.log(f"[OK] Excel criado: {excel_path}")
            messagebox.showinfo("Sucesso", f"Excel exportado com sucesso!\n{excel_path}")
            
        except Exception as e:
            self.log(f"[ERRO] Falha ao exportar: {e}")
            messagebox.showerror("Erro", f"Erro ao exportar: {e}")
    
    def _salvar_ret_scg(self):
        if not hasattr(self, 'dados_processados') or not self.dados_processados:
            messagebox.showwarning("Aviso", "Processe os PDFs primeiro!")
            return
        
        from tkinter import simpledialog
        calc = RegrasRET.calcular_ret(self.dados_processados)
        total_geral = calc['ret']

        periodo = simpledialog.askstring("Período RET", "Digite o período (ex: Q1 2026):", initialvalue="Q1 2026")
        if periodo:
            db = DatabasePMPV()
            if not db.buscar_consolidacao(periodo):
                db.criar_periodo_consolidacao(periodo, "RET")
            db.atualizar_ret(periodo, total_geral)
            db.fechar()

            total_fmt = f"R$ {total_geral:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            messagebox.showinfo("RET Salvo", f"RET: {total_fmt}\nPeríodo: {periodo}")