"""A migração de colunas não pode derrubar a requisição que perde a corrida contra outra.

Em produção, o Dashboard dispara 5 requisições juntas. Logo depois de um deploy que acrescenta colunas,
todas veem a coluna faltando e só a primeira consegue o ALTER TABLE; as outras davam
`duplicate column name` e viravam erro 500.
"""
from __future__ import annotations

import sqlite3

import pytest

from Src.Database.database import DatabasePMPV


class _CursorQueVeColunaFaltando:
    """Imita a leitura atrasada: o PRAGMA devolve a tabela sem a coluna, embora outra conexão já a criou."""

    def __init__(self, real: sqlite3.Cursor):
        self._real = real
        self._pragma = False

    def execute(self, sql, *args):
        self._pragma = sql.strip().upper().startswith("PRAGMA TABLE_INFO")
        return self._real.execute(sql, *args)

    def fetchall(self):
        return [] if self._pragma else self._real.fetchall()


def test_coluna_que_outra_requisicao_acabou_de_criar_nao_gera_erro(tmp_path):
    with DatabasePMPV(db_path=str(tmp_path / "corrida.db")) as db:
        db.cursor = _CursorQueVeColunaFaltando(db.cursor)
        # a coluna já existe, mas a leitura diz que não: o ALTER falha com "duplicate column name"
        db._garantir_coluna("historico_alteracoes", "motivo", "TEXT")


def test_outro_erro_do_alter_continua_aparecendo(tmp_path):
    with DatabasePMPV(db_path=str(tmp_path / "erro.db")) as db:
        db.cursor = _CursorQueVeColunaFaltando(db.cursor)
        with pytest.raises(sqlite3.OperationalError):
            db._garantir_coluna("historico_alteracoes", "motivo", "TEXTO INVALIDO ((")
