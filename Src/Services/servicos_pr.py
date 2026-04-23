from __future__ import annotations

from Src.Database.database import DatabasePMPV


class ServicosPR:
    """
    PR = (SGR + SR) / VP

    Nomenclatura: SGR é tratado como SCG por compatibilidade com o restante do
    sistema (o campo consolidacao.scg armazena o valor equivalente ao SGR).
    PR = 0.0 quando VP = 0 para evitar divisão por zero.
    """

    def __init__(self, db: DatabasePMPV | None = None):
        self._db = db or DatabasePMPV()

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
        return f"R$ {(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def formatar_pr(valor: float) -> str:
        """Formata o PR com 4 casas decimais (R$/m³)."""
        return f"R$ {(valor or 0):,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def formatar_volume(valor: float) -> str:
        return f"{(valor or 0):,.2f} m³".replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def parse_brl(texto: str) -> float:
        """Converte 'R$ 1.234,56' ou '1234,56' para float."""
        txt = texto.strip().replace("R$", "").replace(" ", "").replace("m³", "")
        if "," in txt and "." in txt:
            txt = txt.replace(".", "").replace(",", ".")
        elif "," in txt:
            txt = txt.replace(",", ".")
        try:
            return float(txt)
        except ValueError:
            return 0.0

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
        for row in self._db.listar_sr():
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

        sr_row = self._db.buscar_sr(periodo)
        sr = (sr_row or {}).get("sr") or 0.0
        vp = (sr_row or {}).get("vp") or 0.0

        pr_row = self._db.buscar_pr(periodo)
        pr = (pr_row or {}).get("pr") or self.calcular_pr(scg, sr, vp)

        return {"scg": scg, "sr": sr, "vp": vp, "pr": pr}

    def buscar_dados_trimestral(self, periodos: list[str]) -> dict[str, float]:
        """Soma SGR/SCG, SR e VP dos períodos do trimestre e retorna o PR resultante."""
        from Src.Services.servicos_consolidacao import ServicosConsolidacao
        servicos_cons = ServicosConsolidacao()
        scg_total = 0.0
        sr_total = 0.0
        vp_total = 0.0
        for periodo in periodos:
            if not periodo:
                continue
            dados_cons = servicos_cons.buscar_consolidacao(periodo)
            scg_total += float((dados_cons or {}).get("scg") or 0.0)
            sr_row = self._db.buscar_sr(periodo)
            sr_total += float((sr_row or {}).get("sr") or 0.0)
            vp_total += float((sr_row or {}).get("vp") or 0.0)
        pr = self.calcular_pr(scg_total, sr_total, vp_total)
        return {"scg": scg_total, "sr": sr_total, "vp": vp_total, "pr": pr}

    def salvar_valores(self, periodo: str, scg: float, sr: float, vp: float) -> float:
        """Calcula e persiste o PR final para o período."""
        scg = scg or 0.0
        sr = sr or 0.0
        vp = vp or 0.0
        pr = self.calcular_pr(scg, sr, vp)
        self._db.salvar_pr(periodo, scg, sr, vp, pr)
        return pr

    def gerar_texto_historico(self) -> str:
        periodos = self._db.listar_pr()
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
