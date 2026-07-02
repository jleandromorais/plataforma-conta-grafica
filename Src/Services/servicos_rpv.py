from Src.Services.servicos_consolidacao import ServicosConsolidacao
from Src.common.formatting import format_brl, parse_brl as _parse_brl

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

    def gerar_texto_historico(self) -> str:
        """Monta o texto bonitinho da tabela de histórico."""
        periodos = self.obter_periodos()
        
        cab = f"{'Período':<14} {'CGR':>16} {'CGF':>16} {'RPV':>16}   {'Atualizado':<16}\n"
        texto_final = cab + "─" * 80 + "\n"

        for p in periodos:
            dados = self.consolidacao.buscar_consolidacao(p["periodo"])
            if dados:
                cgr = dados.get("cgr") or 0.0
                cgf = dados.get("cgf") or 0.0
                rpv = dados.get("rpv") or (cgr - cgf)
                data = (dados.get("data_atualizacao") or "")[:16]
                
                linha = (
                    f"{p['periodo']:<14} "
                    f"{self.formatar_brl(cgr):>16} "
                    f"{self.formatar_brl(cgf):>16} "
                    f"{self.formatar_brl(rpv):>16}   "
                    f"{data:<16}\n"
                )
                texto_final += linha

        return texto_final