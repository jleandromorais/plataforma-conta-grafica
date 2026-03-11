from Src.Database.database import DatabasePMPV
from Src.application.use_cases.pmpv_use_cases import PMPVUseCases
from Src.infrastructure.repositories.sqlite_repositories import SqlitePMPVRepository


class TestPMPVUseCases:
    def test_salvar_sessao_completa(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pmpv_use_cases.db"))
        repo = SqlitePMPVRepository(db)
        use_cases = PMPVUseCases(repo)

        dados = {
            "Janeiro": [
                {"empresa": "PETROBRAS", "molecula": 1.0, "transporte": 0.5, "logistica": 0.2, "volume": 100}
            ],
            "Fevereiro": [],
            "Março": [],
        }
        resultado = {
            "volume_total": 3100.0,
            "custo_total": 5270.0,
            "pmpv": 1.7,
            "conta_grafica": -0.02,
            "preco_final": 1.68,
        }

        try:
            sid = use_cases.salvar_sessao_completa("Sessao Teste", dados, resultado)
            assert sid > 0
            assert db.carregar_dados_mes(sid, 1)
        finally:
            use_cases.fechar()

    def test_salvar_pmpv_mensal(self, tmp_path):
        db = DatabasePMPV(str(tmp_path / "pmpv_use_cases.db"))
        use_cases = PMPVUseCases(SqlitePMPVRepository(db))

        try:
            use_cases.salvar_pmpv_mensal("Jan/2026", 2.1234)
            assert db.buscar_pmpv_mensal("Jan/2026") == 2.1234
        finally:
            use_cases.fechar()
