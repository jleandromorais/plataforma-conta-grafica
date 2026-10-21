from Src.Database.database import DatabasePMPV
from Src.Services.servicos_auditoria import empresa_integra_cgr
from Src.Services.servicos_concilia import FATOR_PIS_COFINS
from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.common.formatting import format_brl

class ServicosSCG:
    """Especialista na gestão de dados e formatação da Consolidação SCG."""

    def __init__(self):
        self.consolidacao = ServicosConsolidacao()

    @staticmethod
    def formatar_brl(valor: float) -> str:
        return format_brl(valor)

    def obter_periodos(self) -> list:
        return self.consolidacao.obter_periodos()

    def criar_periodo(self, nome: str):
        self.consolidacao.criar_periodo(nome.strip())

    def apagar_periodo(self, nome: str):
        self.consolidacao.apagar_periodo(nome)

    def buscar_dados_periodo(self, periodo: str) -> dict:
        """Busca os dados e garante que nenhum vem como None."""
        dados = self.consolidacao.buscar_consolidacao(periodo)
        if not dados:
            return None

        cgr = dados.get('cgr') or 0.0
        cgf = dados.get('cgf') or 0.0
        rpv = dados.get('rpv') or (cgr - cgf)
        ret = dados.get('ret') or 0.0
        rp  = dados.get('rp')  or 0.0
        scg = dados.get('scg') or 0.0

        return {
            "cgr": cgr, "cgf": cgf, "rpv": rpv,
            "ret": ret, "rp": rp, "scg": scg
        }

    def salvar_valores_manuais(self, periodo: str, cgr: float, cgf: float, ret: float, rp: float) -> float:
        """Salva valores e recalcula o RPV."""
        dados = self.consolidacao.salvar_valores(periodo, cgr=cgr, cgf=cgf, ret=ret, rp=rp)
        return dados["rpv"]

    def calcular_scg_oficial(self, periodo: str) -> dict:
        """Garante os cálculos finais e devolve os dados atualizados."""
        return self.consolidacao.recalcular_scg(periodo)

    def salvar_e_calcular(self, periodo: str, cgr: float, cgf: float, ret: float, rp: float) -> dict:
        """Grava os 4 valores escolhidos e recalcula RPV e SCG do período
        (o "Salvar manual" + "Calcular SCG" do desktop numa operação só)."""
        self.salvar_valores_manuais(periodo, cgr, cgf, ret, rp)
        return self.calcular_scg_oficial(periodo)

    @staticmethod
    def _sinal_rp(categoria: str | None) -> int:
        """Despesa de penalidade soma no RP; receita subtrai."""
        return -1 if "rec" in (categoria or "").lower() else 1

    @staticmethod
    def buscar_dados_fontes(periodo: str) -> dict:
        """Valores do período recalculados a partir dos itens de cada módulo
        (é o que a tela desktop mostra no modo Automático):

        - CGR = Σ cgr_liquido da Auditoria: NF-e (compra de gás) + CT-e da
          TAG/Mastergás (transporte via gasoduto, que a planilha oficial trata
          como parte do CGR). CT-e das demais transportadoras é frete e não
          integra o CGR;
        - RP  = Σ valor dos itens da Conciliação × (1 − 9,25% PIS/COFINS);
        - CGF e RET = o que está gravado na consolidação.
        """
        with DatabasePMPV() as db:
            cgr = sum(float(i.get("cgr_liquido") or 0)
                      for i in (db.listar_auditoria_itens(periodo) or [])
                      if i.get("tipo") == "NF-e" or empresa_integra_cgr(i.get("empresa")))
            cons = db.buscar_consolidacao(periodo) or {}
            cgf = float(cons.get("cgf") or 0)
            ret = float(cons.get("ret") or 0)
            # Saldo de penalidade = (despesas − receitas) líquido de PIS/COFINS
            # (planilha oficial "Conta Gráfica", linha "Saldo de penalidade";
            # mesma regra da tela de Conciliação). Antes somava receitas e
            # despesas juntas.
            rp = sum(ServicosSCG._sinal_rp(i.get("categoria")) * float(i.get("valor") or 0)
                     for i in (db.listar_concilia_itens(periodo) or [])) * FATOR_PIS_COFINS
        rpv = cgr - cgf
        scg = rpv + ret + rp
        return {"cgr": cgr, "cgf": cgf, "rpv": rpv, "ret": ret, "rp": rp, "scg": scg}

    def historico(self) -> list[dict]:
        """Valores gravados de cada período, do mais recente ao mais antigo."""
        linhas = []
        for p in self.obter_periodos():
            dados = self.buscar_dados_periodo(p["periodo"])
            if dados:
                bruto = self.consolidacao.buscar_consolidacao(p["periodo"]) or {}
                linhas.append({
                    "periodo": p["periodo"],
                    **dados,
                    "data_atualizacao": (bruto.get("data_atualizacao") or "")[:16],
                })
        return linhas

    def gerar_texto_historico(self) -> str:
        """Cria o texto formatado para a caixa de histórico."""
        texto = f"{'Período':<18} {'SCG':>18}   {'Atualizado em':<22}\n"
        texto += "─" * 62 + "\n"

        # Antes lia SCG e data de obter_periodos(), que só traz o nome do
        # período — o histórico mostrava R$ 0,00 e data vazia em todos os meses.
        for h in self.historico():
            texto += f"{h['periodo']:<18} {self.formatar_brl(h['scg']):>18}   {h['data_atualizacao']:<22}\n"

        return texto