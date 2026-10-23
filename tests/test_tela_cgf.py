"""Gravação do CGF pela tela desktop.

A tela gravava sozinha logo após processar (no período que estivesse no
campo, sem confirmação) e, sem PMPV, gravava o VOLUME em m³ como se fosse
CGF em R$. Isso deixou CGF de um mês gravado no mês seguinte (Jun/26 com o
CGF de Mai/26). Agora só grava com confirmação e sempre via
`ServicosCGF.salvar_com_pmpv`, que exige PMPV > 0.
"""
from unittest.mock import MagicMock, patch

import pytest

from Src.Views import tela_cgf
from Src.Views.tela_cgf import TelaCGF

RESUMO = {"volume_faturado": 100.0, "volume_canceladas": 0.0, "volume_devolucoes": 0.0,
          "volume_consumo_proprio": 0.0, "volume_final": 100.0, "logs": []}


def _tela(pmpv: str = "2.2830", periodo: str = "Mai/2026") -> TelaCGF:
    tela = TelaCGF.__new__(TelaCGF)  # sem Tk: só o estado que a gravação usa
    tela.servicos = MagicMock()
    tela.servicos.salvar_com_pmpv.return_value = {"cgf_rs": 228.30, "rpv": 1.0}
    tela.servicos.processar_arquivos.return_value = dict(RESUMO)
    tela._ultimo_resultado_cgf = dict(RESUMO)
    tela.volume_final_cgf = 100.0
    tela.pmpv_manual = MagicMock(get=MagicMock(return_value=pmpv))
    tela.cgf_rs = 100.0 * float(pmpv or 0)
    tela._periodo_widget = MagicMock(get=MagicMock(return_value=periodo))
    return tela


@pytest.fixture
def mb():
    with patch.object(tela_cgf, "messagebox") as m:
        m.askyesno.return_value = True
        yield m


@pytest.fixture(autouse=True)
def periodo_widget():
    with patch.object(TelaCGF, "entry_periodo", property(lambda self: self._periodo_widget)):
        yield


def test_salvar_usa_salvar_com_pmpv_no_periodo_confirmado(mb):
    tela = _tela()
    tela._salvar_cgf_scg()
    tela.servicos.salvar_com_pmpv.assert_called_once_with("Mai/2026", RESUMO, 2.283)
    tela.servicos.salvar_cgf.assert_not_called()
    assert "Mai/2026" in mb.askyesno.call_args.args[1]


def test_salvar_sem_pmpv_nao_grava_volume(mb):
    tela = _tela(pmpv="")
    tela._salvar_cgf_scg()
    tela.servicos.salvar_com_pmpv.assert_not_called()
    tela.servicos.salvar_cgf.assert_not_called()
    mb.showwarning.assert_called_once()


def test_salvar_cancelado_nao_grava(mb):
    mb.askyesno.return_value = False
    tela = _tela()
    tela._salvar_cgf_scg()
    tela.servicos.salvar_com_pmpv.assert_not_called()


def test_excel_final_sem_pmpv_nao_grava_volume(mb):
    tela = _tela(pmpv="")
    tela._adicionar_excel_final()
    tela.servicos.salvar_com_pmpv.assert_not_called()
    tela.servicos.salvar_cgf.assert_not_called()


def test_processar_nao_grava_sozinho(mb):
    tela = _tela()
    tela.selected_files = ["NF Faturadas 05.26.xlsx"]
    for campo in ("col_fat_volume", "col_fat_consumo", "val_fat_consumo",
                  "col_canc_volume", "col_dev_volume"):
        setattr(tela, campo, MagicMock(get=MagicMock(return_value="Volume")))
    for widget in ("log_text", "result_label", "lbl_volume_card", "lbl_detalhes",
                   "lbl_cgf_rs", "tabview"):
        setattr(tela, widget, MagicMock())
    with patch.object(TelaCGF, "_carregar_pmpv_banco"):
        tela.calculate_total()
    tela.servicos.salvar_com_pmpv.assert_not_called()
    tela.servicos.salvar_cgf.assert_not_called()
