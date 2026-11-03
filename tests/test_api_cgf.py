"""Testes da API web do CGF (Src/api/routers/cgf.py).

A tela desktop (tela_cgf.py) usa ServicosCGF.processar_arquivos; os testes
conferem que a API dá o mesmo resultado com as mesmas planilhas, e que salvar
exige PMPV (o desktop gravava m³ no campo do CGF em R$ quando faltava).
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from Src.Database.database import DatabasePMPV
from Src.Services.servicos_cgf import ServicosCGF

RAIZ = Path(__file__).resolve().parents[1]
REAIS = [RAIZ / "NF Faturadas e complementares 01.26.xlsx",
         RAIZ / "NF Canceladas e denegadas 01.26.xlsx",
         RAIZ / "NF Devolvidas 01.26.xlsx"]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    banco = tmp_path / "cgf_teste.db"
    with DatabasePMPV(db_path=str(banco)):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    from Src.api.main import app
    with TestClient(app) as c:
        yield c


def _xlsx(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def _arquivos_sinteticos():
    fat = pd.DataFrame({"Produto": ["Gás", "Gás", "Consumo Proprio"], "Volume Faturado": ["1.000,50", "2000", "300"]})
    canc = pd.DataFrame({"Volume Canc/Deneg": [40.0]})
    dev = pd.DataFrame({"Volume Devolução": [100.25]})
    xl = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return [
        ("arquivos", ("NF Faturadas 03.26.xlsx", _xlsx(fat), xl)),
        ("arquivos", ("NF Canceladas 03.26.xlsx", _xlsx(canc), xl)),
        ("arquivos", ("NF Devolvidas 03.26.xlsx", _xlsx(dev), xl)),
    ]


def test_processar_calcula_volumes_e_detecta_periodo(client):
    resp = client.post("/api/cgf/processar", files=_arquivos_sinteticos())
    assert resp.status_code == 200
    r = resp.json()
    assert r["volume_faturado"] == pytest.approx(3000.5)      # sem o consumo próprio
    assert r["volume_consumo_proprio"] == pytest.approx(300.0)
    assert r["volume_canceladas"] == pytest.approx(40.0)
    assert r["volume_devolucoes"] == pytest.approx(100.25)
    assert r["volume_final"] == pytest.approx(3000.5 - 100.25)  # canceladas não entram
    assert r["periodo_detectado"] == "Mar/2026"
    assert r["arquivos_ignorados"] == []


def test_processar_avisa_arquivo_sem_tipo_no_nome(client):
    xl = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    arquivos = _arquivos_sinteticos() + [("arquivos", ("planilha qualquer.xlsx", _xlsx(pd.DataFrame({"a": [1]})), xl))]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    assert r["arquivos_ignorados"] == ["planilha qualquer.xlsx"]


XL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _problemas(r: dict, codigo: str) -> list[dict]:
    return [p for p in r["problemas"] if p["codigo"] == codigo]


def test_processar_sem_problemas_quando_tudo_certo(client):
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    assert [p for p in r["problemas"] if p["gravidade"] != "info"] == []


def test_reconhece_abreviacoes_canc_deneg(client):
    """AC1: o caso real 'NF canc.rejeitadas.deneg.xlsx' é a planilha de canceladas."""
    canc = pd.DataFrame({"Volume Canc/Deneg": [40.0]})
    arquivos = [a for a in _arquivos_sinteticos() if "Canceladas" not in a[1][0]]
    arquivos.append(("arquivos", ("NF canc.rejeitadas.deneg.xlsx", _xlsx(canc), XL)))
    r = client.post("/api/cgf/processar", files=arquivos).json()
    assert r["arquivos_ignorados"] == []
    assert r["volume_canceladas"] == pytest.approx(40.0)


def test_tipo_nao_reconhecido_e_erro_com_palavras_aceitas(client):
    """AC2."""
    arquivos = _arquivos_sinteticos() + [("arquivos", ("NF qualquer.xlsx", _xlsx(pd.DataFrame({"a": [1]})), XL))]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "tipo_nao_reconhecido")
    assert p["gravidade"] == "erro"
    assert p["arquivo"] == "NF qualquer.xlsx"
    assert "faturada" in p["mensagem"] and "devolução" in p["mensagem"]


def test_coluna_ausente_lista_colunas_encontradas(client):
    """AC3."""
    fat = pd.DataFrame({"Data": ["01/03"], "Qtd": [10]})
    arquivos = [a for a in _arquivos_sinteticos() if "Faturadas" not in a[1][0]]
    arquivos.append(("arquivos", ("NF Faturadas 03.26.xlsx", _xlsx(fat), XL)))
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "coluna_ausente")
    assert p["gravidade"] == "erro"
    assert "Volume Faturado" in p["mensagem"]
    assert "Data" in p["tecnico"] and "Qtd" in p["tecnico"]


def test_planilha_ilegivel_sem_caminho_do_servidor(client):
    """AC4."""
    arquivos = _arquivos_sinteticos() + [("arquivos", ("NF Devolvidas extra.xlsx", b"isto nao e um xlsx", XL))]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "planilha_ilegivel")
    assert p["gravidade"] == "erro"
    assert p["arquivo"] == "NF Devolvidas extra.xlsx"
    textos = " ".join(f"{q['mensagem']} {q.get('tecnico') or ''}" for q in r["problemas"])
    for proibido in ("/tmp", "\\", "cgf_", "Temp"):
        assert proibido not in textos


def test_so_faturadas_avisa_tipos_ausentes(client):
    """AC5."""
    arquivos = [a for a in _arquivos_sinteticos() if "Faturadas" in a[1][0]]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    ausentes = _problemas(r, "tipo_ausente")
    assert len(ausentes) == 2
    assert all(p["gravidade"] == "aviso" for p in ausentes)
    assert not [p for p in r["problemas"] if p["gravidade"] == "erro"]


def test_sem_faturadas_e_erro(client):
    arquivos = [a for a in _arquivos_sinteticos() if "Faturadas" not in a[1][0]]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "sem_faturadas")
    assert p["gravidade"] == "erro"


def test_planilha_vazia_e_aviso(client):
    arquivos = _arquivos_sinteticos() + [("arquivos", ("NF Devolvidas 2.xlsx", _xlsx(pd.DataFrame({"Volume Devolução": []})), XL))]
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "planilha_vazia")
    assert p["gravidade"] == "aviso"


def test_coluna_por_apelido_e_info(client):
    canc = pd.DataFrame({"Volume Canceladas": [40.0]})
    arquivos = [a for a in _arquivos_sinteticos() if "Canceladas" not in a[1][0]]
    arquivos.append(("arquivos", ("NF Canceladas 03.26.xlsx", _xlsx(canc), XL)))
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "coluna_por_apelido")
    assert p["gravidade"] == "info"
    assert "Volume Canceladas" in p["mensagem"]


def test_consumo_nao_encontrado_e_info(client):
    fat = pd.DataFrame({"Produto": ["Gás"], "Volume Faturado": [100.0]})
    arquivos = [a for a in _arquivos_sinteticos() if "Faturadas" not in a[1][0]]
    arquivos.append(("arquivos", ("NF Faturadas 03.26.xlsx", _xlsx(fat), XL)))
    r = client.post("/api/cgf/processar", files=arquivos).json()
    [p] = _problemas(r, "consumo_nao_encontrado")
    assert p["gravidade"] == "info"


def test_processar_rejeita_arquivo_que_nao_e_planilha(client):
    resp = client.post("/api/cgf/processar", files=[("arquivos", ("NF Faturadas.pdf", b"%PDF", "application/pdf"))])
    assert resp.status_code == 422


@pytest.mark.skipif(not all(p.exists() for p in REAIS), reason="planilhas de NF de exemplo ausentes")
def test_processar_planilhas_reais_igual_ao_desktop(client):
    esperado = ServicosCGF().processar_arquivos(
        [str(p) for p in REAIS], "Volume Faturado", "Produto", "consumo proprio", "Volume Canc/Deneg", "Volume Devolução",
    )
    handles = [p.open("rb") for p in REAIS]
    try:
        r = client.post("/api/cgf/processar", files=[("arquivos", (p.name, h, "application/octet-stream")) for p, h in zip(REAIS, handles)]).json()
    finally:
        for h in handles:
            h.close()
    for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final"):
        assert r[k] == pytest.approx(esperado[k])
    assert r["periodo_detectado"] == "Jan/2026"


def test_salvar_exige_pmpv(client):
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    payload = {k: r[k] for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final")}
    resp = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mar/2026", "pmpv": 0})
    assert resp.status_code == 422
    assert "PMPV" in resp.json()["detail"]
    assert client.get("/api/rpv", params={"periodo": "Mar/2026"}).status_code == 404  # nada gravado


def test_salvar_grava_cgf_em_reais_e_resumo(client):
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    payload = {k: r[k] for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final")}
    resp = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mar/2026", "pmpv": 2.5})
    assert resp.status_code == 200
    assert resp.json()["cgf_rs"] == pytest.approx(r["volume_final"] * 2.5)

    assert client.get("/api/rpv", params={"periodo": "Mar/2026"}).json()["cgf"] == pytest.approx(r["volume_final"] * 2.5)
    hist = {h["periodo"]: h for h in client.get("/api/cgf/historico").json()}
    assert hist["Mar/2026"]["volume_final"] == pytest.approx(r["volume_final"])
    assert hist["Mar/2026"]["cgf_rs"] == pytest.approx(r["volume_final"] * 2.5)


def test_cgf_usa_pmpv_com_4_casas_como_o_desktop(client):
    """O desktop carrega o PMPV como f"{pmpv:.4f}" antes de multiplicar."""
    r = client.post("/api/cgf/processar", files=_arquivos_sinteticos()).json()
    payload = {k: r[k] for k in ("volume_faturado", "volume_canceladas", "volume_devolucoes", "volume_consumo_proprio", "volume_final")}
    pmpv_banco = 2.282982647346896
    cgf = client.post("/api/cgf/salvar", json={**payload, "periodo": "Mai/2026", "pmpv": pmpv_banco}).json()["cgf_rs"]
    assert cgf == pytest.approx(r["volume_final"] * float(f"{pmpv_banco:.4f}"))


# CGF da planilha oficial (rev9 do Alexandre, aba BASE): volume final com 2 casas
# × PMPV com 4 casas. Jun, Ago e Set ficavam 1 centavo fora com o volume bruto.
PLANILHA_REV9 = [
    ("Jan/2026", 41805735.0, 2.1154, 88435851.82),
    ("Fev/2026", 39940613.0, 1.9988, 79833297.26),
    ("Mar/2026", 44979282.33039879, 1.9988, 89904589.52),
    ("Abr/2026", 42078110.63, 1.9988, 84105727.53),
    ("Mai/2026", 45564265.79, 2.283, 104023218.80),
    ("Jun/2026", 43730399.2768, 2.283, 99836501.56),   # volume bruto, com 4 casas
    ("Jul/2026", 43909249.06, 2.283, 100244815.60),
    ("Ago/2026", 43947586.6, 2.3597, 103703120.10),
    ("Set/2026", 39419521.7549, 2.3597, 93018245.47),  # volume bruto, com 4 casas
]


@pytest.mark.parametrize("periodo,volume,pmpv,esperado", PLANILHA_REV9)
def test_calcular_cgf_rs_bate_com_a_planilha(periodo, volume, pmpv, esperado):
    r = ServicosCGF().calcular_cgf_rs(periodo, volume, pmpv)
    assert round(r["cgf_rs"], 2) == esperado
    assert r["volume_final"] == round(volume, 2)


def test_salvar_arredonda_volume_como_a_planilha(client):
    payload = {"volume_faturado": 43731032.0, "volume_canceladas": 0.0, "volume_devolucoes": 632.7232,
               "volume_consumo_proprio": 0.0, "volume_final": 43730399.2768}
    r = client.post("/api/cgf/salvar", json={**payload, "periodo": "Jun/2026", "pmpv": 2.283}).json()
    assert round(r["cgf_rs"], 2) == 99836501.56
    resumo = next(h for h in client.get("/api/cgf/historico").json() if h["periodo"] == "Jun/2026")
    assert resumo["volume_final"] == 43730399.28
