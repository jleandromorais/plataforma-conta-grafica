
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from Src.common import excel_final_destino as efd


@pytest.fixture
def mock_db():
    """Mocka DatabasePMPV usado dentro do módulo (context manager)."""
    with patch("Src.common.excel_final_destino.DatabasePMPV") as mock_cls:
        instance = MagicMock()
        mock_cls.return_value.__enter__ = MagicMock(return_value=instance)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        yield instance


class TestNormalizarPeriodoHelper:
    def test_valido(self):
        assert efd._normalizar_periodo("jan/26") == "Jan/2026"

    def test_none_vira_geral(self):
        assert efd._normalizar_periodo(None) == "Geral"

    def test_vazio_vira_geral(self):
        assert efd._normalizar_periodo("") == "Geral"

    def test_invalido_preserva_texto(self):
        # normalizar_periodo retorna o texto original quando não casa
        assert efd._normalizar_periodo("xyz") == "xyz"


class TestObterPeriodosTrimestre:
    def test_trimestre_valido_com_dois_meses_retorna_direto(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = ["Jan/2026", "Fev/2026", "Mar/2026"]
        resultado = efd.obter_periodos_trimestre()
        assert resultado == ["Jan/2026", "Fev/2026", "Mar/2026"]

    def test_filtra_entradas_invalidas(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = ["Jan/2026", "RET/25", "Q1/2026", "Fev/2026"]
        resultado = efd.obter_periodos_trimestre()
        assert resultado == ["Jan/2026", "Fev/2026"]

    def test_trimestre_vazio_sem_periodo_atual_retorna_vazio(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = []
        resultado = efd.obter_periodos_trimestre()
        assert resultado == []

    def test_trimestre_vazio_reconstroi_via_ret(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = []
        mock_db.buscar_periodos_ret_para_trimestre.return_value = ["Jan/2026", "Fev/2026", "Mar/2026"]
        resultado = efd.obter_periodos_trimestre("jan/26")
        assert resultado == ["Jan/2026", "Fev/2026", "Mar/2026"]
        mock_db.salvar_trimestre_ativo.assert_called_once_with(["Jan/2026", "Fev/2026", "Mar/2026"])

    def test_trimestre_vazio_sem_ret_retorna_periodo_normalizado(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = []
        mock_db.buscar_periodos_ret_para_trimestre.return_value = []
        resultado = efd.obter_periodos_trimestre("jan/26")
        assert resultado == ["Jan/2026"]

    def test_periodo_atual_pertence_ao_trimestre_ativo(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = ["Jan/2026", "Fev/2026", "Mar/2026"]
        resultado = efd.obter_periodos_trimestre("fev/26")
        assert resultado == ["Jan/2026", "Fev/2026", "Mar/2026"]

    def test_periodo_atual_nao_pertence_reconstroi(self, mock_db):
        mock_db.buscar_trimestre_ativo.return_value = ["Jan/2026", "Fev/2026", "Mar/2026"]
        mock_db.buscar_periodos_ret_para_trimestre.return_value = ["Abr/2026", "Mai/2026", "Jun/2026"]
        resultado = efd.obter_periodos_trimestre("mai/26")
        assert resultado == ["Abr/2026", "Mai/2026", "Jun/2026"]


class TestRegistrarExecucao:
    def test_registra_com_periodo(self, mock_db):
        mock_db.registrar_execucao_excel_final.return_value = 42

        resultado = efd.registrar_execucao_excel_final("ETAPA1", "jan/26")

        assert resultado is not None
        caminho, nome, periodo, execucao = resultado
        assert nome == efd.EXCEL_FIXO_NOME
        assert caminho == efd.EXCEL_FIXO_PATH
        assert periodo == "Jan/2026"
        assert execucao == 42
        mock_db.salvar_sessao_excel_final.assert_called_once_with(
            efd.EXCEL_FIXO_NOME, efd.EXCEL_FIXO_PATH
        )
        mock_db.registrar_execucao_excel_final.assert_called_once_with(
            nome_sessao=efd.EXCEL_FIXO_NOME,
            periodo="Jan/2026",
            etapa="ETAPA1",
            caminho_arquivo=efd.EXCEL_FIXO_PATH,
        )

    def test_etapa_vazia_vira_padrao(self, mock_db):
        mock_db.registrar_execucao_excel_final.return_value = 1
        efd.registrar_execucao_excel_final("", "jan/26")
        _, kwargs = mock_db.registrar_execucao_excel_final.call_args
        assert kwargs["etapa"] == "ETAPA"

    def test_sem_periodo_vira_geral(self, mock_db):
        mock_db.registrar_execucao_excel_final.return_value = 1
        _, _, periodo, _ = efd.registrar_execucao_excel_final("ETAPA1", None)
        assert periodo == "Geral"

    def test_fecha_db_mesmo_em_erro(self, mock_db):
        mock_db.registrar_execucao_excel_final.side_effect = RuntimeError("falha")
        with pytest.raises(RuntimeError):
            efd.registrar_execucao_excel_final("X", "jan/26")


class TestNovoExcelFinal:
    def test_usuario_cancela(self, mock_db):
        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=False):
            resultado = efd.novo_excel_final()
        assert resultado is False
        mock_db.zerar_sessao_excel_final.assert_not_called()

    def test_zera_e_remove_arquivo_existente(self, mock_db, tmp_path):
        arquivo_fake = tmp_path / "fake.xlsx"
        arquivo_fake.write_text("conteudo")

        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=True), \
             patch("Src.common.excel_final_destino.messagebox.showinfo"), \
             patch("Src.common.excel_final_destino.EXCEL_FIXO_PATH", str(arquivo_fake)), \
             patch("Src.common.excel_final_destino.os.remove") as mock_remove:
            resultado = efd.novo_excel_final()

        assert resultado is True
        mock_db.zerar_sessao_excel_final.assert_called_once()
        mock_remove.assert_called_once_with(str(arquivo_fake))

    def test_zera_quando_arquivo_nao_existe(self, mock_db, tmp_path):
        caminho_inexistente = str(tmp_path / "nao_existe.xlsx")

        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=True), \
             patch("Src.common.excel_final_destino.messagebox.showinfo"), \
             patch("Src.common.excel_final_destino.EXCEL_FIXO_PATH", caminho_inexistente), \
             patch("Src.common.excel_final_destino.os.remove") as mock_remove:
            resultado = efd.novo_excel_final()

        assert resultado is True
        mock_remove.assert_not_called()

    def test_oserror_no_remove_nao_propaga(self, mock_db, tmp_path):
        arquivo_fake = tmp_path / "trava.xlsx"
        arquivo_fake.write_text("x")

        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=True), \
             patch("Src.common.excel_final_destino.messagebox.showinfo"), \
             patch("Src.common.excel_final_destino.EXCEL_FIXO_PATH", str(arquivo_fake)), \
             patch("Src.common.excel_final_destino.os.remove", side_effect=OSError("locked")):
            resultado = efd.novo_excel_final()

        assert resultado is True


class TestRemoverExcelFinalAtivo:
    def test_sem_sessao_ativa(self, mock_db):
        mock_db.buscar_sessao_excel_final_ativa.return_value = None
        ok, msg = efd.remover_excel_final_ativo()
        assert ok is False
        assert "Nenhuma" in msg
        mock_db.desativar_sessao_excel_final_ativa.assert_not_called()

    def test_desvincula_sem_remover_arquivo(self, mock_db, tmp_path):
        arquivo = tmp_path / "ativo.xlsx"
        arquivo.write_text("x")
        mock_db.buscar_sessao_excel_final_ativa.return_value = {
            "nome": "Sessao1",
            "caminho_arquivo": str(arquivo),
        }
        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=False), \
             patch("Src.common.excel_final_destino.os.remove") as mock_remove:
            ok, msg = efd.remover_excel_final_ativo()
        assert ok is True
        assert "Sessao1" in msg
        mock_remove.assert_not_called()
        mock_db.desativar_sessao_excel_final_ativa.assert_called_once()
        assert arquivo.exists()

    def test_desvincula_e_remove_arquivo(self, mock_db, tmp_path):
        arquivo = tmp_path / "ativo.xlsx"
        arquivo.write_text("x")
        mock_db.buscar_sessao_excel_final_ativa.return_value = {
            "nome": "Sessao1",
            "caminho_arquivo": str(arquivo),
        }
        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=True), \
             patch("Src.common.excel_final_destino.os.remove") as mock_remove:
            ok, msg = efd.remover_excel_final_ativo()
        assert ok is True
        mock_remove.assert_called_once_with(str(arquivo))

    def test_remove_com_oserror_reporta_no_msg(self, mock_db, tmp_path):
        arquivo = tmp_path / "ativo.xlsx"
        arquivo.write_text("x")
        mock_db.buscar_sessao_excel_final_ativa.return_value = {
            "nome": "Sessao1",
            "caminho_arquivo": str(arquivo),
        }
        with patch("Src.common.excel_final_destino.messagebox.askyesno", return_value=True), \
             patch("Src.common.excel_final_destino.os.remove", side_effect=OSError("locked")):
            ok, msg = efd.remover_excel_final_ativo()
        assert ok is True
        assert "Arquivo não removido" in msg


class TestConstantes:
    def test_excel_fixo_path_em_downloads(self):
        assert efd.EXCEL_FIXO_PATH.endswith("Excel_Final_ContaGrafica.xlsx")
        assert "Downloads" in efd.EXCEL_FIXO_PATH

    def test_path_e_absoluto(self):
        assert Path(efd.EXCEL_FIXO_PATH).is_absolute()
