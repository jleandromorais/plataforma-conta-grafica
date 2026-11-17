"""Testes do backup do banco (scripts/backup_banco.py). Só bancos temporários."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_CAMINHO = Path(__file__).resolve().parents[1] / "scripts" / "backup_banco.py"
_spec = importlib.util.spec_from_file_location("backup_banco", _CAMINHO)
bk = importlib.util.module_from_spec(_spec)
sys.modules["backup_banco"] = bk
_spec.loader.exec_module(bk)


@pytest.fixture
def banco(tmp_path):
    caminho = tmp_path / "pmpv_data.db"
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE nota (id INTEGER PRIMARY KEY, valor REAL)")
    con.execute("CREATE TABLE trilha (id INTEGER PRIMARY KEY, texto TEXT)")
    con.executemany("INSERT INTO nota (valor) VALUES (?)", [(1000.0,), (2500.5,)])
    con.commit()
    con.close()
    return caminho


def _linhas(caminho):
    con = sqlite3.connect(caminho)
    try:
        return con.execute("SELECT valor FROM nota ORDER BY id").fetchall()
    finally:
        con.close()


def test_cria_backup_com_data_no_nome_e_valida(banco, tmp_path):
    agora = datetime(2026, 11, 17, 8, 30, 15)
    feito = bk.criar_backup(banco, tmp_path / "bk", agora=agora)
    assert feito.name == "pmpv_data_20261117_083015.db"
    assert bk.validar(feito) == 2
    assert _linhas(feito) == [(1000.0,), (2500.5,)]


def test_backup_nao_altera_a_origem(banco, tmp_path):
    antes = _linhas(banco)
    bk.criar_backup(banco, tmp_path / "bk")
    assert _linhas(banco) == antes


def test_backup_com_banco_aberto_e_gravando(banco, tmp_path):
    aberto = sqlite3.connect(banco)
    aberto.execute("INSERT INTO nota (valor) VALUES (3.0)")
    aberto.commit()
    feito = bk.criar_backup(banco, tmp_path / "bk")
    aberto.close()
    assert _linhas(feito)[-1] == (3.0,)


def test_retencao_mantem_so_as_mais_novas_e_ignora_nomes_manuais(banco, tmp_path):
    pasta = tmp_path / "bk"
    base = datetime(2026, 11, 1, 8, 0, 0)
    for i in range(5):
        bk.criar_backup(banco, pasta, manter=3, agora=base + timedelta(days=i))
    assert len(bk.listar(pasta)) == 3  # a retenção já rodou dentro do criar
    manual = pasta / "pmpv_data.backup_manual.db"
    manual.write_bytes(b"x")
    bk.aplicar_retencao(pasta, 2)
    nomes = [p.name for p in bk.listar(pasta)]
    assert nomes == ["pmpv_data_20261104_080000.db", "pmpv_data_20261105_080000.db"]
    assert manual.exists()


def test_retencao_exige_pelo_menos_uma(tmp_path):
    with pytest.raises(ValueError):
        bk.aplicar_retencao(tmp_path, 0)


def test_validar_recusa_arquivo_corrompido_e_inexistente(tmp_path):
    ruim = tmp_path / "ruim.db"
    ruim.write_bytes(b"isto nao e um banco sqlite" * 100)
    with pytest.raises(bk.BackupInvalido):
        bk.validar(ruim)
    with pytest.raises(bk.BackupInvalido):
        bk.validar(tmp_path / "nao_existe.db")


def test_validar_recusa_banco_sem_tabelas(tmp_path):
    vazio = tmp_path / "vazio.db"
    sqlite3.connect(vazio).close()
    with pytest.raises(bk.BackupInvalido):
        bk.validar(vazio)


def test_restaura_em_arquivo_novo_e_confere_dados(banco, tmp_path):
    feito = bk.criar_backup(banco, tmp_path / "bk")
    novo = tmp_path / "restaurado" / "teste.db"
    bk.restaurar(feito, novo)
    assert _linhas(novo) == _linhas(banco)
    assert bk.validar(novo) == 2


def test_restaurar_recusa_sobrescrever_sem_confirmacao(banco, tmp_path):
    feito = bk.criar_backup(banco, tmp_path / "bk")
    con = sqlite3.connect(banco)
    con.execute("INSERT INTO nota (valor) VALUES (9.0)")
    con.commit()
    con.close()
    with pytest.raises(FileExistsError):
        bk.restaurar(feito, banco)
    assert _linhas(banco)[-1] == (9.0,)  # nada mudou


def test_restaurar_com_confirmacao_guarda_copia_do_que_havia(banco, tmp_path):
    feito = bk.criar_backup(banco, tmp_path / "bk")
    con = sqlite3.connect(banco)
    con.execute("INSERT INTO nota (valor) VALUES (9.0)")
    con.commit()
    con.close()
    bk.restaurar(feito, banco, confirmo_sobrescrever=True)
    assert _linhas(banco) == [(1000.0,), (2500.5,)]
    guardas = list(tmp_path.glob("pmpv_data.db.antes_da_restauracao_*"))
    assert len(guardas) == 1
    assert _linhas(guardas[0])[-1] == (9.0,)


def test_restaurar_recusa_backup_corrompido_sem_tocar_no_destino(banco, tmp_path):
    ruim = tmp_path / "ruim.db"
    ruim.write_bytes(b"lixo" * 500)
    antes = _linhas(banco)
    with pytest.raises(bk.BackupInvalido):
        bk.restaurar(ruim, banco, confirmo_sobrescrever=True)
    assert _linhas(banco) == antes


def test_linha_de_comando_usa_plataforma_db(banco, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PLATAFORMA_DB", str(banco))
    pasta = tmp_path / "bk"
    assert bk.main(["criar", "--pasta", str(pasta), "--manter", "5"]) == 0
    assert len(bk.listar(pasta)) == 1
    assert "Backup criado e validado" in capsys.readouterr().out
    assert bk.main(["validar", str(bk.listar(pasta)[0])]) == 0


def test_linha_de_comando_devolve_erro_para_origem_inexistente(tmp_path, capsys):
    assert bk.main(["criar", "--origem", str(tmp_path / "x.db"), "--pasta", str(tmp_path / "bk")]) == 1
    assert "ERRO" in capsys.readouterr().err


def test_backup_fica_em_um_arquivo_so(banco, tmp_path):
    feito = bk.criar_backup(banco, tmp_path / "bk")
    bk.validar(feito)
    assert sorted(p.name for p in (tmp_path / "bk").iterdir()) == [feito.name]
