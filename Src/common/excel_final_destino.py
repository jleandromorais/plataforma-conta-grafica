from __future__ import annotations

from pathlib import Path
import os
from tkinter import messagebox
import customtkinter as ctk

from Src.Database.database import DatabasePMPV
from Src.common.periodos import normalizar_periodo, MESES_ABREVS as _MESES_ABREVS_SET

# Arquivo Excel único e fixo — sempre salvo na pasta Downloads do utilizador
EXCEL_FIXO_NOME = "Excel_Final_ContaGrafica"
EXCEL_FIXO_PATH = str(Path.home() / "Downloads" / f"{EXCEL_FIXO_NOME}.xlsx")


def _normalizar_periodo(periodo: str | None) -> str:
    return normalizar_periodo(periodo) or "Geral"


def obter_periodos_trimestre(periodo_atual: str | None = None) -> list[str]:
    """
    Retorna os meses do trimestre ativo para o Excel consolidado.

    Lógica:
    - Lê o trimestre_ativo do banco (gravado pelo PMPV com os 3 meses reais).
    - Filtra entradas inválidas ('RET/25', 'Q1/2026', etc.).
    - Se o trimestre já contiver >= 2 meses válidos, devolve-o sem alterar o banco.
    - Só reconstrói via ret_itens quando o trimestre está vazio ou tem < 2 meses válidos.
    - Nunca sobrescreve um trimestre válido existente.
    """
    _ABREVS = set(_MESES_ABREVS_SET)

    def _valido(p: str) -> bool:
        parts = (p or "").strip().split("/")
        if len(parts) != 2:
            return False
        ab, an = parts[0].strip().capitalize()[:3], parts[1].strip()
        return ab in _ABREVS and len(an) == 4 and an.isdigit()

    def _normalizar_abrev(p: str) -> str:
        parts = (p or "").strip().split("/")
        if len(parts) != 2:
            return p.strip().lower()
        ab = parts[0].strip().capitalize()[:3]
        an = parts[1].strip()
        # aceita ano de 2 ou 4 dígitos
        if len(an) == 2:
            an = "20" + an
        return f"{ab}/{an}".lower()

    with DatabasePMPV() as db:
        meses_raw = db.buscar_trimestre_ativo()
        meses = [m for m in meses_raw if _valido(m)]

        if periodo_atual and len(meses) >= 2:
            norm = normalizar_periodo(periodo_atual) or periodo_atual
            if _normalizar_abrev(norm) in {_normalizar_abrev(m) for m in meses}:
                return meses
            periodos_ret = db.buscar_periodos_ret_para_trimestre(norm)
            if periodos_ret:
                return periodos_ret
            return [norm]

        if len(meses) >= 2:
            return meses

        if periodo_atual:
            norm = normalizar_periodo(periodo_atual) or periodo_atual
            periodos_ret = db.buscar_periodos_ret_para_trimestre(norm)
            if periodos_ret:
                db.salvar_trimestre_ativo(periodos_ret)
                return periodos_ret
            return [norm]

        return meses


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


def registrar_execucao_excel_final(
    etapa: str,
    periodo: str | None = None,
    parent=None,
) -> tuple[str, str, str, int] | None:
    """
    Registra a execução da etapa e retorna sempre o caminho do Excel fixo.

    Returns:
        tuple(caminho_arquivo, nome_sessao, periodo_normalizado, execucao)
    """
    periodo_norm = _normalizar_periodo(periodo)
    etapa_norm = (etapa or "").strip() or "ETAPA"

    # Garante que a sessão fixa está ativa no banco
    with DatabasePMPV() as db:
        db.salvar_sessao_excel_final(EXCEL_FIXO_NOME, EXCEL_FIXO_PATH)
        execucao = db.registrar_execucao_excel_final(
            nome_sessao=EXCEL_FIXO_NOME,
            periodo=periodo_norm,
            etapa=etapa_norm,
            caminho_arquivo=EXCEL_FIXO_PATH,
        )
        return EXCEL_FIXO_PATH, EXCEL_FIXO_NOME, periodo_norm, execucao


def novo_excel_final(parent=None) -> bool:
    """Apaga o arquivo Excel fixo e zera as execuções para começar do zero."""
    msg = (
        f"Zerar o Excel Final?\n\n"
        f"Arquivo: {Path(EXCEL_FIXO_PATH).name}\n\n"
        f"O arquivo atual será apagado e todas as execuções registradas serão removidas.\n"
        f"Os dados dos módulos no banco de dados NÃO serão apagados."
    )
    if not messagebox.askyesno("Zerar Excel Final", msg, parent=parent):
        return False

    with DatabasePMPV() as db:
        db.zerar_sessao_excel_final(EXCEL_FIXO_NOME, EXCEL_FIXO_PATH)

    if Path(EXCEL_FIXO_PATH).exists():
        try:
            os.remove(EXCEL_FIXO_PATH)
        except OSError:
            pass

    messagebox.showinfo(
        "Excel zerado",
        "Excel Final zerado com sucesso.\nO próximo módulo criará um arquivo novo.",
        parent=parent,
    )
    return True


def remover_excel_final_ativo(parent=None) -> tuple[bool, str]:
    """Desativa a sessão ativa do Excel final e opcionalmente exclui o arquivo físico."""
    with DatabasePMPV() as db:
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
