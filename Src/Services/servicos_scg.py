from Src.Services.servicos_consolidacao import ServicosConsolidacao

class ServicosSCG:
    """Especialista na gestão de dados e formatação da Consolidação SCG."""

    def __init__(self):
        self.consolidacao = ServicosConsolidacao()

    @staticmethod
    def formatar_brl(valor: float) -> str:
        """Formata um valor para Reais (ex: R$ 1.500,00)."""
        return f"R$ {(valor or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

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

    def gerar_texto_historico(self) -> str:
        """Cria o texto formatado para a caixa de histórico."""
        periodos = self.obter_periodos()
        
        texto = f"{'Período':<18} {'SCG':>18}   {'Atualizado em':<22}\n"
        texto += "─" * 62 + "\n"
        
        for p in periodos:
            scg_v = p.get('scg') or 0.0
            data  = (p.get('data_atualizacao') or '')[:16]
            texto += f"{p['periodo']:<18} {self.formatar_brl(scg_v):>18}   {data:<22}\n"
            
        return texto