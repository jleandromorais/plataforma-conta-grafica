import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import logging
import os
import threading
import tempfile
import zipfile
import shutil
from pathlib import Path
from datetime import datetime

# --- IMPORTAÇÕES DA NOVA ARQUITETURA ---
from Src.config import ui_theme as ui
from Src.Services.servicos_concilia import RegrasConcilia
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.Services.excel_concilia import ExcelConcilia
from Src.common.formatting import format_brl_plain
from Src.common.excel_final_destino import registrar_execucao_excel_final, obter_periodos_trimestre
from Src.infrastructure.ocr.ocr_pdf import OCR_ENABLED
from Src.Database.database import DatabasePMPV
from Src.infrastructure.exporters.excel_consolidado import ExcelConsolidado

logger = logging.getLogger(__name__)

class TelaConciliador(ctk.CTkFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.path_rec = tk.StringVar()
        self.path_desp = tk.StringVar()
        self.var_excel_bonito = tk.BooleanVar(value=False)
        self.status_ocr_txt = "✅ MOTOR OCR ATIVO" if OCR_ENABLED else "❌ OCR NÃO ENCONTRADO"
        self.cor_ocr = "#27ae60" if OCR_ENABLED else "#c0392b"
        self.consolidacao = ServicosConsolidacao()
        self._tmp_zip_extract_dirs = []
        self._destino_excel_concilia = None

        self._setup_ui()

    def _setup_ui(self):
        # HEADER
        self.header_frame = ctk.CTkFrame(self, height=80, corner_radius=0, fg_color=ui.COR_HEADER)
        self.header_frame.pack(fill="x")
        self.header_frame.pack_propagate(False)
        ctk.CTkLabel(self.header_frame, text="Conciliador Financeiro",
                     font=ui.FONTE_TITULO, text_color=ui.COR_TEXTO_TITULO
                     ).pack(side="left", padx=ui.ESP_LG, pady=ui.ESP_LG)

        self.ocr_badge = ctk.CTkLabel(self.header_frame, text=self.status_ocr_txt, fg_color=self.cor_ocr,
                                     text_color="white", corner_radius=10, font=ui.FONTE_LABEL, padx=10)
        self.ocr_badge.pack(side="right", padx=ui.ESP_LG)

        # SELEÇÃO
        self.selection_frame = ctk.CTkFrame(self)
        self.selection_frame.pack(fill="x", padx=20, pady=10)
        
        self._criar_input_folder(self.selection_frame, "📂 Pasta de RECEITAS", self.path_rec, self.sel_rec, "green")
        ctk.CTkFrame(self.selection_frame, height=2, fg_color="gray30").pack(fill="x", padx=10, pady=10)
        self._criar_input_folder(self.selection_frame, "📂 Pasta de DESPESAS", self.path_desp, self.sel_desp, "red")

        # BOTÕES
        self.btn_run = ctk.CTkButton(self, text="⚡ PROCESSAR E CONCILIAR", command=self.iniciar_thread,
                                    font=("Roboto", 16, "bold"), height=50,
                                    fg_color=ui.COR_PRIMARIA, hover_color=ui.COR_PRIMARIA_HOVER)
        self.btn_run.pack(fill="x", padx=40, pady=(ui.ESP_LG, ui.ESP_SM))

        self.chk_excel_bonito = ctk.CTkCheckBox(
            self,
            text="Gerar Excel bonito (layout detalhado)",
            variable=self.var_excel_bonito,
            onvalue=True,
            offvalue=False,
            font=("Roboto", 12, "bold"),
        )
        self.chk_excel_bonito.pack(anchor="w", padx=40, pady=(0, 6))

        periodo_frame = ctk.CTkFrame(self, fg_color="transparent")
        periodo_frame.pack(fill="x", padx=40, pady=(0, 10))
        ctk.CTkLabel(periodo_frame, text="Período:", font=("Roboto", 13, "bold"), width=70).pack(side="left")
        self.entry_periodo = ctk.CTkEntry(periodo_frame, placeholder_text="ex: Dez/2025", width=160)
        self.entry_periodo.insert(0, datetime.now().strftime("%b/%Y"))
        self.entry_periodo.pack(side="left", padx=(8, 0))

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
        """Thread-safe: agenda a escrita no log na thread principal do Tkinter.

        Pode ser chamado tanto da UI quanto da thread de processamento (é usado
        como callback por RegrasConcilia.processar_arquivos). Tkinter não é
        thread-safe, então o widget só é tocado via `after`.
        """
        self.after(0, self._log_message_ui, msg)

    def _log_message_ui(self, msg):
        """Escrita real no widget — sempre executada na thread principal."""
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

        nome_padrao = f"Conciliacao_{datetime.now().strftime('%H%M%S')}.xlsx"
        destino = filedialog.asksaveasfilename(
            title="Salvar relatório de Conciliação",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")],
            initialfile=nome_padrao,
        )
        if not destino:
            self.log_message("Operação cancelada: destino do Excel não informado.")
            return

        self._destino_excel_concilia = Path(destino)
        self.btn_run.configure(state="disabled", text="Processando...")
        self.progress.start()
        threading.Thread(target=self.rodar_processamento, daemon=True).start()

    def rodar_processamento(self):
        try:
            p_rec = Path(self.path_rec.get()) if self.path_rec.get() else None
            p_desp = Path(self.path_desp.get()) if self.path_desp.get() else None

            arquivos_rec = self._coletar_pdfs(p_rec) if p_rec else []
            arquivos_desp = self._coletar_pdfs(p_desp) if p_desp else []

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

            caminho_final = self._destino_excel_concilia or (Path(os.getcwd()) / f"Conciliacao_{datetime.now().strftime('%H%M%S')}.xlsx")

            layout_bonito = bool(self.var_excel_bonito.get())
            if layout_bonito:
                self.log_message("Modo Excel bonito ativado.")

            tot_rec, tot_desp = ExcelConcilia.gerar_relatorio(caminho_final, itens, layout_bonito=layout_bonito)
            saldo_receita_menos_despesa = tot_rec - tot_desp
            saldo_despesa_menos_receita = tot_desp - tot_rec
            self._ultimo_saldo_rp = saldo_despesa_menos_receita
            self._ultimos_itens_concilia = itens

            self.log_message("--- RESUMO DA CONCILIAÇÃO ---")
            self.log_message(f"Total Receita: R$ {format_brl_plain(tot_rec)}")
            self.log_message(f"Total Despesa: R$ {format_brl_plain(tot_desp)}")
            self.log_message(f"Saldo (Despesa - Receita): R$ {format_brl_plain(saldo_despesa_menos_receita)}")
            self.log_message(f"Conferência (Receita - Despesa): R$ {format_brl_plain(saldo_receita_menos_despesa)}")
            self.log_message(f"CONCLUÍDO! Salvo em: {caminho_final}")

            # Atualizações de UI (janelas/botões) na thread principal.
            msg = f"Finalizado!\nSaldo (Despesa - Receita): R$ {format_brl_plain(saldo_despesa_menos_receita)}"
            self.after(0, self._on_processamento_sucesso, msg)

        except Exception as e:
            logger.exception("Falha no processamento da conciliação")
            self.after(0, self._on_processamento_erro, str(e))
        finally:
            self._limpar_temporarios_zip()
            # restaurar_interface toca widgets → sempre na thread principal.
            self.after(0, self.restaurar_interface)

    def _on_processamento_sucesso(self, msg: str):
        """Executado na thread principal após o processamento bem-sucedido."""
        messagebox.showinfo("Sucesso", msg)
        self.btn_salvar_scg.configure(state="normal")
        self.btn_excel_final.configure(state="normal")

    def _on_processamento_erro(self, detalhe: str):
        """Executado na thread principal quando o processamento falha."""
        self._log_message_ui(f"ERRO: {detalhe}")
        messagebox.showerror(
            "Erro na Conciliação",
            "Não foi possível concluir a conciliação.\n\n"
            "Verifique se as pastas/PDFs estão acessíveis e tente novamente.\n\n"
            f"Detalhe técnico: {detalhe}",
        )

    def _coletar_pdfs(self, pasta: Path):
        """Coleta PDFs diretos e também PDFs contidos em ZIPs dentro da pasta."""
        if not pasta or not pasta.exists():
            return []

        pdfs = list(pasta.rglob("*.pdf"))
        zips = list(pasta.rglob("*.zip"))

        if zips:
            self.log_message(f"Detectado(s) {len(zips)} ZIP(s) em {pasta.name}. Extraindo PDFs...")

        for zip_path in zips:
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    nomes_pdf = [n for n in zf.namelist() if n.lower().endswith(".pdf")]
                    if not nomes_pdf:
                        continue

                    tmp_dir = tempfile.mkdtemp(prefix="concilia_zip_")
                    self._tmp_zip_extract_dirs.append(tmp_dir)

                    for nome in nomes_pdf:
                        zf.extract(nome, path=tmp_dir)
                        pdfs.append(Path(tmp_dir) / nome)

                self.log_message(f"ZIP lido: {zip_path.name} ({len(nomes_pdf)} PDF(s))")
            except Exception as e:
                self.log_message(f"Falha ao ler ZIP {zip_path.name}: {e}")

        return pdfs

    def _limpar_temporarios_zip(self):
        """Remove diretórios temporários usados para extração de ZIPs."""
        for d in self._tmp_zip_extract_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        self._tmp_zip_extract_dirs = []

    def _salvar_rp_scg(self):
        periodo = self.entry_periodo.get().strip()
        if not periodo:
            periodo = simpledialog.askstring("Salvar RP", "Digite o período (ex: Dez/2025):", initialvalue="Dez/2025")
        if not periodo:
            return

        n_itens = len(getattr(self, "_ultimos_itens_concilia", []))
        saldo = getattr(self, "_ultimo_saldo_rp", 0.0)
        if not messagebox.askyesno("Confirmar salvamento",
                                   f"Salvar Conciliação RP no banco de dados?\n\n"
                                   f"Período: {periodo}\n"
                                   f"Saldo RP: R$ {saldo:,.2f}\n"
                                   f"Itens: {n_itens}"):
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

        periodo_salvar = self.entry_periodo.get().strip() or "Geral"

        try:
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