from Src.Services.apuracao.servicos_consolidacao import ServicosConsolidacao
from Src.common.formatting import format_brl, parse_brl as _parse_brl

TOL_PROVA_REAL_RS = 1.0  # R$: abaixo disso é arredondamento


class ServicosRPV:
    """Especialista em regras de negócio e formatação para o módulo RPV."""

    def __init__(self):
        self.consolidacao = ServicosConsolidacao()

    @staticmethod
    def formatar_brl(valor: float) -> str:
        return format_brl(valor)

    @staticmethod
    def parse_brl(texto: str) -> float:
        return _parse_brl(texto)

    def obter_periodos(self) -> list:
        return self.consolidacao.obter_periodos()

    def criar_periodo(self, nome: str):
        self.consolidacao.criar_periodo(nome.strip())

    def buscar_dados_periodo(self, periodo: str) -> dict:
        """Busca os valores CGR e CGF do banco de dados e já previne valores Nulos."""
        dados = self.consolidacao.buscar_consolidacao(periodo)
        if not dados:
            return None
            
        cgr = dados.get("cgr") or 0.0
        cgf = dados.get("cgf") or 0.0
        rpv = dados.get("rpv") or (cgr - cgf)
        
        return {"cgr": cgr, "cgf": cgf, "rpv": rpv}

    def salvar_valores(self, periodo: str, cgr: float, cgf: float) -> float:
        """Salva CGR e CGF e pede ao banco para recalcular o RPV oficial."""
        dados = self.consolidacao.salvar_valores(periodo, cgr=cgr, cgf=cgf)
        return dados["rpv"]

    def prova_real(self, periodo: str) -> dict:
        """A conta do RPV gravado do mês: CGR − CGF = RPV, comparada com o RPV gravado, e de
        onde vêm os dois números (a prova real da Auditoria CGR e a do CGF). Não grava nada.

        `origem_cgr` / `origem_cgf`: o CGR gravado bate com a soma das notas? O CGF gravado
        bate com volume × PMPV? Mês sem notas (ou sem resumo) vira `None`: não dá para provar.
        """
        from Src.Services.auditoria import servicos_auditoria_lote as lote
        from Src.Services.cgf.servicos_cgf import ServicosCGF

        dados = self.consolidacao.buscar_consolidacao(periodo) or {}
        gravado = bool(dados)
        cgr = float(dados.get("cgr") or 0.0)
        cgf = float(dados.get("cgf") or 0.0)
        rpv_gravado = float(dados["rpv"]) if dados.get("rpv") is not None else None
        rpv_calculado = cgr - cgf
        diferenca = rpv_calculado - rpv_gravado if rpv_gravado is not None else None
        confere = gravado and diferenca is not None and abs(diferenca) <= TOL_PROVA_REAL_RS

        aud = lote.prova_real(periodo)
        prova_cgf = ServicosCGF().prova_real(periodo)
        return {
            "periodo": periodo,
            "gravado": gravado,
            "cgr": cgr,
            "cgf": cgf,
            "rpv_calculado": rpv_calculado,
            "rpv_gravado": rpv_gravado,
            "diferenca": diferenca,
            "confere": confere,
            "origem_cgr": {"tem_notas": aud["qtd_notas"] > 0, "valor_das_notas": aud["cgr_das_notas"] if aud["qtd_notas"] else None,
                           "confere": aud["confere"]},
            "origem_cgf": {"tem_resumo": prova_cgf["tem_resumo"], "valor_calculado": prova_cgf["cgf_calculado"],
                           "confere": prova_cgf["confere"]},
            "data_atualizacao": (dados.get("data_atualizacao") or "")[:16],
        }

    def historico(self) -> list[dict]:
        """CGR, CGF e RPV de cada período, do mais recente ao mais antigo."""
        linhas = []
        for p in self.obter_periodos():
            dados = self.consolidacao.buscar_consolidacao(p["periodo"])
            if dados:
                cgr = dados.get("cgr") or 0.0
                cgf = dados.get("cgf") or 0.0
                linhas.append({
                    "periodo": p["periodo"],
                    "cgr": cgr,
                    "cgf": cgf,
                    "rpv": dados.get("rpv") or (cgr - cgf),
                    "data_atualizacao": (dados.get("data_atualizacao") or "")[:16],
                })
        return linhas

    def gerar_texto_historico(self) -> str:
        """Monta o texto bonitinho da tabela de histórico."""
        cab = f"{'Período':<14} {'CGR':>16} {'CGF':>16} {'RPV':>16}   {'Atualizado':<16}\n"
        texto_final = cab + "─" * 80 + "\n"

        for h in self.historico():
            texto_final += (
                f"{h['periodo']:<14} "
                f"{self.formatar_brl(h['cgr']):>16} "
                f"{self.formatar_brl(h['cgf']):>16} "
                f"{self.formatar_brl(h['rpv']):>16}   "
                f"{h['data_atualizacao']:<16}\n"
            )

        return texto_final