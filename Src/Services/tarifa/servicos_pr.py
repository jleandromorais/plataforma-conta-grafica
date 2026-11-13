from __future__ import annotations

from Src.application.use_cases.sr_use_cases import vp_do_mes
from Src.common.periodos import TRIMESTRES_FISCAIS_ABREVS, periodos_do_trimestre
from Src.common.precisao import arredondar_tarifa
from Src.domain.ports.repositories import PRRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePRRepository, SqliteSRRepository
from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao

_MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def meses_apurados_do_pr(meses_pr: list[str]) -> list[str]:
    """Trimestre civil cujo SCG/SR entra no PR (planilha "Q7, Q8 e Q9 PR-PV"):
    os 3 meses que terminam 2 meses antes do 1º mês do PR. PR Mai–Jul/26 →
    Jan–Mar/26; PR Fev–Abr/26 → Out–Dez/25."""
    mes, ano = meses_pr[0].split("/")
    base = int(ano) * 12 + _MESES.index(mes)
    return [f"{_MESES[(base - k) % 12]}/{(base - k) // 12}" for k in (4, 3, 2)]


def meses_da_chave_pr(chave_pr: str) -> list[str]:
    """Chave do PR → os 3 meses em que ele é aplicado. A chave usa o ano do ÚLTIMO mês:
    "Fev - Abr/2026" → Fev/2026, Mar/2026, Abr/2026; "Nov - Jan/2026" → Nov/2025, Dez/2025, Jan/2026.
    Chave fora desse formato (ex.: "Jan/2026") → ValueError (vira 422)."""
    label, _, ano = (chave_pr or "").strip().rpartition("/")
    if label not in {nome for nome, _ in TRIMESTRES_FISCAIS_ABREVS} or not ano.isdigit():
        raise ValueError(f"“{chave_pr}” não é um trimestre da tarifa. Use Nov - Jan, Fev - Abr, Mai - Jul ou "
                         "Ago - Out com o ano do último mês, por exemplo Fev - Abr/2026.")
    ano_inicio = int(ano) - 1 if label == "Nov - Jan" else int(ano)  # o Nov - Jan começa no ano anterior
    return periodos_do_trimestre(label, ano_inicio)


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
        from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
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
        from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
        ServicosConsolidacao().criar_periodo(nome.strip())

    def buscar_dados_periodo(self, periodo: str) -> dict[str, float] | None:
        """
        Agrega SGR/SCG, SR e VP do banco para o período.
        Busca SCG da tabela consolidacao, SR e VP da tabela sr_resultados.
        """
        from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao

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
        from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
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

    @staticmethod
    def apurar_pr_nt(meses: list[dict], vps: list[float], pmpv: float) -> dict:
        """PR da Nota Técnica: ROUND((Σ SCG×(1+SELIC acum) + Σ SR com SELIC) / VP; 4).

        `meses`: os 3 meses do trimestre civil apurado, cada um com `scg`,
        `selic` (% acumulada até o fim do trimestre, a mesma do SR) e `sr`
        (SR do mês já com SELIC). `vps`: VP de cada mês do PR."""
        detalhe = [{**m, "scg_selic": m["scg"] * (1 + m["selic"] / 100)} for m in meses]
        scg_selic = sum(m["scg_selic"] for m in detalhe)
        sr = sum(m["sr"] for m in detalhe)
        vp = sum(vps)
        saldo = scg_selic + sr
        pr = arredondar_tarifa(saldo / vp) if vp else 0.0
        return {"meses": detalhe, "scg_selic": scg_selic, "sr": sr, "saldo_total": saldo,
                "vp": vp, "pr": pr, "pmpv": pmpv, "pv": arredondar_tarifa(pmpv + pr) if pmpv else 0.0}

    def apurar_trimestre(self, meses_pr: list[str]) -> dict:
        """Lê do banco o que o PR de `meses_pr` precisa e aplica `apurar_pr_nt`:
        SCG da consolidação e SELIC/SR do SR salvo do trimestre civil apurado,
        VP do PMPV de cada mês do PR. `pendencias` diz o que falta."""
        apurados = meses_apurados_do_pr(meses_pr)
        label_sr = f"{apurados[0]}_{apurados[-1]}"
        pendencias = []
        repo_sr = SqliteSRRepository()
        cons = ServicosConsolidacao()
        try:
            sr_salvo = {r["mes"]: r for r in (repo_sr.buscar_sr_trimestre(label_sr) or [])}
            if not sr_salvo:
                pendencias.append(f"Salve o SR de {apurados[0]} a {apurados[-1]} na tela SR.")
            meses = []
            for p in apurados:
                dados = cons.buscar_consolidacao(p)
                if not dados:
                    pendencias.append(f"Sem SCG gravado para {p}.")
                if sr_salvo and p not in sr_salvo:
                    # SR salvo pela metade: o mês que falta entraria como 0 no PR.
                    pendencias.append(f"Falta o SR de {p} no SR salvo de {apurados[0]} a {apurados[-1]}: "
                                      "salve o SR do trimestre de novo na tela SR.")
                linha = sr_salvo.get(p) or {}
                meses.append({"periodo": p, "scg": float((dados or {}).get("scg") or 0.0),
                              "selic": float(linha.get("selic_mensal") or 0.0),
                              "sr": float(linha.get("sr_selic") or 0.0)})
            vps = [float(vp_do_mes(repo_sr, p) or 0.0) for p in meses_pr]
        finally:
            repo_sr.fechar()
            cons.fechar()
        for p, vp in zip(meses_pr, vps):
            if not vp:
                pendencias.append(f"Sem VP para {p}: salve o PMPV deste trimestre.")
        pmpv = float(self._repo.buscar_pmpv_mensal(meses_pr[0]) or 0.0)
        if not pmpv:
            pendencias.append(f"Sem PMPV para {meses_pr[0]}.")
        return {**self.apurar_pr_nt(meses, vps, pmpv), "meses_pr": meses_pr,
                "meses_apurados": apurados, "vps": vps, "pendencias": pendencias}

    def salvar_apurado(self, chave_pr: str) -> float:
        """Refaz a apuração do PR de `chave_pr` ("Fev - Abr/2026") com o que está no banco e grava
        o valor do SERVIDOR (nunca números vindos da tela). Se faltar algo (SR, SCG, VP, PMPV) ou o
        VP der zero, levanta ValueError (422) com as pendências, uma por linha, e NADA é gravado."""
        meses_pr = meses_da_chave_pr(chave_pr)
        apuracao = self.apurar_trimestre(meses_pr)
        if apuracao["pendencias"]:
            raise ValueError(f"O PR de {chave_pr} não foi salvo. Resolva antes:\n"
                             + "\n".join(f"- {p}" for p in apuracao["pendencias"]))
        if apuracao["vp"] <= 0:
            raise ValueError(f"O PR de {chave_pr} não foi salvo: o VP de {meses_pr[0]} a {meses_pr[-1]} "
                             "está zerado. Salve o PMPV deste trimestre.")
        return self.salvar_valores(chave_pr, apuracao["scg_selic"], apuracao["sr"], apuracao["vp"])

    def salvar_valores(self, periodo: str, scg: float, sr: float, vp: float) -> float:
        """Calcula e persiste o PR final para o período."""
        scg = scg or 0.0
        sr = sr or 0.0
        vp = vp or 0.0
        pr = arredondar_tarifa(self.calcular_pr(scg, sr, vp))  # ROUND(...;4), como a planilha
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
