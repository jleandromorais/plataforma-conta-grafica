import customtkinter as ctk
from tkinter import messagebox, simpledialog
from database import DatabasePMPV

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class ModuloSCG(ctk.CTkToplevel):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.title("📊 Consolidação SCG - Sistema de Conta Gráfica")
        self.geometry("900x700")
        
        self.db = DatabasePMPV()
        self.periodo_atual = None
        
        self._setup_ui()
        self._carregar_periodos()
    
    def _setup_ui(self):
        # HEADER
        header = ctk.CTkFrame(self, height=60, corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="💼 Consolidação SCG", 
                     font=("Roboto", 24, "bold")).pack(pady=15)
        
        # SELEÇÃO DE PERÍODO
        frame_periodo = ctk.CTkFrame(self)
        frame_periodo.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(frame_periodo, text="Período:").pack(side="left", padx=10)
        
        self.combo_periodo = ctk.CTkComboBox(frame_periodo, width=200,
                                             command=self._on_periodo_change)
        self.combo_periodo.pack(side="left", padx=10)
        
        ctk.CTkButton(frame_periodo, text="➕ Novo Período",
                     command=self._criar_periodo).pack(side="left", padx=5)
        
        # VALORES DOS MÓDULOS (somente leitura)
        frame_modulos = ctk.CTkFrame(self)
        frame_modulos.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(frame_modulos, text="📋 Valores dos Módulos",
                     font=("Roboto", 16, "bold")).pack(pady=10)
        
        # CGR
        self._criar_linha_valor(frame_modulos, "CGR (Auditoria XML):", "cgr")
        # RET
        self._criar_linha_valor(frame_modulos, "RET (Encargos):", "ret")
        # RP
        self._criar_linha_valor(frame_modulos, "RP (Conciliação):", "rp")
        
        # VALORES MANUAIS
        frame_manual = ctk.CTkFrame(self)
        frame_manual.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(frame_manual, text="✍️ Valores Manuais",
                     font=("Roboto", 16, "bold")).pack(pady=10)
        
        # RPV
        row_rpv = ctk.CTkFrame(frame_manual, fg_color="transparent")
        row_rpv.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row_rpv, text="RPV:", width=150).pack(side="left")
        self.entry_rpv = ctk.CTkEntry(row_rpv, width=200)
        self.entry_rpv.pack(side="left", padx=10)
        
        # CGF
        row_cgf = ctk.CTkFrame(frame_manual, fg_color="transparent")
        row_cgf.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(row_cgf, text="CGF:", width=150).pack(side="left")
        self.entry_cgf = ctk.CTkEntry(row_cgf, width=200)
        self.entry_cgf.pack(side="left", padx=10)
        
        ctk.CTkButton(frame_manual, text="💾 Salvar RPV e CGF",
                     command=self._salvar_rpv_cgf,
                     fg_color="#3498db").pack(pady=10)
        
        # CÁLCULO FINAL
        frame_scg = ctk.CTkFrame(self, fg_color="#1a1a1a")
        frame_scg.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(frame_scg, text="🎯 Fórmula: SCG = RPV(CGR + CGF) + RET + RP",
                     font=("Roboto", 12)).pack(pady=10)
        
        ctk.CTkButton(frame_scg, text="⚡ CALCULAR SCG",
                     command=self._calcular_scg,
                     font=("Roboto", 16, "bold"),
                     height=50,
                     fg_color="#e74c3c").pack(pady=10)
        
        self.lbl_scg = ctk.CTkLabel(frame_scg, text="SCG: R$ 0,00",
                                    font=("Roboto", 28, "bold"),
                                    text_color="#f39c12")
        self.lbl_scg.pack(pady=15)
    
    def _criar_linha_valor(self, parent, texto, key):
        """Cria linha com label e valor (somente leitura)"""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkLabel(row, text=texto, width=200).pack(side="left")
        
        lbl = ctk.CTkLabel(row, text="R$ 0,00", width=200,
                          fg_color="#2c3e50", corner_radius=5,
                          font=("Roboto", 14, "bold"))
        lbl.pack(side="left", padx=10)
        
        # Guardar referência
        setattr(self, f"lbl_{key}", lbl)
    
    def _carregar_periodos(self):
        """Carrega lista de períodos do banco"""
        periodos = self.db.listar_periodos()
        if periodos:
            nomes = [p['periodo'] for p in periodos]
            self.combo_periodo.configure(values=nomes)
            self.combo_periodo.set(nomes[0])
            self._on_periodo_change(nomes[0])
    
    def _criar_periodo(self):
        """Cria novo período"""
        nome = simpledialog.askstring("Novo Período", 
                                     "Nome do período (ex: Q1 2026):")
        if nome:
            self.db.criar_periodo_consolidacao(nome)
            self._carregar_periodos()
            messagebox.showinfo("Sucesso", f"Período '{nome}' criado!")
    
    def _on_periodo_change(self, periodo):
        """Atualiza tela quando período muda"""
        self.periodo_atual = periodo
        dados = self.db.buscar_consolidacao(periodo)
        
        if dados:
            self.lbl_cgr.configure(text=f"R$ {dados['cgr']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            self.lbl_ret.configure(text=f"R$ {dados['ret']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            self.lbl_rp.configure(text=f"R$ {dados['rp']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            
            self.entry_rpv.delete(0, "end")
            self.entry_rpv.insert(0, str(dados['rpv']))
            
            self.entry_cgf.delete(0, "end")
            self.entry_cgf.insert(0, str(dados['cgf']))
            
            scg_fmt = f"R$ {dados['scg']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            self.lbl_scg.configure(text=f"SCG: {scg_fmt}")
    
    def _salvar_rpv_cgf(self):
        """Salva RPV e CGF"""
        if not self.periodo_atual:
            messagebox.showwarning("Aviso", "Selecione um período!")
            return
        
        try:
            rpv = float(self.entry_rpv.get().replace(",", "."))
            cgf = float(self.entry_cgf.get().replace(",", "."))
            
            self.db.atualizar_rpv_cgf(self.periodo_atual, rpv, cgf)
            messagebox.showinfo("Sucesso", "RPV e CGF salvos!")
            self._on_periodo_change(self.periodo_atual)
        except ValueError:
            messagebox.showerror("Erro", "Digite valores numéricos válidos!")
    
    def _calcular_scg(self):
        """Calcula e exibe SCG"""
        if not self.periodo_atual:
            messagebox.showwarning("Aviso", "Selecione um período!")
            return
        
        scg = self.db.calcular_scg(self.periodo_atual)
        scg_fmt = f"R$ {scg:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        
        self.lbl_scg.configure(text=f"SCG: {scg_fmt}")
        messagebox.showinfo("SCG Calculado", f"SCG = {scg_fmt}")

if __name__ == "__main__":
    app = ModuloSCG()
    app.mainloop()
