from __future__ import annotations

from Src.domain.ports.repositories import PRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePRRepository


class ServicosPR:
    """
    PR = (SGR + SR) / VP

    Nomenclatura: SGR é tratado como SCG por compatibilidade com o restante do
    sistema (o campo consolidacao.scg armazena o valor equivalente ao SGR).
    PR = 0.0 quando VP = 0 para evitar divisão por zero.
    """

    def __init__(self, repo: PRRepository | None = None):
        self._repo = repo or SqlitePRRepository()

    @staticmethod
    def calcular_pr(scg: float, sr: float, vp: float) -> float:
        """PR = (SGR + SR) / VP. Retorna 0.0 se VP = 0."""
        scg = scg or 0.0
        sr = sr or 0.0
        vp = vp or 0.0
        if vp == 0.0:
            return 0.0
        return (scg + sr) / vp

    @staticmethod
    def formatar_brl(valor: float) -> str:
        from Src.common.formatting import format_brl
        return format_brl(valor)

    @staticmethod
    def formatar_pr(valor: float) -> str:
        """Formata o PR com 4 casas decimais (R$/m³)."""
        from Src.common.formatting import format_brl4
        return format_brl4(valor)

    @staticmethod
    def formatar_volume(valor: float) -> str:
        from Src.common.formatting import format_brl_plain
        return f"{format_brl_plain(valor)} m³"

    @staticmethod
    def parse_brl(texto: str) -> float:
        from Src.common.formatting import parse_brl
        return parse_brl(texto)

    def obter_periodos(self) -> list[dict]:
        """Retorna períodos cadastrados na consolidação (fonte do SCG/SGR)."""
        from Src.Services.servicos_consolidacao import ServicosConsolidacao
        return ServicosConsolidacao().obter_periodos()

    def obter_todos_periodos(self) -> list[str]:
        """Retorna todos os períodos disponíveis (consolidação + sr_resultados), sem duplicatas."""
        vistos: set[str] = set()
        periodos: list[str] = []
        for p in self.obter_periodos():
            per = p.get("periodo", "")
            if per and per not in vistos:
                vistos.add(per)
                periodos.append(per)
        for row in self._repo.listar_sr():
            per = row.get("periodo", "")
            if per and per not in vistos:
                vistos.add(per)
                periodos.append(per)
        return periodos

    def criar_periodo(self, nome: str):
        from Src.Services.servicos_consolidacao import ServicosConsolidacao
        ServicosConsolidacao().criar_periodo(nome.strip())

    def buscar_dados_periodo(self, periodo: str) -> dict[str, float] | None:
        """
        Agrega SGR/SCG, SR e VP do banco para o período.
        Busca SCG da tabela consolidacao, SR e VP da tabela sr_resultados.
        """
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        dados_cons = ServicosConsolidacao().buscar_consolidacao(periodo)
        scg = (dados_cons or {}).get("scg") or 0.0

        sr_row = self._repo.buscar_sr(periodo)
        sr = (sr_row or {}).get("sr") or 0.0
        vp = (sr_row or {}).get("vp") or 0.0

        pr_row = self._repo.buscar_pr(periodo)
        pr = (pr_row or {}).get("pr") or self.calcular_pr(scg, sr, vp)

        return {"scg": scg, "sr": sr, "vp": vp, "pr": pr}

    def buscar_dados_trimestral(self, periodos: list[str]) -> dict:
        """
        Calcula o PR trimestral pela fórmula normalizada por VP mensal:
            PR = Σ(SCG_m / VP_m) + Σ(SR_m / VP_m)

        Retorna totais + detalhamento por mês + PR final.
        """
        from Src.Services.servicos_consolidacao import ServicosConsolidacao
        servicos_cons = ServicosConsolidacao()

        # Primeira passagem: coleta dados de todos os meses
        meses_raw = []
        scg_total = sr_total = vp_total = 0.0

        for periodo in periodos:
            if not periodo:
                continue
            dados_cons = servicos_cons.buscar_consolidacao(periodo)
            scg_m = float((dados_cons or {}).get("scg") or 0.0)
            sr_row = self._repo.buscar_sr(periodo)
            sr_m  = float((sr_row or {}).get("sr") or 0.0)
            vp_m  = float((sr_row or {}).get("vp") or 0.0)

            scg_total += scg_m
            sr_total  += sr_m
            vp_total  += vp_m

            meses_raw.append({
                "periodo": periodo,
                "scg": scg_m,
                "sr":  sr_m,
                "vp":  vp_m,
            })

        # Segunda passagem: calcula parcelas usando VP do mês.
        # Meses com VP=0 usam VP total do trimestre como fallback para não
        # distorcer o PR — se nem o VP total existir, a parcela fica em zero
        # e o mês é marcado para aviso.
        meses = []
        pr_acumulado = 0.0
        meses_sem_vp = []

        for m in meses_raw:
            vp_ref = m["vp"] if m["vp"] else vp_total
            if vp_ref:
                parcela = (m["scg"] + m["sr"]) / vp_ref
            else:
                parcela = 0.0
                meses_sem_vp.append(m["periodo"])
            pr_acumulado += parcela
            meses.append({**m, "parcela_pr": parcela, "vp_sem_dado": not m["vp"]})

        return {
            "scg": scg_total,
            "sr":  sr_total,
            "vp":  vp_total,
            "pr":  pr_acumulado,
            "meses": meses,
            "meses_sem_vp": meses_sem_vp,  # lista de períodos sem VP para aviso na UI
        }

    def salvar_valores(self, periodo: str, scg: float, sr: float, vp: float) -> float:
        """Calcula e persiste o PR final para o período."""
        scg = scg or 0.0
        sr = sr or 0.0
        vp = vp or 0.0
        pr = self.calcular_pr(scg, sr, vp)
        self._repo.salvar_pr(periodo, scg, sr, vp, pr)
        return pr

    def gerar_texto_historico(self) -> str:
        periodos = self._repo.listar_pr()
        cab = (
            f"{'Período':<14} {'SGR/SCG':>16} {'SR':>16} "
            f"{'VP (m³)':>14} {'PR (R$/m³)':>18}   {'Atualizado':<16}\n"
        )
        texto = cab + "─" * 90 + "\n"
        for p in periodos:
            scg = p.get("scg") or 0.0
            sr = p.get("sr") or 0.0
            vp = p.get("vp") or 0.0
            pr = p.get("pr") or 0.0
            data = (p.get("data_atualizacao") or "")[:16]
            linha = (
                f"{p['periodo']:<14} "
                f"{self.formatar_brl(scg):>16} "
                f"{self.formatar_brl(sr):>16} "
                f"{self.formatar_volume(vp):>14} "
                f"{self.formatar_pr(pr):>18}   "
                f"{data:<16}\n"
            )
            texto += linha
        return texto
