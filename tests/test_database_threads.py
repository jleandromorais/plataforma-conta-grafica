"""A API abre a conexão na dependência (uma thread do pool) e usa no endpoint
(muitas vezes outra thread). Com várias requisições juntas — o Painel do Ciclo
faz ~30 — o SQLite recusava: "objects created in a thread can only be used in
that same thread", e a tela mostrava "sem conexão com o servidor"."""
import threading

from Src.Database.database import DatabasePMPV


def test_conexao_criada_numa_thread_pode_ser_usada_e_fechada_em_outra(tmp_path):
    db = DatabasePMPV(str(tmp_path / "t.db"))
    erros = []

    def usar():
        try:
            db.conn.execute("SELECT 1").fetchone()
            db.fechar()
        except Exception as exc:  # noqa: BLE001 — o teste quer ver qualquer erro
            erros.append(exc)

    t = threading.Thread(target=usar)
    t.start()
    t.join()
    assert erros == []
