"""Perfis, "quem fez" na trilha e a matriz da Amanda (Src/api/perfis.py, docs/PERFIS.md).

Dois modos: PERFIS_ATIVOS=0 (padrão: todo usuário logado pode tudo, a trilha só anota quem) e
PERFIS_ATIVOS=1 (a matriz vale). Login de verdade (sem o usuário de mentira do conftest), banco
temporário e valores fictícios.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from Src.api import auth
from Src.Database.database import DatabasePMPV

SCG = {"periodo": "Fev/2026", "cgr": 1000.0, "cgf": 400.0, "ret": 30.0, "rp": -20.0}
MB = {"ano": 2027, "margem": 0.5}
PV = {"periodo": "Fev - Abr/2026", "pmpv": 1.0, "pr": 0.1}
SR_LINHAS = [{"mes": m, "vp": 1000.0, "vf": 900.0, "pr": 0.1, "selic_mensal": 1.0, "sr_anterior": 0.0}
             for m in ("Jul/2026", "Ago/2026", "Set/2026")]
SR = {"labels_meses": ["Jul/2026", "Ago/2026", "Set/2026"], "periodo_referencia": "Jul/2026", "linhas": SR_LINHAS}


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "perfis.db")
    with DatabasePMPV(db_path=caminho):
        pass
    monkeypatch.setenv("PLATAFORMA_DB", caminho)
    monkeypatch.delenv("PERFIS_ATIVOS", raising=False)
    return caminho


@pytest.fixture()
def client(banco):
    from Src.api.auth import usuario_atual
    from Src.api.main import app
    app.dependency_overrides.pop(usuario_atual, None)  # aqui o login é de verdade
    # raise_server_exceptions=False: um erro interno de um gerador de arquivo com banco vazio vira 500 (não 403).
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _usuario(client, nome: str, perfis: list[str]) -> dict:
    """Cria a conta, dá os perfis e devolve o cabeçalho de login."""
    email = f"{nome}@teste.local"
    if "administrador" not in perfis and not any("administrador" in u["perfis"] for u in auth.listar_usuarios()):
        auth.criar_usuario("raiz", "raiz@teste.local", "senha-de-teste", "senha-de-teste")  # o 1º vira administrador
    criado = auth.criar_usuario(nome, email, "senha-de-teste", "senha-de-teste")
    if perfis != criado["perfis"]:
        auth.definir_perfis(criado["id"], perfis)
    token = client.post("/api/auth/login", json={"email": email, "senha": "senha-de-teste"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _admin(client) -> dict:
    return _usuario(client, "chefe", ["administrador"])


def _trilha(banco: str, **filtros) -> list[dict]:
    with DatabasePMPV(db_path=banco) as db:
        return db.listar_alteracoes(**filtros)


# ── perfis guardados no banco ───────────────────────────────────────────────

def test_conta_antiga_vira_administrador_na_migracao(banco):
    import sqlite3
    conn = sqlite3.connect(banco)
    conn.execute("CREATE TABLE usuarios (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, "
                 "email TEXT NOT NULL UNIQUE, senha_hash TEXT NOT NULL, criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("INSERT INTO usuarios(nome, email, senha_hash) VALUES('Antiga', 'antiga@teste.local', 'x')")
    conn.commit()
    conn.close()
    assert [u["perfis"] for u in auth.listar_usuarios()] == [["administrador"]]
    # conta criada DEPOIS da migração não vira administrador
    novo = auth.criar_usuario("Nova", "nova@teste.local", "senha-de-teste", "senha-de-teste")
    assert novo["perfis"] == ["consulta"]


def test_primeiro_usuario_da_instalacao_vira_administrador_e_os_outros_consulta(banco):
    primeiro = auth.criar_usuario("Primeiro", "p@teste.local", "senha-de-teste", "senha-de-teste")
    segundo = auth.criar_usuario("Segundo", "s@teste.local", "senha-de-teste", "senha-de-teste")
    assert primeiro["perfis"] == ["administrador"] and segundo["perfis"] == ["consulta"]


def test_me_e_login_mostram_perfis(client):
    cab = _usuario(client, "ana", ["operador", "aprovador"])
    eu = client.get("/api/auth/me", headers=cab).json()
    assert eu["perfis"] == ["operador", "aprovador"] and eu["perfis_ativos"] is False


def test_perfil_vem_do_banco_a_cada_requisicao_nao_do_token(client, monkeypatch):
    monkeypatch.setenv("PERFIS_ATIVOS", "1")
    cab = _usuario(client, "ana", ["operador"])
    assert client.post("/api/scg/salvar", json=SCG, headers=cab).status_code == 200
    uid = client.get("/api/auth/me", headers=cab).json()["id"]
    auth.definir_perfis(uid, ["consulta"])  # o mesmo token, perfil novo
    assert client.post("/api/scg/salvar", json=SCG, headers=cab).status_code == 403


# ── modo DESLIGADO: nada muda, a trilha anota quem ──────────────────────────

def test_desligado_consulta_pode_tudo_e_motivo_nao_e_exigido(client):
    _admin(client)
    cab = _usuario(client, "visitante", ["consulta"])
    assert client.post("/api/scg/salvar", json=SCG, headers=cab).status_code == 200
    assert client.post("/api/pmpv/margem-regulatoria", json=MB, headers=cab).status_code == 200  # sem motivo
    assert client.post("/api/scg/salvar", json={**SCG, "escolha": "soma"}, headers=cab).status_code == 200


def test_desligado_trilha_registra_quem_fez(client, banco):
    cab = _usuario(client, "ana", ["operador"])
    client.post("/api/scg/salvar", json=SCG, headers=cab)
    linha = _trilha(banco, tabela="consolidacao")[0]
    assert (linha["usuario_nome"], linha["usuario_email"], linha["perfil"], linha["acao"]) == \
        ("ana", "ana@teste.local", "operador", "salvar_modulo")
    assert linha["usuario_id"] and linha["motivo"] is None
    assert client.get("/api/trilha", headers=cab).json()[0]["usuario_nome"] == "ana"


def test_desligado_usuarios_continua_so_para_administrador(client):
    _admin(client)
    cab = _usuario(client, "visitante", ["consulta"])
    assert client.get("/api/usuarios", headers=cab).status_code == 403


def test_sem_login_continua_401(client):
    assert client.get("/api/scg/historico").status_code == 401
    assert client.get("/api/health").status_code == 200


# ── trilha dos apagamentos (DELETE /scg e DELETE /periodos) ─────────────────

def test_delete_scg_entra_na_trilha_com_quem_apagou(client, banco):
    cab = _usuario(client, "ana", ["operador"])
    client.post("/api/scg/salvar", json=SCG, headers=cab)
    r = client.delete("/api/scg", params={"periodo": "Fev/2026", "motivo": "mês lançado por engano"}, headers=cab)
    assert r.status_code == 204
    apagados = [l for l in _trilha(banco, tabela="consolidacao") if l["origem"] == "apagar"]
    por_campo = {l["campo"]: l for l in apagados}
    assert por_campo["scg"]["valor_antigo"] == pytest.approx(610.0) and por_campo["scg"]["valor_novo"] is None
    assert por_campo["scg"]["acao"] == "apagar_scg" and por_campo["scg"]["usuario_nome"] == "ana"
    assert por_campo["scg"]["motivo"] == "mês lançado por engano"


def test_delete_periodos_entra_na_trilha(client, banco):
    cab = _usuario(client, "ana", ["administrador"])
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pmpv_mensal("Teste2", 1.2345)
        db.salvar_pr("Teste2", 1.0, 2.0, 3.0, 0.5)
    assert client.delete("/api/periodos/Teste2", params={"aplicar": True}, headers=cab).status_code == 200
    apagados = [l for l in _trilha(banco) if l["origem"] == "apagar"]
    assert {(l["tabela"], l["campo"]) for l in apagados} >= {("pmpv_mensal", "pmpv"), ("pr_resultados", "pr")}
    assert all(l["valor_novo"] is None and l["usuario_nome"] == "ana" and l["acao"] == "apagar_periodo"
               for l in apagados)


def test_simulacao_do_delete_periodos_nao_anota_nada(client, banco):
    cab = _usuario(client, "ana", ["administrador"])
    with DatabasePMPV(db_path=banco) as db:
        db.salvar_pmpv_mensal("Teste2", 1.2345)
    antes = len(_trilha(banco))
    client.delete("/api/periodos/Teste2", headers=cab)  # aplicar=false
    assert len(_trilha(banco)) == antes


# ── modo LIGADO: a matriz vale ──────────────────────────────────────────────

@pytest.fixture()
def ligado(monkeypatch):
    monkeypatch.setenv("PERFIS_ATIVOS", "1")


PERFIS = ("consulta", "operador", "aprovador", "analista", "administrador")

# (descrição, método, rota, corpo/params, perfis que PODEM)
MATRIZ = [
    ("ver", "GET", "/api/scg/historico", {}, PERFIS),
    ("gravar módulo", "POST", "/api/scg/salvar", {"json": SCG}, ("operador", "analista", "administrador")),
    ("calcular (só prévia)", "POST", "/api/sr/calcular", {"json": {"vp": 1.0, "vf": 1.0, "pr": 0.1}}, PERFIS),
    ("aprovar PV", "POST", "/api/pv/salvar", {"json": PV}, ("aprovador", "analista")),
    ("aprovar cascata", "POST", "/api/cascata/aplicar", {"json": {"periodos": ["Jul/2026"]}}, ("aprovador", "analista")),
    ("aprovar SR", "POST", "/api/sr/trimestre/salvar", {"json": SR}, ("aprovador", "analista")),
    ("escolher MB", "POST", "/api/pmpv/margem-regulatoria", {"json": {**MB, "motivo": "NT"}}, ("analista",)),
    ("apagar PR", "DELETE", "/api/pr", {"params": {"periodo": "Fev - Abr/2026"}}, ("administrador",)),
    ("apagar SCG", "DELETE", "/api/scg", {"params": {"periodo": "Fev/2026"}}, ("administrador",)),
    ("apagar período", "DELETE", "/api/periodos/Teste2", {}, ("administrador",)),
    ("reparar SCG", "POST", "/api/scg/reparar-historico", {}, ("administrador",)),
    ("relatório oficial", "POST", "/api/nota-tecnica/gerar", {"params": {"periodo": "Jul/2026"}}, ("analista", "administrador")),
    ("usuários", "GET", "/api/usuarios", {}, ("administrador",)),
]


@pytest.mark.parametrize("perfil", PERFIS)
@pytest.mark.parametrize("nome,metodo,rota,args,quem_pode", MATRIZ, ids=[m[0] for m in MATRIZ])
def test_ligado_matriz_da_amanda(client, ligado, perfil, nome, metodo, rota, args, quem_pode):
    _admin(client)  # garante que existe um administrador
    cab = _usuario(client, f"u_{perfil}", [perfil])
    r = client.request(metodo, rota, headers=cab, **args)
    if perfil in quem_pode:
        assert r.status_code != 403, f"{perfil} deveria poder: {nome} ({r.text})"
    else:
        assert r.status_code == 403, f"{perfil} não deveria poder: {nome}"
        assert "perfil" in r.json()["detail"] and "Quem pode" in r.json()["detail"]


def test_ligado_recusa_nao_grava_nada(client, banco, ligado):
    _admin(client)
    cab = _usuario(client, "visitante", ["consulta"])
    assert client.post("/api/scg/salvar", json=SCG, headers=cab).status_code == 403
    assert _trilha(banco) == []


def test_ligado_usuario_sem_perfil_nao_entra_em_nada(client, ligado):
    _admin(client)
    cab = _usuario(client, "sem_acesso", [])
    assert client.get("/api/scg/historico", headers=cab).status_code == 403
    assert client.get("/api/auth/me", headers=cab).status_code == 200  # /auth não depende de perfil


def test_ligado_pessoa_com_dois_perfis_soma_as_permissoes(client, ligado):
    _admin(client)
    cab = _usuario(client, "dupla", ["operador", "aprovador"])
    assert client.post("/api/scg/salvar", json=SCG, headers=cab).status_code == 200
    assert client.post("/api/pv/salvar", json=PV, headers=cab).status_code == 200


def test_ligado_escolha_do_scg_exige_analista_e_motivo(client, banco, ligado):
    _admin(client)
    oper = _usuario(client, "oper", ["operador"])
    ana = _usuario(client, "ana", ["analista"])
    com_escolha = {**SCG, "escolha": "soma"}
    assert client.post("/api/scg/salvar", json=com_escolha, headers=oper).status_code == 403
    sem_motivo = client.post("/api/scg/salvar", json=com_escolha, headers=ana)
    assert sem_motivo.status_code == 422 and "motivo" in sem_motivo.json()["detail"]
    assert _trilha(banco) == []  # a recusa não gravou nada
    ok = client.post("/api/scg/salvar", json={**com_escolha, "motivo": "soma bate com a planilha"}, headers=ana)
    assert ok.status_code == 200
    linha = _trilha(banco, tabela="consolidacao")[0]
    assert (linha["acao"], linha["perfil"], linha["usuario_nome"], linha["motivo"]) == \
        ("escolher", "analista", "ana", "soma bate com a planilha")


def test_ligado_mb_sem_motivo_da_422(client, ligado):
    _admin(client)
    ana = _usuario(client, "ana", ["analista"])
    r = client.post("/api/pmpv/margem-regulatoria", json=MB, headers=ana)
    assert r.status_code == 422 and "motivo" in r.json()["detail"]
    assert client.post("/api/pmpv/margem-regulatoria", json={**MB, "motivo": "  "}, headers=ana).status_code == 422
    assert client.post("/api/pmpv/margem-regulatoria", json={**MB, "motivo": "Resolução 2027"}, headers=ana).status_code == 200


def test_ligado_sr_anterior_diferente_do_gravado_e_escolha(client, ligado):
    _admin(client)
    aprov = _usuario(client, "aprov", ["aprovador"])
    ana = _usuario(client, "ana", ["analista"])
    mudou = {**SR, "linhas": [{**SR_LINHAS[0], "sr_anterior": 500.0}, *SR_LINHAS[1:]]}
    assert client.post("/api/sr/trimestre/salvar", json=mudou, headers=aprov).status_code == 403
    sem_motivo = client.post("/api/sr/trimestre/salvar", json=mudou, headers=ana)
    assert sem_motivo.status_code == 422 and "motivo" in sem_motivo.json()["detail"]
    manual = client.post("/api/sr/trimestre/salvar", json={**SR, "selic_manual": True}, headers=aprov)
    assert manual.status_code == 403


def test_ligado_aprovar_sr_sem_escolha_nao_pede_motivo(client, ligado):
    _admin(client)
    aprov = _usuario(client, "aprov", ["aprovador"])
    r = client.post("/api/sr/trimestre/salvar", json=SR, headers=aprov)
    assert r.status_code == 200, r.text


def test_ligado_trilha_da_aprovacao_leva_perfil_e_acao(client, banco, ligado):
    _admin(client)
    aprov = _usuario(client, "aprov", ["aprovador"])
    client.post("/api/pv/salvar", json=PV, headers=aprov)
    linhas = _trilha(banco, tabela="pv_resultados")
    assert linhas and all(l["perfil"] == "aprovador" and l["acao"] == "aprovar_pv"
                          and l["usuario_nome"] == "aprov" for l in linhas)


# ── usuários e perfis ───────────────────────────────────────────────────────

def test_administrador_lista_e_troca_perfis(client):
    cab = _admin(client)
    outro = auth.criar_usuario("outro", "outro@teste.local", "senha-de-teste", "senha-de-teste")
    assert {u["email"] for u in client.get("/api/usuarios", headers=cab).json()} >= {"outro@teste.local"}
    r = client.put(f"/api/usuarios/{outro['id']}/perfis", json={"perfis": ["aprovador", "operador"]}, headers=cab)
    assert r.status_code == 200 and r.json()["perfis"] == ["operador", "aprovador"]


def test_nao_deixa_tirar_o_ultimo_administrador(client):
    cab = _admin(client)
    meu_id = client.get("/api/auth/me", headers=cab).json()["id"]
    r = client.put(f"/api/usuarios/{meu_id}/perfis", json={"perfis": ["consulta"]}, headers=cab)
    assert r.status_code == 422 and "último administrador" in r.json()["detail"]


def test_perfil_inexistente_e_usuario_inexistente(client):
    cab = _admin(client)
    meu_id = client.get("/api/auth/me", headers=cab).json()["id"]
    assert client.put(f"/api/usuarios/{meu_id}/perfis", json={"perfis": ["rei"]}, headers=cab).status_code == 422
    assert client.put("/api/usuarios/9999/perfis", json={"perfis": ["consulta"]}, headers=cab).status_code == 404


def test_cadastro_pela_api_nasce_consulta_depois_do_primeiro(client):
    corpo = {"senha": "senha-de-teste", "confirmar_senha": "senha-de-teste"}
    primeiro = client.post("/api/auth/cadastro", json={"nome": "Primeiro", "email": "a@teste.local", **corpo}).json()
    segundo = client.post("/api/auth/cadastro", json={"nome": "Segundo", "email": "b@teste.local", **corpo}).json()
    assert primeiro["usuario"]["perfis"] == ["administrador"] and segundo["usuario"]["perfis"] == ["consulta"]


# ── a tabela cobre todas as rotas ───────────────────────────────────────────

def test_toda_rota_que_muda_algo_esta_na_tabela_de_regras():
    from Src.api.main import app
    from Src.api.perfis import REGRAS

    # O OpenAPI lista cada rota com o método (a lista app.routes varia conforme a versão do FastAPI).
    rotas = {(metodo.upper(), re.sub(r":\w+}", "}", caminho)) for caminho, ops in app.openapi()["paths"].items()
             if caminho.startswith("/api/") and not caminho.startswith("/api/auth/") and caminho != "/api/health"
             for metodo in ops}
    regras = {(m, re.sub(r":\w+}", "}", c)) for m, c in REGRAS}  # o OpenAPI não mostra o ":path"
    sem_regra = sorted(k for k in rotas if k[0] != "GET" and k not in regras)
    assert not sem_regra, f"Rotas sem perfil definido em Src/api/perfis.py: {sem_regra}"
    fantasmas = sorted(k for k in regras if k not in rotas)
    assert not fantasmas, f"Regras para rotas que não existem (erro de digitação?): {fantasmas}"
