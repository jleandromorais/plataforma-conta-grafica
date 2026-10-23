from __future__ import annotations

from Src.common.precisao import arredondar_tarifa
from Src.domain.ports.repositories import PRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePRRepository


def _num(v: float) -> str:
    """4 casas no padrão brasileiro: 1.9667 → '1,9667'."""
    return f"{v:.4f}".replace(".", ",")


class ServicosPV:
    """
    PV = PMPV + PR

    - PMPV: valor mensal salvo no módulo PMPV (tabela pmpv_mensal)
    - PR: preço regulatório final salvo no módulo PR (tabela pr_resultados)
    """

    def __init__(self, repo: PRRepository | None = None):
        self._repo = repo or SqlitePRRepository()

    @staticmethod
    def calcular_pv(pmpv: float, pr: float) -> float:
        return (pmpv or 0.0) + (pr or 0.0)

    @staticmethod
    def formatar_brl(valor: float) -> str:
        from Src.common.formatting import format_brl4
        return format_brl4(valor)

    @staticmethod
    def parse_brl(texto: str) -> float:
        from Src.common.formatting import parse_brl
        return parse_brl(texto)

    def obter_periodos(self) -> list[dict]:
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        return ServicosConsolidacao().obter_periodos()

    def criar_periodo(self, nome: str):
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        ServicosConsolidacao().criar_periodo(nome.strip())

    def buscar_dados_periodo(self, periodo: str) -> dict[str, float] | None:
        pmpv = self._repo.buscar_pmpv_mensal(periodo) or 0.0
        pr_row = self._repo.buscar_pr(periodo)
        pr = (pr_row or {}).get("pr") or 0.0

        pv_row = self._repo.buscar_pv(periodo)
        pv = (pv_row or {}).get("pv") or self.calcular_pv(pmpv, pr)

        return {"pmpv": pmpv, "pr": pr, "pv": pv}

    def salvar_valores(self, periodo: str, pmpv: float, pr: float) -> float:
        pmpv = pmpv or 0.0
        pr = pr or 0.0
        pv = self.calcular_pv(pmpv, pr)
        self._repo.salvar_pv(periodo, pmpv, pr, pv)
        return pv

    # ── Trimestral: PV = PMPV + PR do mesmo trimestre fiscal (NT, Quadro 12) ──

    def buscar_trimestre(self, label: str, ano: int) -> dict:
        """PMPV, PR e PV do trimestre fiscal (ex.: "Fev - Abr", 2026).

        PMPV: o do 1º mês com valor em pmpv_mensal (o PMPV salva o mesmo nos 3).
        PR: o salvo pelo módulo PR com a chave do trimestre. O módulo PR usa o ano
        do ÚLTIMO mês (Nov/25–Jan/26 = "Nov - Jan/2026"); o PV, como o PMPV, usa o
        do 1º mês ("Nov - Jan/2025").
        `pmpv`/`pr`/`pv` são os valores ATUAIS dos módulos; `salvo` é o PV já
        gravado para o trimestre (o que o Excel Final usa), ou None.
        `avisos` diz o que falta ou está desatualizado."""
        from Src.common.periodos import periodos_do_trimestre

        periodos = periodos_do_trimestre(label, ano)
        chave = f"{label.strip()}/{ano}"
        avisos: list[str] = []

        por_mes = {p: self._repo.buscar_pmpv_mensal(p) for p in periodos}
        com_valor = [(p, float(v)) for p, v in por_mes.items() if v is not None]
        sem_valor = [p for p, v in por_mes.items() if v is None]
        # 4 casas, como a planilha (o PMPV mensal fica gravado sem arredondar).
        pmpv = arredondar_tarifa(com_valor[0][1]) if com_valor else 0.0
        if not com_valor:
            avisos.append(f"PMPV de {chave} não foi salvo: salve o PMPV do trimestre ou digite o valor.")
        else:
            if sem_valor:
                avisos.append(
                    f"PMPV não salvo em {', '.join(sem_valor)}; usei o de {com_valor[0][0]}. "
                    "Salve o PMPV do trimestre para ficar completo."
                )
            if len({round(v, 4) for _, v in com_valor}) > 1:
                lista = ", ".join(f"{p} = {_num(v)}" for p, v in com_valor)
                avisos.append(f"O PMPV está diferente entre os meses ({lista}). Usei o de {com_valor[0][0]}; confira.")

        chave_pr = f"{label.strip()}/{periodos[-1].split('/')[1]}"
        pr_row = self._repo.buscar_pr(chave_pr)
        pr_val = (pr_row or {}).get("pr")
        pr = float(pr_val or 0.0)
        if pr_row is None or pr_val is None:
            avisos.append(
                f"PR de {chave} ({periodos[0]} a {periodos[-1]}) não foi salvo: "
                "rode o módulo PR do trimestre ou digite o valor."
            )

        pv = arredondar_tarifa(self.calcular_pv(pmpv, pr))
        salvo = None
        pv_row = self._repo.buscar_pv(chave)
        if pv_row and pv_row.get("pv") is not None:
            salvo = {
                "pmpv": float(pv_row.get("pmpv") or 0.0),
                "pr": float(pv_row.get("pr") or 0.0),
                "pv": float(pv_row["pv"]),
                "data": str(pv_row.get("data_atualizacao") or "")[:16],
            }
            if abs(salvo["pv"] - pv) > 1e-6:
                avisos.append(
                    f"O PV salvo ({_num(salvo['pv'])}) difere do atual pelos módulos ({_num(pv)}): "
                    "PMPV ou PR mudaram depois. Confira e salve de novo para atualizar."
                )
        return {"chave": chave, "periodos": periodos, "pmpv": pmpv, "pr": pr, "pv": pv,
                "salvo": salvo, "avisos": avisos}

    def salvar_trimestre(self, label: str, ano: int, pmpv: float, pr: float) -> dict:
        """Grava o PV no trimestre e repete nos 3 meses (o Excel Final lê por mês),
        tudo numa transação. Devolve {"pv", "gravado_em"}."""
        from Src.common.periodos import periodos_do_trimestre

        periodos = periodos_do_trimestre(label, ano)
        pmpv, pr = pmpv or 0.0, pr or 0.0
        if not pmpv:
            raise ValueError("O PMPV está zerado: carregue o PMPV do trimestre ou digite o valor antes de salvar.")
        pv = self.calcular_pv(pmpv, pr)
        chaves = [f"{label.strip()}/{ano}", *periodos]
        self._repo.salvar_pv_lote(chaves, pmpv, pr, pv)
        return {"pv": pv, "gravado_em": chaves}

    def gerar_texto_historico(self) -> str:
        periodos = self._repo.listar_pv()
        cab = (
            f"{'Período':<14} {'PMPV (R$/m³)':>18} {'PR (R$/m³)':>18} "
            f"{'PV (R$/m³)':>18}   {'Atualizado':<16}\n"
        )
        texto = cab + "─" * 92 + "\n"
        for p in periodos:
            pmpv = p.get("pmpv") or 0.0
            pr = p.get("pr") or 0.0
            pv = p.get("pv") or 0.0
            data = (p.get("data_atualizacao") or "")[:16]
            linha = (
                f"{p['periodo']:<14} "
                f"{self.formatar_brl(pmpv):>18} "
                f"{self.formatar_brl(pr):>18} "
                f"{self.formatar_brl(pv):>18}   "
                f"{data:<16}\n"
            )
            texto += linha
        return texto
