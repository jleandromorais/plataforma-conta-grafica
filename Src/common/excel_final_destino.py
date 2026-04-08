from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog

from Src.Database.database import DatabasePMPV

def escolher_destino_excel_final(periodo: str | None = None, parent=None) -> str | None:
    """Retorna o destino do Excel final, reutilizando a sessão ativa quando possível."""
    db = DatabasePMPV()
    try:
        sessao_ativa = db.buscar_sessao_excel_final_ativa()
        if sessao_ativa:
            nome = sessao_ativa.get("nome", "Sessão ativa")
            caminho = sessao_ativa.get("caminho_arquivo", "")
            usar_existente = messagebox.askyesnocancel(
                "Sessão do Excel Final",
                f"Usar a sessão ativa do Módulo 9?\n\nSessão: {nome}\nArquivo: {caminho}\n\nSim = reutilizar\nNão = escolher outra\nCancelar = sair",
                parent=parent,
            )
            if usar_existente is None:
                return None
            if usar_existente:
                return caminho

        nome_sessao = simpledialog.askstring(
            "Sessão do Excel Final",
            "Nome da sessão do Excel Final (Módulo 9):",
            initialvalue="Geral",
            parent=parent,
        )
        if not nome_sessao or not nome_sessao.strip():
            return None

        nome_sessao = nome_sessao.strip()
        nome_base_sessao = "_".join(nome_sessao.split())

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        p_slug = (periodo or "completo").replace("/", "-").strip() or "completo"
        nome_padrao = f"Modulo9_{nome_base_sessao}_{p_slug}_{ts}.xlsx"

        caminho = filedialog.asksaveasfilename(
            title="Salvar no Excel Final (Módulo 9)",
            initialfile=nome_padrao,
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx"), ("Todos os arquivos", "*.*")],
        )

        if not caminho:
            return None

        db.salvar_sessao_excel_final(nome_sessao, str(Path(caminho)))
        return caminho
    finally:
        db.fechar()
