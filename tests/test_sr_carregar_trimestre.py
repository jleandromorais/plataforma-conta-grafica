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
    repo.buscar_sr.return_value = None   # o PR do próprio SR não conta mais como fonte
    repo.buscar_pr.side_effect = lambda chave: {"pr": pr[chave]} if chave in pr else None  # PR da tela PR, por chave
    return repo


def _carregar(repo):
    cons = MagicMock()
    cons.buscar_consolidacao.return_value = {"scg": -461.0}
    with patch.object(sr_use_cases, "ServicosConsolidacao", return_value=cons):
        return {l["mes"]: l for l in SRUseCases(repo).carregar_vp_vf_pr(0, ["Jan/2026", "Fev/2026", "Mar/2026"])}


def test_origem_do_pr_e_do_vp():
    # Só o PR "Nov - Jan/2026" está salvo: vale para Jan/26 (trimestre da tarifa do próprio mês).
    linhas = _carregar(_repo(vp={"Jan/2026": 1000.0, "Mar/2026": 10000.0}, pr={"Nov - Jan/2026": -0.0210}))

    assert linhas["Jan/2026"]["pr"] == -0.0210
    assert linhas["Jan/2026"]["pr_origem"] == "salvo"
    assert linhas["Jan/2026"]["pr_chave"] == "Nov - Jan/2026"
    # Fev/26 ("Fev - Abr/2026") não tem PR salvo e não tem VP: ausente.
    assert linhas["Fev/2026"]["vp"] == 0.0
    assert linhas["Fev/2026"]["pr_origem"] == "ausente"
    # Mar/26 ("Fev - Abr/2026") não tem PR salvo, mas tem VP: estimado por (SCG + SR) / VP.
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
    """PR do próprio mês: o PR de Ago–Out/2026 vale para Ago/Set; Jul (Mai–Jul) continua sem."""
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


def test_pr_do_proprio_sr_nao_e_mais_fonte():
    """Um PR velho gravado no próprio SR não vale: sem PR na tela PR (e sem VP) fica ausente."""
    repo = _repo(vp={}, pr={})
    repo.buscar_sr.return_value = {"pr": -0.5, "sr": 0.0}
    linhas = _carregar(repo)
    assert linhas["Jan/2026"]["pr"] == 0.0
    assert linhas["Jan/2026"]["pr_origem"] == "ausente"


@pytest.mark.parametrize("mes, chave", [
    # Aba SR da NT_05/2026 e PR-PV: Out/25 usa PR Ago–Out/25 (0,0116); Nov e Dez/25 usam Nov/25–Jan/26 (−0,0210);
    # Jan/26 usa Nov–Jan (−0,0210); Fev e Mar/26 usam Fev–Abr/26 (−0,0321).
    ("Out/2025", "Ago - Out/2025"), ("Nov/2025", "Nov - Jan/2026"), ("Dez/2025", "Nov - Jan/2026"),
    ("Jan/2026", "Nov - Jan/2026"), ("Fev/2026", "Fev - Abr/2026"), ("Mar/2026", "Fev - Abr/2026"),
    ("Out/2026", "Ago - Out/2026"), ("Nov/2026", "Nov - Jan/2027"),
])
def test_chave_do_pr_usada_no_sr_e_a_do_proprio_mes(mes, chave):
    repo = _repo(vp={mes: 1000.0}, pr={chave: -0.01})
    cons = MagicMock()
    cons.buscar_consolidacao.return_value = None
    with patch.object(sr_use_cases, "ServicosConsolidacao", return_value=cons):
        linha = SRUseCases(repo).carregar_vp_vf_pr(0, [mes])[0]
    assert (linha["pr_chave"], linha["pr_origem"]) == (chave, "salvo")
