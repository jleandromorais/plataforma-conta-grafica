import os
import sys
import customtkinter as ctk
from tkinter import filedialog, messagebox
from datetime import datetime
from pathlib import Path

from Src.config import ui_theme as ui
from Src.Services.servicos_ret import RegrasRET
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.common.excel_final_destino import registrar_execucao_excel_final, obter_periodos_trimestre
from Src.Database.database import DatabasePMPV
from Src.common.formatting import format_brl
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

_APP_DIR = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) \
           else os.path.dirname(os.path.abspath(__file__))

class TelaRET(ctk.CTkFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.pasta_selecionada = None
        self.dados_processados = []
        self.resultados = None
        self.consolidacao = ServicosConsolidacao()
        
        self._setup_ui()
    
    def _setup_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=ui.COR_HEADER)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="Sistema RET",
            font=ui.FONTE_TITULO,
            text_color=ui.COR_TEXTO_TITULO
        ).pack(side="left", padx=ui.ESP_LG, pady=ui.ESP_LG)

        ctk.CTkLabel(
            header,
            text="Processamento Automatizado de Encargos",
            font=ui.FONTE_SUBTITULO,
            text_color=ui.COR_TEXTO_SUBTITULO
        ).pack(side="left", padx=ui.ESP_SM)
        
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

        self._setup_seletor_periodo(left)

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
        
        # =================================================================
        # FLUXO DE SALVAMENTO ÚNICO:
        # 1. Processar PDFs
        # 2. Verificar resultados (abas: Resumo, Logs, Detalhados)
        # 3. Salvar RET no Banco (salvará em BD Principal com período)
        # 4. (Opcional) Adicionar ao Excel Final para gerar relatório
        # =================================================================
        btn_frame = ctk.CTkFrame(footer, fg_color="transparent")
        btn_frame.pack(side="right", padx=30, pady=20)

        ctk.CTkButton(
            btn_frame,
            text="💾 Salvar RET no Banco",
            command=self._salvar_ret_no_banco,
            width=180,
            height=40,
            font=("Roboto", 13, "bold"),
            fg_color="#27ae60",
            hover_color="#229954"
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_frame,
            text="➕ Adicionar ao Excel Final (Módulo 9)",
            command=self._adicionar_excel_final,
            width=260,
            height=40,
            font=("Roboto", 13, "bold"),
            fg_color="#2980b9",
            hover_color="#1a6fa8"
        ).pack(side="left", padx=8)
    
    # ------------------------------------------------------------------
    # SELETOR DE PERÍODO (mês + ano visual, sem digitação)
    # ------------------------------------------------------------------
    _MESES_ABREV = ["Jan","Fev","Mar","Abr","Mai","Jun",
                    "Jul","Ago","Set","Out","Nov","Dez"]

    def _setup_seletor_periodo(self, parent):
        """Cria o seletor visual de mês/ano no painel esquerdo."""
        agora = datetime.now()
        self._mes_sel  = agora.month   # 1-12
        self._ano_sel  = agora.year
        self._btns_mes = {}
        self._periodo_manual = False   # True quando o usuário clicou num mês

        ctk.CTkLabel(
            parent, text="Período de Referência",
            font=("Roboto", 13, "bold")
        ).pack(pady=(14, 4), padx=20, anchor="w")

        card = ctk.CTkFrame(parent, fg_color="#12122a", corner_radius=10)
        card.pack(fill="x", padx=14, pady=(0, 8))

        # ── Seletor de ano ────────────────────────────────────────────
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
            font=("Roboto", 18, "bold"), width=70,
            text_color="#00d9ff"
        )
        self.lbl_ano.pack(side="left")

        ctk.CTkButton(
            ano_row, text="▶", width=32, height=28,
            fg_color="#1a3a5c", hover_color="#2e6da4",
            font=("Roboto", 13, "bold"),
            command=self._ano_proximo
        ).pack(side="left", padx=(6, 0))

        # ── Grade de meses (3 colunas × 4 linhas) ────────────────────
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

        # ── Label de confirmação ──────────────────────────────────────
        self.lbl_periodo_sel = ctk.CTkLabel(
            card, text="", font=("Roboto", 12, "bold"),
            text_color="#f1c40f"
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

    def _auto_detectar_periodo(self):
        """Após processar PDFs, ajusta o seletor se o usuário não escolheu manualmente."""
        if self._periodo_manual:
            return  # respeita a escolha do usuário
        from collections import Counter
        refs = [d.get("mes_ref", "") for d in self.dados_processados if d.get("mes_ref")]
        if not refs:
            return
        mais_comum = Counter(refs).most_common(1)[0][0]  # ex: "Fev/2026"
        try:
            abrev, ano_str = mais_comum.split("/")
            mes_num = self._MESES_ABREV.index(abrev) + 1
            self._mes_sel = mes_num
            self._ano_sel = int(ano_str)
            self.lbl_ano.configure(text=str(self._ano_sel))
            self._atualizar_visual_meses()
            self.log(f"[INFO] Período detectado automaticamente: {mais_comum}")
        except Exception:
            pass

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
        """Compatibilidade: retorna um objeto com .get() igual ao período selecionado."""
        class _FakePeriodo:
            def __init__(self_, val): self_._v = val
            def get(self_): return self_._v
            def strip(self_): return self_._v
        return _FakePeriodo(
            f"{self._MESES_ABREV[self._mes_sel - 1]}/{self._ano_sel}"
        )

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
            self._periodo_manual = False  # nova pasta → permite auto-detecção
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

        self._auto_detectar_periodo()
        self._mostrar_resultados(arquivos_processados)
    
    def _mostrar_resultados(self, total_arquivos):
        self._mostrar_sem_valores()
        
        if not self.dados_processados:
            messagebox.showwarning("Aviso", "Nenhum PDF foi processado! Verifique a pasta e os tipos de encargo selecionados.")
            return
        
        # O cálculo oficial agora vem do ficheiro de regras
        calc = RegrasRET.calcular_ret(self.dados_processados)
        com_valores = len([d for d in self.dados_processados if d['valor_total'] > 0])

        ret_fmt2 = format_brl(calc['ret'])
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

        eat_bruto_fmt = format_brl(calc['eat_bruto'])
        stats_text = f"""
ESTATÍSTICAS DO PROCESSAMENTO

Total de PDFs: {total_arquivos}
PDFs com valores: {com_valores}
Σ EAT (bruto): {eat_bruto_fmt}
EC = RET (líquido): {ret_fmt2}

RESUMO POR TIPO:
"""
        for tipo, stats in resumo_tipos.items():
            total_tipo_fmt = format_brl(stats['total'])
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
    
    def _salvar_ret_no_banco(self):
        if not hasattr(self, 'dados_processados') or not self.dados_processados:
            messagebox.showwarning("Aviso", "Processe os PDFs primeiro!")
            return

        calc = RegrasRET.calcular_ret(self.dados_processados)
        total_geral = calc['ret']
        periodo = self.entry_periodo.get()

        total_fmt = format_brl(total_geral)
        if not messagebox.askyesno("Confirmar salvamento",
                                   f"Salvar RET no banco de dados?\n\n"
                                   f"Período: {periodo}\n"
                                   f"Total RET: {total_fmt}\n"
                                   f"Documentos: {len(self.dados_processados)}"):
            return

        self.consolidacao.salvar_ret(periodo, total_geral)

        # Salva os itens detalhados no banco principal
        try:
            with DatabasePMPV() as db:
                db.salvar_ret_itens(periodo, self.dados_processados)
        except Exception as e:
            messagebox.showwarning("Aviso BD", f"RET salvo no SCG, mas erro ao salvar itens:\n{e}")

        total_fmt = format_brl(total_geral)
        messagebox.showinfo(
            "RET Salvo ✅",
            f"Período: {periodo}\n"
            f"RET (EC): {total_fmt}\n\n"
            f"{len(self.dados_processados)} documento(s) salvo(s) no banco."
        )

    def _adicionar_excel_final(self):
        if not hasattr(self, 'dados_processados') or not self.dados_processados:
            messagebox.showwarning("Aviso", "Processe os PDFs do RET antes de adicionar ao Excel final.")
            return

        periodo_salvar = self.entry_periodo.get().strip()
        if not periodo_salvar:
            meses_auto = obter_periodos_trimestre()
            periodo_salvar = meses_auto[-1] if meses_auto else ""
        if not periodo_salvar:
            messagebox.showwarning(
                "Período não encontrado",
                "Preencha o campo Período ou calcule o PMPV primeiro para determinar o trimestre ativo.",
                parent=self,
            )
            return

        try:
            # Garante que os dados estão no BD antes de gerar o Excel
            # (idempotente: DELETE+INSERT — não duplica se já foi salvo)
            calc = RegrasRET.calcular_ret(self.dados_processados)
            self.consolidacao.salvar_ret(periodo_salvar, calc['ret'])
            with DatabasePMPV() as db_save:
                db_save.salvar_ret_itens(periodo_salvar, self.dados_processados)

            meta_execucao = registrar_execucao_excel_final(etapa="RET", periodo=periodo_salvar, parent=self)
            if not meta_execucao:
                return
            destino, nome_sessao, periodo_norm, execucao = meta_execucao
            meses_tri = obter_periodos_trimestre(periodo_norm)
            arquivo = ExcelConsolidado.exportar(
                periodo=periodo_norm,
                nome_arquivo=destino,
                periodos_trimestre=meses_tri,
            )
            self._mostrar_sucesso_modulo9(arquivo, periodo_norm, execucao, meses_tri)

        except Exception as e:
            messagebox.showerror("Erro — Módulo 9", f"Falha ao adicionar ao Excel Final:\n\n{e}")

    def _mostrar_sucesso_modulo9(self, arquivo: str, periodo: str, execucao: int, meses: list | None = None):
        import customtkinter as ctk
        win = ctk.CTkToplevel(self)
        win.title("Módulo 9 — Concluído")
        win.geometry("480x270")
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.lift()
        win.after(50, win.grab_set)

        ctk.CTkFrame(win, height=5, fg_color="#27ae60", corner_radius=0).pack(fill="x")
        ctk.CTkLabel(win, text="✅  RET adicionado ao Excel Final",
                     font=("Roboto", 16, "bold"), text_color="#27ae60").pack(pady=(16, 4))
        ctk.CTkLabel(win, text="Os encargos de transporte foram gravados no Módulo 9.",
                     font=("Roboto", 11), text_color="#aaaaaa").pack(pady=(0, 12))

        frame = ctk.CTkFrame(win, fg_color="#12122a", corner_radius=10)
        frame.pack(fill="x", padx=20, pady=(0, 14))

        def _row(label, valor):
            f = ctk.CTkFrame(frame, fg_color="transparent")
            f.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(f, text=label, font=("Roboto", 11), text_color="#7f8c8d", width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(f, text=valor, font=("Roboto", 11, "bold"), text_color="#ecf0f1", anchor="w").pack(side="left")

        _row("Período:", periodo)
        _row("Execução nº:", str(execucao))
        _row("Arquivo:", arquivo.split("\\")[-1] if "\\" in arquivo else arquivo.split("/")[-1])

        ctk.CTkButton(win, text="Fechar", command=win.destroy, width=120,
                      fg_color="#27ae60", hover_color="#2ecc71").pack(pady=(0, 16))