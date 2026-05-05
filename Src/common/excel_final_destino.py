from __future__ import annotations

from pathlib import Path
import os
import datetime
from tkinter import filedialog, messagebox
import customtkinter as ctk

from Src.Database.database import DatabasePMPV
from Src.common.periodos import normalizar_periodo


def _normalizar_periodo(periodo: str | None) -> str:
    return normalizar_periodo(periodo) or "Geral"


def obter_periodos_trimestre(periodo_atual: str | None = None) -> list[str]:
    """
    Retorna os 3 meses do trimestre para o Excel consolidado.

    Garante que apenas períodos no formato 'Mmm/YYYY' são devolvidos.
    Se o trimestre_ativo contiver entradas inválidas (ex: 'RET/25', 'Q1/2026'),
    reconstrói automaticamente a partir dos ret_itens reais.
    """
    _ABREVS = {"Jan","Fev","Mar","Abr","Mai","Jun",
               "Jul","Ago","Set","Out","Nov","Dez"}

    def _valido(p: str) -> bool:
        parts = (p or "").strip().split("/")
        if len(parts) != 2:
            return False
        ab, an = parts[0].strip().capitalize()[:3], parts[1].strip()
        return ab in _ABREVS and len(an) == 4 and an.isdigit()

    db = DatabasePMPV()
    try:
        meses_raw = db.buscar_trimestre_ativo()
        # Filtrar apenas períodos válidos — descarta 'RET/25', 'Q1/2026', etc.
        meses = [m for m in meses_raw if _valido(m)]

        if not periodo_atual:
            return meses if meses else []

        norm = normalizar_periodo(periodo_atual) or periodo_atual
        meses_norm = [normalizar_periodo(m) or m for m in meses]
        periodo_no_trimestre = (norm in meses_norm or periodo_atual in meses_norm)

        if not meses or not periodo_no_trimestre:
            # Trimestre inválido ou não corresponde — reconstruir via ret_itens
            periodos_ret = db.buscar_periodos_ret_para_trimestre(norm)
            if periodos_ret:
                meses = periodos_ret
                db.salvar_trimestre_ativo(meses)  # corrige o BD
            else:
                meses = [norm]
        else:
            if norm not in meses_norm and periodo_atual not in meses_norm:
                meses.append(norm)

        return meses if meses else [norm]
    finally:
        db.fechar()


def solicitar_periodo_excel_final(
    parent=None,
    titulo: str = "Período do Excel Final",
    mensagem: str = "Informe o período (ex: Dez/2025):",
    valor_inicial: str = "",
) -> str | None:
    """Solicita período em modal CTk e retorna string normalizada.

    Retorna `None` quando cancelado. Não aceita período vazio.
    """
    modal = ctk.CTkToplevel(parent)
    modal.title(titulo)
    modal.geometry("520x220")
    modal.resizable(False, False)

    result: str | None = None

    ctk.CTkLabel(modal, text=titulo, font=("Roboto", 15, "bold")).pack(pady=(14, 8), padx=14, anchor="w")
    ctk.CTkLabel(modal, text=mensagem, font=("Roboto", 12)).pack(pady=(0, 8), padx=14, anchor="w")

    entry = ctk.CTkEntry(modal, placeholder_text="Ex.: Dez/2025")
    entry.pack(fill="x", padx=14, pady=(0, 6))
    if valor_inicial:
        entry.insert(0, valor_inicial)
    entry.focus_set()

    info_label = ctk.CTkLabel(modal, text="", text_color="#ff6b6b", font=("Roboto", 11))
    info_label.pack(fill="x", padx=14, pady=(0, 4), anchor="w")

    btn_frame = ctk.CTkFrame(modal)
    btn_frame.pack(side="bottom", fill="x", pady=12)

    def on_ok():
        nonlocal result
        periodo = _normalizar_periodo(entry.get())
        if not periodo:
            info_label.configure(text="Período obrigatório para evitar mistura de sessões.")
            return
        result = periodo
        modal.destroy()

    def on_cancel():
        modal.destroy()

    ctk.CTkButton(btn_frame, text="Cancelar", command=on_cancel, width=120).pack(side="right", padx=12)
    ctk.CTkButton(btn_frame, text="Confirmar", command=on_ok, width=120, fg_color="#2196F3").pack(side="right")

    modal.transient(parent)
    modal.grab_set()
    modal.wait_window()
    return result

def escolher_destino_excel_final(periodo: str | None = None, parent=None) -> tuple[str, str] | None:
    """Mostra um modal CTk para escolher/criar a sessão do Excel final.

    Retorna uma tupla `(caminho_arquivo, nome_sessao)` ou `None` se cancelado.
    """
    db = DatabasePMPV()
    result = None
    try:
        sessoes = db.listar_sessoes_excel_final()
        sessao_ativa = db.buscar_sessao_excel_final_ativa() or {}
        nome_ativo = str(sessao_ativa.get("nome") or "Sessão ativa")
        caminho_ativo = str(sessao_ativa.get("caminho_arquivo") or "").strip()

        modal_parent = parent
        modal = ctk.CTkToplevel(modal_parent)
        modal.title("Excel Final (Módulo 9)")
        modal.geometry("680x320")
        modal.resizable(False, False)

        sel_var = ctk.IntVar(value=1)

        ctk.CTkLabel(modal, text="Como deseja atualizar o Excel final?", font=("Roboto", 14, "bold")).pack(pady=(10, 6))

        frame_opts = ctk.CTkFrame(modal)
        frame_opts.pack(fill="x", padx=12, pady=6)

        rb1 = ctk.CTkRadioButton(frame_opts, text=f"Usar Excel ativo: {nome_ativo}", variable=sel_var, value=1)
        rb1.grid(row=0, column=0, sticky="w", padx=6, pady=6)

        opcoes = [s for s in sessoes if s.get("caminho_arquivo")]
        rb2 = ctk.CTkRadioButton(frame_opts, text="Escolher Excel existente", variable=sel_var, value=2)
        rb2.grid(row=1, column=0, sticky="w", padx=6, pady=6)
        vals = [str(s.get("nome", "Sessao")) for s in opcoes]
        opt_var = ctk.StringVar(value=vals[0] if vals else "")
        dropdown = ctk.CTkOptionMenu(frame_opts, values=vals or ["(vazio)"], variable=opt_var)
        dropdown.grid(row=1, column=1, sticky="w", padx=6)

        rb3 = ctk.CTkRadioButton(frame_opts, text="Criar novo Excel", variable=sel_var, value=3)
        rb3.grid(row=2, column=0, sticky="w", padx=6, pady=6)
        entry_nome = ctk.CTkEntry(frame_opts, placeholder_text="Nome da nova sessão (ex: Dez/2025)")
        entry_nome.grid(row=2, column=1, sticky="we", padx=6)
        frame_opts.grid_columnconfigure(1, weight=1)

        # Ações
        btn_frame = ctk.CTkFrame(modal)
        btn_frame.pack(side="bottom", fill="x", pady=12)

        def on_ok():
            nonlocal result
            escolha = int(sel_var.get())
            if escolha == 1:
                if caminho_ativo:
                    db.salvar_sessao_excel_final(nome_ativo, caminho_ativo)
                    result = (caminho_ativo, nome_ativo)
                else:
                    messagebox.showwarning("Excel Final (Módulo 9)", "Não há Excel ativo. Escolha existente ou crie novo.", parent=modal)
                    return
            elif escolha == 2:
                if not opcoes:
                    messagebox.showwarning("Excel Final (Módulo 9)", "Não há sessões existentes. Crie uma nova.", parent=modal)
                    return
                sel_name = opt_var.get()
                selecionada = next((s for s in opcoes if str(s.get("nome")) == sel_name), None)
                if selecionada and selecionada.get("caminho_arquivo"):
                    caminho = str(selecionada.get("caminho_arquivo"))
                    db.salvar_sessao_excel_final(sel_name, caminho)
                    result = (caminho, sel_name)
                else:
                    messagebox.showwarning("Excel Final (Módulo 9)", "Sessão selecionada inválida.", parent=modal)
                    return
            else:
                nome_sessao = (entry_nome.get() or "").strip() or (periodo or "Geral")
                if not nome_sessao:
                    messagebox.showwarning("Nome inválido", "Digite um nome para a nova sessão.", parent=modal)
                    return
                nome_base = "_".join(nome_sessao.split())
                p_slug = (periodo or "completo").replace("/", "-")
                nome_padrao = f"Modulo9_{nome_base}_{p_slug}.xlsx"
                caminho = filedialog.asksaveasfilename(
                    title="Salvar no Excel Final (Módulo 9)",
                    initialfile=nome_padrao,
                    defaultextension=".xlsx",
                    filetypes=[("Planilha Excel", "*.xlsx"), ("Todos os arquivos", "*.*")],
                    parent=modal,
                )
                if not caminho:
                    return
                db.salvar_sessao_excel_final(nome_sessao, str(Path(caminho)))
                result = (caminho, nome_sessao)

            modal.destroy()

        def on_cancel():
            modal.destroy()

        ctk.CTkButton(btn_frame, text="Cancelar", command=on_cancel, width=120).pack(side="right", padx=12)
        ctk.CTkButton(btn_frame, text="OK", command=on_ok, width=120, fg_color="#2196F3").pack(side="right")

        modal.transient(parent)
        modal.grab_set()
        modal.wait_window()

        return result
    finally:
        db.fechar()


def registrar_execucao_excel_final(
    etapa: str,
    periodo: str | None = None,
    parent=None,
) -> tuple[str, str, str, int] | None:
    """
    Resolve destino/sessao e registra a execução da etapa no fluxo cumulativo.
    Usa a sessão ativa automaticamente; só abre modal quando não há sessão ativa.

    Returns:
        tuple(caminho_arquivo, nome_sessao, periodo_normalizado, execucao) ou None.
    """
    db_check = DatabasePMPV()
    try:
        sessao_ativa = db_check.buscar_sessao_excel_final_ativa() or {}
        caminho_ativo = str(sessao_ativa.get("caminho_arquivo") or "").strip()
        nome_ativo = str(sessao_ativa.get("nome") or "").strip()
    finally:
        db_check.fechar()

    if caminho_ativo and nome_ativo:
        caminho, nome_sessao = caminho_ativo, nome_ativo
    else:
        # Sem sessão ativa: cria uma nova com nome fixo (sem timestamp)
        periodo_norm_tmp = _normalizar_periodo(periodo) or "Geral"
        p_slug = periodo_norm_tmp.replace("/", "-")
        nome_sessao = f"Modulo9_{p_slug}"
        nome_arquivo_auto = f"Modulo9_{p_slug}.xlsx"
        db_dir = Path(__file__).resolve().parents[2]
        caminho = str(db_dir / nome_arquivo_auto)

        db_auto = DatabasePMPV()
        try:
            db_auto.salvar_sessao_excel_final(nome_sessao, caminho)
        finally:
            db_auto.fechar()

    periodo_norm = _normalizar_periodo(periodo)
    etapa_norm = (etapa or "").strip() or "ETAPA"

    # Incrementa o contador de execuções no banco
    db = DatabasePMPV()
    try:
        execucao = db.registrar_execucao_excel_final(
            nome_sessao=nome_sessao,
            periodo=periodo_norm,
            etapa=etapa_norm,
            caminho_arquivo=str(Path(caminho)),
        )
        return str(Path(caminho)), nome_sessao, periodo_norm, execucao
    finally:
        db.fechar()


def novo_excel_final(parent=None) -> bool:
    """Limpa a sessão ativa para que o próximo módulo crie um arquivo Excel novo."""
    db = DatabasePMPV()
    try:
        sessao_ativa = db.buscar_sessao_excel_final_ativa()
        nome = (sessao_ativa or {}).get("nome", "")
        arquivo = (sessao_ativa or {}).get("caminho_arquivo", "")

        msg = "Iniciar um novo Excel Final?\n\n"
        if arquivo:
            msg += f"Sessão atual: {nome}\nArquivo: {Path(arquivo).name}\n\n"
        msg += "Na próxima execução de qualquer módulo será criado um arquivo novo."

        if not messagebox.askyesno("Novo Excel Final", msg, parent=parent):
            return False

        db.desativar_sessao_excel_final_ativa()
        messagebox.showinfo(
            "Novo Excel pronto",
            "Sessão zerada.\nO próximo módulo criará um arquivo Excel novo.",
            parent=parent,
        )
        return True
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
