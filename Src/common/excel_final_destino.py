from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
from tkinter import filedialog, messagebox, simpledialog

from Src.Database.database import DatabasePMPV

def escolher_destino_excel_final(periodo: str | None = None, parent=None) -> str | None:
    """Retorna o destino do Excel final, reutilizando o mesmo arquivo pela sessão/nome informado."""
    db = DatabasePMPV()
    try:
        sessao_ativa = db.buscar_sessao_excel_final_ativa()
        nome_inicial = (periodo or "").strip() or (sessao_ativa or {}).get("nome", "Geral")

        nome_sessao = simpledialog.askstring(
            "Sessão do Excel Final",
            "Nome da sessão do Excel Final (Módulo 9):\nUse o mesmo nome para atualizar o mesmo arquivo.",
            initialvalue=nome_inicial,
            parent=parent,
        )
        if not nome_sessao or not nome_sessao.strip():
            return None

        nome_sessao = nome_sessao.strip()
        sessao_existente = db.buscar_sessao_excel_final_por_nome(nome_sessao)
        if sessao_existente:
            caminho_existente = sessao_existente.get("caminho_arquivo", "")
            if caminho_existente:
                db.salvar_sessao_excel_final(nome_sessao, caminho_existente)
                return caminho_existente

        nome_base_sessao = "_".join(nome_sessao.split())
        p_slug = (periodo or "completo").replace("/", "-").strip() or "completo"
        nome_padrao = f"Modulo9_{nome_base_sessao}_{p_slug}.xlsx"

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


def remover_excel_final_ativo(parent=None) -> tuple[bool, str]:
    """Desativa a sessão ativa do Excel final e opcionalmente exclui o arquivo físico."""
    db = DatabasePMPV()
    try:
        sessao_ativa = db.buscar_sessao_excel_final_ativa()
        if not sessao_ativa:
            return False, "Nenhuma sessão ativa do Excel final foi encontrada."

        nome = sessao_ativa.get("nome", "Sessão ativa")
        caminho = sessao_ativa.get("caminho_arquivo", "")
        remover_arquivo = messagebox.askyesno(
            "Remover Excel Final",
            f"Desvincular a sessão ativa '{nome}'?\n\nArquivo: {caminho}\n\nSim = desvincular e apagar arquivo\nNão = só desvincular do sistema",
            parent=parent,
        )

        erro_arquivo = ""
        if remover_arquivo and caminho:
            try:
                if Path(caminho).exists():
                    os.remove(caminho)
            except OSError as exc:
                erro_arquivo = f"\nArquivo não removido: {exc}"

        db.desativar_sessao_excel_final_ativa()
        return True, f"Sessão '{nome}' removida do fluxo do Módulo 9.{erro_arquivo}"
    finally:
        db.fechar()
