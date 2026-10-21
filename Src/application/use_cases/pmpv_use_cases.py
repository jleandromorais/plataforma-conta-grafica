"""Casos de uso do módulo PMPV (camada application).

Orquestra os fluxos do PMPV entre a UI e as camadas de domínio/infraestrutura:
delega o cálculo a ``RegrasPMPV`` (domínio) e a persistência aos repositórios
(via Protocol), sem conhecer detalhes de implementação. Ver ARCHITECTURE.md.
"""
from __future__ import annotations

from typing import Any

from Src.domain.ports.repositories import PMPVRepository
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository
from Src.Services.servicos_pmpv import ExcelPMPV, RegrasPMPV


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

    def salvar_vp_por_periodo(
        self,
        dados_por_mes: dict[str, list[dict[str, Any]]],
        periodos: list[str],
        sessao_id: int | None = None,
    ) -> None:
        """Grava o VP (soma dos volumes) de cada mês com o mês do calendário,
        para o SR achar o VP certo mesmo quando o trimestre do SR (ex.: Jan–Mar)
        não coincide com o do PMPV (Nov–Jan, Fev–Abr...)."""
        for periodo, linhas in zip(periodos, dados_por_mes.values()):
            vp = sum(float(l.get("volume", 0) or 0) for l in linhas)
            self.repo.salvar_vp_periodo(periodo, vp, sessao_id)

    def buscar_trimestre_ativo(self) -> list[str]:
        return self.repo.buscar_trimestre_ativo()

    def salvar_trimestre_ativo(self, meses: list[str]) -> None:
        """Grava os 3 meses do trimestre ativo — lido por SCG, RET, CGF e o
        Excel Final para saber qual trimestre exibir."""
        self.repo.salvar_trimestre_ativo(meses)

    def salvar_com_periodos(
        self,
        nome: str,
        dados_por_mes: dict[str, list[dict[str, Any]]],
        resultado: dict[str, Any],
        periodos: list[str],
    ) -> int:
        """Mesmo efeito do "Salvar Sessão" do desktop (tela_pmpv.salvar):
        sessão completa + PMPV mensal de cada mês + trimestre ativo."""
        sessao_id = self.salvar_sessao_completa(nome, dados_por_mes, resultado)
        if periodos:
            pmpv = resultado.get("pmpv", 0.0)
            for periodo in periodos:
                self.salvar_pmpv_mensal(periodo, pmpv)
            self.salvar_vp_por_periodo(dados_por_mes, periodos, sessao_id)
            self.salvar_trimestre_ativo(periodos)
        return sessao_id

    @staticmethod
    def importar_memoria(caminho_arquivo: str, periodos: list[str]) -> dict[str, Any]:
        """Lê a planilha "Memória de Cálculo" para cada mês do trimestre.

        Retorna {"meses": {periodo: [linhas]}, "erros": [str],
        "meses_encontrados": [str]} — um mês com problema não impede os outros
        (mesmo comportamento do desktop). `meses_encontrados` são os meses que a
        planilha tem, para a tela sugerir o trimestre certo.
        Arquivo ilegível ou sem linha de meses → ValueError (nada a importar).
        """
        df = ExcelPMPV.ler_aba(caminho_arquivo)  # lida uma vez só
        meses_cols = ExcelPMPV.colunas_de_meses(df)
        encontrados = ExcelPMPV.rotulos(meses_cols)
        faixa = f"{encontrados[0]} a {encontrados[-1]}" if len(encontrados) > 1 else encontrados[0]
        # mesma comparação que a leitura usa (aceita "Fev/2026", "fev-26"...)
        faltando = [p for p in periodos if ExcelPMPV.coluna_do_mes(meses_cols, p) is None]

        meses: dict[str, list[dict[str, Any]]] = {}
        erros: list[str] = []
        if faltando and len(faltando) == len(periodos):
            erros.append(f"A planilha não tem {', '.join(faltando)}. Ela tem {', '.join(encontrados)}.")
            return {"meses": meses, "erros": erros, "meses_encontrados": encontrados}

        for periodo in periodos:
            if periodo in faltando:
                erros.append(f"{periodo} não está na planilha (ela vai de {faixa}).")
                continue
            try:
                empresas = ExcelPMPV.ler_dados_memoria_calculo(caminho_arquivo, periodo, df=df)
            except ValueError as e:
                erros.append(f"{periodo}: {e}")
                continue
            if not empresas:
                erros.append(
                    f"{periodo}: a coluna do mês existe, mas nenhuma empresa tem volume (linha E) preenchido."
                )
                continue
            meses[periodo] = [
                {
                    "empresa": nome,
                    "molecula": d["mol"],
                    "transporte": d["trans"],
                    "logistica": d["log"],
                    "volume": d["volume"],
                }
                for nome, d in empresas.items()
            ]
        return {"meses": meses, "erros": erros, "meses_encontrados": encontrados}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.repo.__exit__(exc_type, exc_val, exc_tb)
        return False

    def fechar(self):
        self.repo.fechar()
