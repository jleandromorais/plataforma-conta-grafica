import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import threading
from pathlib import Path
from datetime import datetime

# --- IMPORTAÇÕES DA NOVA ARQUITETURA ---
from Src.Services.servicos_concilia import RegrasConcilia
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.Services.excel_concilia import ExcelConcilia
from Src.common.formatting import format_brl_plain
from Src.common.excel_final_destino import registrar_execucao_excel_final
from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

class TelaConciliador(ctk.CTkFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.path_rec = tk.StringVar()
        self.path_desp = tk.StringVar()
        self.status_ocr_txt = "✅ MOTOR OCR ATIVO" if OCR_ENABLED else "❌ OCR NÃO ENCONTRADO"
        self.cor_ocr = "#27ae60" if OCR_ENABLED else "#c0392b"
        self.consolidacao = ServicosConsolidacao()

        self._setup_ui()

    def _setup_ui(self):
        # HEADER
        self.header_frame = ctk.CTkFrame(self, height=80, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(self.header_frame, text="Conciliador Financeiro Inteligente", font=("Roboto", 24, "bold")).pack(side="left")
        
        self.ocr_badge = ctk.CTkLabel(self.header_frame, text=self.status_ocr_txt, fg_color=self.cor_ocr, 
                                     text_color="white", corner_radius=10, font=("Roboto", 12, "bold"), padx=10)
        self.ocr_badge.pack(side="right")

        # SELEÇÃO
        self.selection_frame = ctk.CTkFrame(self)
        self.selection_frame.pack(fill="x", padx=20, pady=10)
        
        self._criar_input_folder(self.selection_frame, "📂 Pasta de RECEITAS", self.path_rec, self.sel_rec, "green")
        ctk.CTkFrame(self.selection_frame, height=2, fg_color="gray30").pack(fill="x", padx=10, pady=10)
        self._criar_input_folder(self.selection_frame, "📂 Pasta de DESPESAS", self.path_desp, self.sel_desp, "red")

        # BOTÕES
        self.btn_run = ctk.CTkButton(self, text="⚡ PROCESSAR E CONCILIAR", command=self.iniciar_thread, 
                                    font=("Roboto", 16, "bold"), height=50, fg_color="#2980b9")
        self.btn_run.pack(fill="x", padx=40, pady=(20, 5))

        self.btn_salvar_scg = ctk.CTkButton(self, text="💾 SALVAR SALDO (RP) NO SCG", command=self._salvar_rp_scg,
                                           font=("Roboto", 13, "bold"), height=38, fg_color="#27ae60", state="disabled")
        self.btn_salvar_scg.pack(fill="x", padx=40, pady=(0, 15))

        self.btn_excel_final = ctk.CTkButton(
            self,
            text="➕ Adicionar ao Excel Final (Módulo 9)",
            command=self._adicionar_excel_final,
            font=("Roboto", 13, "bold"),
            height=38,
            fg_color="#6c3483",
            hover_color="#884ea0",
            state="disabled",
        )
        self.btn_excel_final.pack(fill="x", padx=40, pady=(0, 15))

        # LOG
        self.log_box = ctk.CTkTextbox(self, height=200, font=("Consolas", 12))
        self.log_box.pack(fill="both", expand=True, padx=20, pady=(5, 20))
        
        self.progress = ctk.CTkProgressBar(self)
        self.progress.set(0)
        self.progress.pack(fill="x", side="bottom")

    def _criar_input_folder(self, parent, titulo, variavel, comando, cor):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame, text=titulo, font=("Roboto", 14, "bold"), text_color=cor).pack(anchor="w")
        sub = ctk.CTkFrame(frame, fg_color="transparent")
        sub.pack(fill="x", pady=5)
        ctk.CTkEntry(sub, textvariable=variavel, width=500, state="readonly").pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(sub, text="Selecionar", command=comando, width=100).pack(side="right")

    def log_message(self, msg):
        self.log_box.insert("end", f"> {datetime.now().strftime('%H:%M:%S')} | {msg}\n")
        self.log_box.see("end")

    def sel_rec(self):
        p = filedialog.askdirectory()
        if p: self.path_rec.set(p)

    def sel_desp(self):
        p = filedialog.askdirectory()
        if p: self.path_desp.set(p)

    def iniciar_thread(self):
        if not self.path_rec.get() and not self.path_desp.get():
            messagebox.showwarning("Aviso", "Selecione pelo menos uma pasta!")
            return
        self.btn_run.configure(state="disabled", text="Processando...")
        self.progress.start()
        threading.Thread(target=self.rodar_processamento, daemon=True).start()

    def rodar_processamento(self):
        try:
            p_rec = Path(self.path_rec.get()) if self.path_rec.get() else None
            p_desp = Path(self.path_desp.get()) if self.path_desp.get() else None

            arquivos_rec = list(p_rec.rglob("*.pdf")) if p_rec else []
            arquivos_desp = list(p_desp.rglob("*.pdf")) if p_desp else []

            itens = []
            if arquivos_rec:
                self.log_message("--- Receitas ---")
                itens += RegrasConcilia.processar_arquivos(arquivos_rec, "Receita", self.log_message)
            if arquivos_desp:
                self.log_message("--- Despesas ---")
                itens += RegrasConcilia.processar_arquivos(arquivos_desp, "Despesa", self.log_message)

            if not itens:
                self.log_message("Nenhum PDF processado.")
                return

            nome_excel = f"Conciliacao_{datetime.now().strftime('%H%M%S')}.xlsx"
            caminho_final = Path(os.getcwd()) / nome_excel

            tot_rec, tot_desp = ExcelConcilia.gerar_relatorio(caminho_final, itens)
            self._ultimo_saldo_rp = tot_rec - tot_desp
            self._ultimos_itens_concilia = itens

            self.log_message(f"CONCLUÍDO! Salvo em: {caminho_final}")
            msg = f"Finalizado!\nSaldo: R$ {format_brl_plain(self._ultimo_saldo_rp)}"
            messagebox.showinfo("Sucesso", msg)
            self.btn_salvar_scg.configure(state="normal")
            self.btn_excel_final.configure(state="normal")

        except Exception as e:
            self.log_message(f"ERRO: {e}")
            messagebox.showerror("Erro", str(e))
        finally:
            self.restaurar_interface()

    def _salvar_rp_scg(self):
        periodo = simpledialog.askstring(
            "Salvar RP", "Digite o período (ex: Dez/2025):", initialvalue="Dez/2025"
        )
        if not periodo:
            return

        self.consolidacao.salvar_rp(periodo, self._ultimo_saldo_rp)

        # Salva itens detalhados no banco principal
        itens = getattr(self, "_ultimos_itens_concilia", [])
        if itens:
            itens_dict = [
                {
                    "arquivo":   it.file_name,
                    "categoria": it.category,
                    "valor":     it.amount,
                    "status":    it.status,
                    "metodo":    it.method,
                }
                for it in itens
            ]
            try:
                db = DatabasePMPV()
                db.salvar_concilia_itens(periodo, itens_dict)
                db.fechar()
            except Exception as e:
                messagebox.showwarning("Aviso BD", f"RP salvo no SCG, mas erro ao salvar itens:\n{e}")

        messagebox.showinfo(
            "Salvo ✅",
            f"Período: {periodo}\n"
            f"RP salvo: R$ {format_brl_plain(self._ultimo_saldo_rp)}\n\n"
            f"{len(itens)} item(ns) salvo(s) no banco."
        )

    def restaurar_interface(self):
        self.progress.stop()
        self.progress.set(1)
        self.btn_run.configure(state="normal", text="⚡ PROCESSAR E CONCILIAR")

    def _adicionar_excel_final(self):
        saldo = getattr(self, "_ultimo_saldo_rp", None)
        itens = getattr(self, "_ultimos_itens_concilia", [])
        if saldo is None:
            messagebox.showwarning("Aviso", "Processe a Conciliação antes de adicionar ao Excel final.")
            return

        periodo = simpledialog.askstring(
            "Excel Final (Módulo 9)",
            "Período para salvar e gerar o Excel final (ex: Dez/2025):\nDeixe em branco para gerar com todos os períodos.",
            parent=self,
        )
        if periodo is None:
            return

        periodo_salvar = periodo.strip() if periodo.strip() else "Geral"

        self.consolidacao.salvar_rp(periodo_salvar, saldo)
        if itens:
            itens_dict = [
                {
                    "arquivo": it.file_name,
                    "categoria": it.category,
                    "valor": it.amount,
                    "status": it.status,
                    "metodo": it.method,
                }
                for it in itens
            ]
            db = DatabasePMPV()
            try:
                db.salvar_concilia_itens(periodo_salvar, itens_dict)
            finally:
                db.fechar()

        meta_execucao = registrar_execucao_excel_final(etapa="Conciliação RP", periodo=periodo_salvar, parent=self)
        if not meta_execucao:
            return
        destino, _, _, execucao = meta_execucao
        arquivo = ExcelConsolidado.exportar(periodo=None, nome_arquivo=destino)
        messagebox.showinfo("Excel final gerado ✅", f"Arquivo criado com sucesso:\n{arquivo}\n\nEtapa Conciliação RP registrada (execução #{execucao}).")