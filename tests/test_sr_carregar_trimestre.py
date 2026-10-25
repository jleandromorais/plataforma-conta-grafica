"""Carregamento de VP/VF/PR do SR trimestral: a tela precisa saber se o PR
veio salvo ou foi estimado ((SCG + SR) / VP), e quando não há VP/PR."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from Src.application.use_cases import sr_use_cases
from Src.application.use_cases.sr_use_cases import SRUseCases


def _repo(vp: dict, pr: dict) -> MagicMock:
    repo = MagicMock()
    repo.buscar_vp_periodo.side_effect = lambda p: vp.get(p)
    repo.listar_sessoes_id_nome.return_value = []
    repo.buscar_cgf_resumo.return_value = {"volume_final": 100.0}
    repo.buscar_sr.side_effect = lambda p: {"pr": pr[p], "sr": 0.0} if p in pr else None
    repo.buscar_pr.return_value = None   # sem PR salvo na tela PR
    return repo


def _carregar(repo):
    cons = MagicMock()
    cons.buscar_consolidacao.return_value = {"scg": -461.0}
    with patch.object(sr_use_cases, "ServicosConsolidacao", return_value=cons):
        return {l["mes"]: l for l in SRUseCases(repo).carregar_vp_vf_pr(0, ["Jan/2026", "Fev/2026", "Mar/2026"])}


def test_origem_do_pr_e_do_vp():
    linhas = _carregar(_repo(vp={"Fev/2026": 1000.0, "Mar/2026": 10000.0}, pr={"Fev/2026": -0.0321}))

    assert linhas["Jan/2026"]["vp"] == 0.0
    assert linhas["Jan/2026"]["pr_origem"] == "ausente"
    assert linhas["Fev/2026"]["pr"] == -0.0321
    assert linhas["Fev/2026"]["pr_origem"] == "salvo"
    assert linhas["Mar/2026"]["pr"] == -0.0461
    assert linhas["Mar/2026"]["pr_origem"] == "estimado"


@pytest.fixture()
def client():
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def test_api_aceita_sem_sessao_e_devolve_origem(client):
    with patch.object(SRUseCases, "carregar_vp_vf_pr",
                      return_value=[{"mes": "Jan/2026", "vp": 0.0, "vf": 1.0, "pr": 0.0, "pr_origem": "ausente"}]):
        r = client.post("/api/sr/trimestre/carregar", json={"labels_meses": ["Jan/2026"]})
    assert r.status_code == 200, r.text
    assert r.json()[0]["pr_origem"] == "ausente"


def test_pr_salvo_na_tela_pr_alimenta_os_meses_do_trimestre():
    """O PR de Ago–Out/2026 salvo na tela PR vale para Ago/Set; Jul (trimestre Mai–Jul) continua sem."""
    repo = _repo(vp={"Jul/2026": 1000.0, "Ago/2026": 1000.0, "Set/2026": 1000.0}, pr={})
    repo.buscar_pr.side_effect = lambda chave: {"pr": 0.0135} if chave == "Ago - Out/2026" else None
    with patch("Src.application.use_cases.sr_use_cases.ServicosConsolidacao") as cons:
        cons.return_value.buscar_consolidacao.return_value = None
        linhas = {l["mes"]: l for l in SRUseCases(repo).carregar_vp_vf_pr(0, ["Jul/2026", "Ago/2026", "Set/2026"])}
    assert (linhas["Ago/2026"]["pr"], linhas["Ago/2026"]["pr_origem"]) == (0.0135, "salvo")
    assert (linhas["Set/2026"]["pr"], linhas["Set/2026"]["pr_origem"]) == (0.0135, "salvo")
    assert linhas["Jul/2026"]["pr_origem"] == "ausente"


@pytest.mark.parametrize("mes, chave", [
    ("Jul/2026", "Mai - Jul/2026"), ("Ago/2026", "Ago - Out/2026"), ("Out/2026", "Ago - Out/2026"),
    ("Nov/2026", "Nov - Jan/2027"), ("Dez/2026", "Nov - Jan/2027"), ("Jan/2026", "Nov - Jan/2026"),
    ("Fev/2026", "Fev - Abr/2026"), ("Abr/2026", "Fev - Abr/2026"), ("Mai/2026", "Mai - Jul/2026"),
])
def test_chave_do_pr_do_trimestre(mes, chave):
    from Src.application.use_cases.sr_use_cases import chave_pr_do_mes
    assert chave_pr_do_mes(mes) == chave
