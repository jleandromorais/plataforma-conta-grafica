from __future__ import annotations



"""
 O diretório `application` neste projeto organiza a lógica de aplicação, isto é, os casos de uso e regras que coordenam a execução dos processos principais da sua solução.
 Ele age como intermediário entre a interface do usuário (UI) e o domínio/núcleo do sistema (domain), orquestrando fluxos, simplificando a interação com as regras de negócio 
 e centralizando procedimentos essenciais que não dizem respeito especificamente nem à infraestrutura (persistência, APIs) nem ao domínio puro (entidades, regras fundamentais).
 Em resumo, no padrão de arquitetura clean/hexagonal/onion, o `application` define "o que" o sistema faz (através dos "use cases"), sem se acoplar à forma "de onde ou como" os dados são acessados.
"""


"""
No seu caso, neste código, a camada 'application' está organizando os casos de uso do módulo PMPV, de forma que ela atua como intermediária entre a interface do usuário e as regras de negócio (domínio).
Por exemplo, a classe PMPVUseCases define métodos como `calcular_resultados` e `salvar_sessao_completa`, que orquestram chamadas para regras de negócio em RegrasPMPV e para persistência via repositórios, mas sem saber detalhes de implementação das camadas inferiores.
Isso permite separar a lógica de orquestração de fluxos (o que o sistema faz) das implementações específicas de domínio e infraestrutura (como faz e onde busca/salva os dados).
Assim, o comportamento dela é centralizar a lógica de execução dos fluxos principais do módulo, mantendo baixo acoplamento entre as camadas do sistema.
"""

from typing import Any

from Src.domain.ports.repositories import PMPVRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository
from Src.Services.servicos_pmpv import RegrasPMPV


class PMPVUseCases:
    """Casos de uso do módulo PMPV desacoplados da UI.""" 
    def __init__(self, repo: PMPVRepository | None = None):
        self.repo = repo or SqlitePMPVRepository()

    @staticmethod
    def calcular_resultados(
        dados_extraidos: dict[str, Any],
        valor_cg: float,
        dias_config: dict[str, int],
        lista_meses: list[str],
        idx_start: int,
    ) -> dict[str, Any]:
        """
        Calcula os resultados principais do módulo PMPV.

        Esta função atua como um “caso de uso” centralizador: recebe os dados extraídos de entrada,
        além do valor da conta gráfica, configuração de dias úteis, lista de meses considerados
        e o índice inicial para o cálculo. Ela delega o processamento à regra de domínio
        implementada em `RegrasPMPV.calcular_resultados` e retorna um dicionário com os resultados
        consolidados, como volume total, custo total, PMPV, valores finais etc.

        Serve para isolar a lógica de cálculo principal do PMPV da interface do usuário 
        e da infraestrutura, tornando o fluxo de cálculo reutilizável e testável na 
        camada de aplicação.

        Args:
            dados_extraidos: Dados de entrada brutos organizados por mês/período.
            valor_cg: Valor da conta gráfica usado no cálculo.
            dias_config: Configuração dos dias úteis do período.
            lista_meses: Lista de strings representando os meses do cálculo.
            idx_start: Índice inicial do mês para iniciar os cálculos.

        Returns:
            dict[str, Any]: Resultados consolidados das regras principais de PMPV.
        """
        return RegrasPMPV.calcular_resultados(
            dados_extraidos=dados_extraidos,
            valor_cg=valor_cg,
            dias_config=dias_config,
            lista_meses=lista_meses,
            idx_start=idx_start,
        )

    def salvar_sessao_completa(
        self,
        nome: str,
        dados_por_mes: dict[str, list[dict[str, Any]]],
        resultado: dict[str, Any],
    ) -> int:
        """
        Salva uma sessão completa, incluindo os dados por mês e os resultados consolidados,
        no repositório associado.

        Args:
            nome: Nome da sessão.
            dados_por_mes: Um dicionário onde as chaves são nomes ou identificadores de meses e os valores são listas de dicionários com dados de entrada daquele mês.
            resultado: Dicionário com os resultados consolidados do cálculo (volume_total, custo_total, pmpv, conta_grafica, preco_final).

        Returns:
            int: Identificador da sessão salva no banco de dados.
        """
        sessao_id = self.repo.criar_sessao(nome)
        for idx, lista in enumerate(dados_por_mes.values(), start=1):
            self.repo.salvar_dados_mes(sessao_id, idx, lista)

        self.repo.salvar_resultado(
            sessao_id,
            resultado.get("volume_total"),
            resultado.get("vp_mensal"),
            resultado.get("vf_total", resultado.get("volume_total")),
            resultado.get("custo_total"),
            resultado.get("pmpv"),
            resultado.get("conta_grafica"),
            resultado.get("preco_final"),
        )
        return sessao_id


    def salvar_pmpv_mensal(self, periodo: str, pmpv: float):
        self.repo.salvar_pmpv_mensal(periodo, pmpv)

    def fechar(self):
        self.repo.fechar()
