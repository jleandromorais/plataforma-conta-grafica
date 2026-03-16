from __future__ import annotations

"""
A camada "domain" serve para centralizar as regras de negócio centrais do sistema, separando o núcleo das regras (entidades, lógica, invariantes) da infraestrutura e da aplicação/orquestração. 
É o "coração" do sistema, onde se define "o que" o sistema faz, suas entidades, valores e políticas, de maneira isolada de padrões de implementação ou detalhes de frameworks, bancos e UI. 
Dessa forma, o domínio permanece estável, fácil de testar, evoluir e reutilizar.

O subdiretório "ports" representa "portas de entrada/saída" para o domínio — interfaces (ou Protocols) que descrevem como o mundo externo pode interagir com o núcleo de regras de negócio. 
Os "ports" existem para garantir que o domínio dependa apenas de interfaces abstratas, e nunca da implementação concreta de repositórios, APIs, serviços, etc. Assim, invertem-se as dependências: 
- O domínio define o contrato (por exemplo, um método salvar(), buscar(), etc), 
- a infraestrutura implementa esse contrato em classes reais.

Essa separação facilita a troca de infraestrutura sem impactar o núcleo, permite mocks e stubs para testes e mantém o domínio desacoplado de detalhes externos.
"""

from typing import Any, Dict, List, Protocol  # Importa tipos para anotações: 
# - Any: qualquer tipo de dado
# - Dict: dicionário (exemplo: Dict[str, Any] = dict com chave string, valor qualquer tipo)
# - List: lista (exemplo: List[Dict[str, Any]] = lista de dicionários)
# - Protocol: permite definir interfaces/contratos de métodos (útil para polimorfismo e duck typing)


class ConsolidacaoRepository(Protocol):
    def listar_periodos(self) -> List[Dict[str, Any]]: ...
    def criar_periodo_consolidacao(self, periodo: str, obs: str = "") -> int: ...
    def apagar_periodo(self, periodo: str): ...
    def buscar_consolidacao(self, periodo: str) -> Dict[str, Any] | None: ...
    def atualizar_cgr(self, periodo: str, valor: float): ...
    def atualizar_cgf(self, periodo: str, valor: float): ...
    def atualizar_ret(self, periodo: str, valor: float): ...
    def atualizar_rp(self, periodo: str, valor: float): ...
    def atualizar_campos_consolidacao(self, periodo: str, **campos: float): ...
    def salvar_rpv(self, periodo: str, rpv: float): ...
    def salvar_scg(self, periodo: str, scg: float): ...
    def fechar(self): ...


class PMPVRepository(Protocol):
    def criar_sessao(self, nome: str, observacoes: str = "") -> int: ...
    def salvar_dados_mes(self, sessao_id: int, mes: int, dados: List[Dict[str, Any]]) -> bool: ...
    def salvar_resultado(
        self,
        sessao_id: int,
        vol_tot: float,
        custo_tot: float,
        pmpv: float,
        cg: float,
        final: float,
    ) -> bool: ...
    def salvar_pmpv_mensal(self, periodo: str, pmpv: float): ...
    def listar_periodos(self) -> List[Dict[str, Any]]: ...
    def listar_pmpv_mensal(self) -> List[Dict[str, Any]]: ...
    def buscar_pmpv_mensal(self, periodo: str) -> float | None: ...
    def fechar(self): ...
    
    # O Python Protocol serve para definir uma interface, isto é, um "contrato": 
    # qualquer classe que implemente TODOS esses métodos, mesmo sem herdar explicitamente de PMPVRepository, será aceita onde se espera um PMPVRepository (duck typing).
    # Isso permite que o domínio dependa apenas do "quê" (assinatura dos métodos), não do "como".

    # Assim, qualquer classe concreta pode "puxar"/implementar as funções/métodos declarados aqui com a mesma assinatura.
    # Por exemplo, a classe SqlitePMPVRepository (na camada infrastructure) implementa todos os métodos de PMPVRepository. 
    # Daí, quando na camada application (use case) você faz algo como:
    #   repo: PMPVRepository = SqlitePMPVRepository()
    # o type checker garante que todos os métodos exigidos estão presentes, e o use case não sabe nada sobre SQLite ou detalhes concretos.
    #
    # Isso permite:
    # - Testar o use case usando mocks/stubs, já que você pode criar um "FakeRepository" só para o teste.
    # - Trocar por outra implementação real no futuro (ex: outro banco, API) sem alterar o domínio ou a orquestração.
    # - Garantir que métodos obrigatórios estejam implementados, facilitando manutenção e legibilidade.


    # deixa eu ve se entendi ,serve para marcacao e todos que usarem esse nome da classe estao ligado a esse arquivo (Prfv ,se possivel ,deixa minhas perguntas como essa a mostra quando for digitar ,para eu ter uma nocao da pergunta que fiz)
    # 
    # Exatamente! Quando você define uma classe como PMPVRepository (ou qualquer outro "Protocol") neste arquivo, ela serve como uma "interface/contrato" para o sistema. 
    # Ou seja, qualquer classe que implemente todos os métodos definidos nesta interface pode ser usada onde se espera um PMPVRepository — 
    # você não precisa de herança explícita! Assim, todo lugar que declara/usa "repo: PMPVRepository" está, de certa forma, "ligado" a esse contrato/interface desse arquivo.
    # Isso facilita garantir que o sistema obedeça esse "contrato" de métodos mínimos, ajuda em testes (usando mocks/fakes), e troca fácil de implementação no futuro.
    # É uma prática comum em arquiteturas como Clean Architecture ou Hexagonal.