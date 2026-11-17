"""Trilha de alterações: lê `historico_alteracoes` (quem grava é o `DatabasePMPV`, só quando o valor muda; guarda também quem fez, quando a API identificou o usuário)."""
from __future__ import annotations

from Src.Database.database import DatabasePMPV
from Src.common.periodos import is_periodo_valido, normalizar_periodo

LIMITE_PADRAO = 200


class ServicosTrilha:
    def __init__(self, db: DatabasePMPV | None = None):
        self._db = db or DatabasePMPV()

    def fechar(self) -> None:
        self._db.fechar()

    def listar(self, periodo: str | None = None, tabela: str | None = None, limite: int = LIMITE_PADRAO) -> list[dict]:
        """Alterações da mais recente para a mais antiga. `periodo` aceita mês ("Jul/2026") ou chave de
        trimestre ("Fev - Abr/2026"); `tabela` precisa ser uma das acompanhadas. Só lê."""
        if tabela and tabela not in DatabasePMPV.TABELAS_DA_TRILHA:
            raise ValueError(f"A tabela “{tabela}” não tem trilha. Use: {', '.join(DatabasePMPV.TABELAS_DA_TRILHA)}.")
        if periodo:
            canonico = normalizar_periodo(periodo)
            if not canonico or not (is_periodo_valido(canonico) or " - " in canonico):
                raise ValueError(f"O período “{periodo}” não é válido. Use um mês (Jul/2026) ou um trimestre "
                                 "da tarifa (Fev - Abr/2026).")
            periodo = canonico
        return self._db.listar_alteracoes(periodo=periodo or None, tabela=tabela or None, limite=limite)
