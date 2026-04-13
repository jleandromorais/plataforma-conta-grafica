"""
Testes para o módulo database.py
"""
import pytest
import sqlite3
import os
from pathlib import Path
from Src.Database.database import DatabasePMPV


class TestDatabasePMPV:
    """Suite de testes para a classe DatabasePMPV"""
    
    @pytest.fixture
    def db_temp(self, tmp_path):
        """Cria um banco de dados temporário para testes"""
        db_path = tmp_path / "test_pmpv.db"
        db = DatabasePMPV(str(db_path))
        yield db
        db.fechar()
        if db_path.exists():
            db_path.unlink()
    
    def test_criar_banco_dados(self, tmp_path):
        """Testa se o banco de dados é criado corretamente"""
        db_path = tmp_path / "test.db"
        db = DatabasePMPV(str(db_path))
        
        assert db_path.exists()
        assert db.conn is not None
        assert db.cursor is not None
        
        db.fechar()
    
    def test_criar_tabelas(self, db_temp):
        """Verifica se todas as tabelas são criadas"""
        cursor = db_temp.cursor
        
        # Verifica tabela sessoes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessoes'")
        assert cursor.fetchone() is not None
        
        # Verifica tabela dados_mes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dados_mes'")
        assert cursor.fetchone() is not None
        
        # Verifica tabela resultados
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='resultados'")
        assert cursor.fetchone() is not None

        # Verifica tabela de progresso do Excel final
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='excel_final_execucoes'")
        assert cursor.fetchone() is not None

    def test_registrar_execucao_excel_final_incrementa_execucao(self, db_temp):
        exec_1 = db_temp.registrar_execucao_excel_final(
            nome_sessao="Sessao Geral",
            periodo="Dez/2025",
            etapa="RET",
            caminho_arquivo="C:/tmp/final.xlsx",
        )
        exec_2 = db_temp.registrar_execucao_excel_final(
            nome_sessao="Sessao Geral",
            periodo="Dez/2025",
            etapa="RET",
            caminho_arquivo="C:/tmp/final.xlsx",
        )

        assert exec_1 == 1
        assert exec_2 == 2

        linhas = db_temp.listar_execucoes_excel_final(nome_sessao="Sessao Geral", periodo="Dez/2025")
        assert len(linhas) == 1
        assert linhas[0]["etapa"] == "RET"
        assert linhas[0]["execucao"] == 2

    def test_periodo_curto_e_longo_resolvem_para_mesmo_pmpv(self, db_temp):
        db_temp.salvar_pmpv_mensal("Dez/25", 2.5)

        assert db_temp.buscar_pmpv_mensal("Dez/2025") == 2.5

        periodos = db_temp.listar_pmpv_mensal()
        assert len(periodos) == 1
        assert periodos[0]["periodo"] == "Dez/2025"

    def test_busca_consolidacao_considera_periodo_normalizado(self, db_temp):
        db_temp.atualizar_cgr("Dez/25", 100.0)
        db_temp.atualizar_cgf("Dez/2025", 40.0)

        dados = db_temp.buscar_consolidacao("Dez/2025")

        assert dados is not None
        assert dados["periodo"] == "Dez/2025"
        assert dados["cgr"] == 100.0
        assert dados["cgf"] == 40.0

    def test_apagar_periodo_remove_variantes_legadas_da_consolidacao(self, db_temp):
        db_temp.cursor.execute(
            "INSERT INTO consolidacao (periodo, cgr) VALUES (?, ?)",
            ("Dez/25", 10.0),
        )
        db_temp.cursor.execute(
            "INSERT INTO consolidacao (periodo, cgf) VALUES (?, ?)",
            ("Dez/2025", 5.0),
        )
        db_temp.conn.commit()

        db_temp.apagar_periodo("DEZ/25")

        db_temp.cursor.execute(
            "SELECT COUNT(*) FROM consolidacao WHERE periodo IN (?, ?)",
            ("Dez/25", "Dez/2025"),
        )
        assert db_temp.cursor.fetchone()[0] == 0

    def test_apagar_periodo_completo_remove_dados_de_todas_as_tabelas(self, db_temp):
        db_temp.cursor.execute(
            "INSERT INTO consolidacao (periodo, cgr) VALUES (?, ?)",
            ("Dez/25", 100.0),
        )
        db_temp.cursor.execute(
            "INSERT INTO consolidacao (periodo, cgf) VALUES (?, ?)",
            ("Dez/2025", 40.0),
        )
        db_temp.conn.commit()

        db_temp.salvar_pmpv_mensal("Dez/25", 2.5)
        db_temp.salvar_sr("Dez/2025", 10.0, 8.0, 0.5, 1.0)
        db_temp.salvar_cgf_resumo("Dez/25", 10.0, 1.0, 2.0, 0.0, 7.0)
        db_temp.salvar_auditoria_itens("Dez/2025", [
            {
                "empresa": "Empresa A",
                "tipo": "NF",
                "numero": "1",
                "valor_total": 10.0,
            }
        ])
        db_temp.salvar_ret_itens("Dez/25", [
            {
                "arquivo": "ret.pdf",
                "tipo_encargo": "EC",
                "empresa": "Empresa B",
                "numero_nd": "22",
                "valor_total": 15.0,
            }
        ])
        db_temp.salvar_concilia_itens("Dez/2025", [
            {
                "arquivo": "conc.xlsx",
                "categoria": "Receita",
                "valor": 20.0,
                "status": "OK",
                "metodo": "manual",
            }
        ])
        db_temp.registrar_execucao_excel_final(
            nome_sessao="Sessao Completa",
            periodo="Dez/25",
            etapa="RET",
            caminho_arquivo="C:/tmp/final.xlsx",
        )

        removidos = db_temp.apagar_periodo_completo("DEZ/25")

        assert removidos["consolidacao"] == 2
        assert removidos["pmpv_mensal"] == 1
        assert removidos["sr_resultados"] == 1
        assert removidos["cgf_resumo"] == 1
        assert removidos["auditoria_itens"] == 1
        assert removidos["ret_itens"] == 1
        assert removidos["concilia_itens"] == 1
        assert removidos["excel_final_execucoes"] == 1

        assert db_temp.buscar_consolidacao("Dez/2025") is None
        assert db_temp.buscar_pmpv_mensal("Dez/2025") is None
        assert db_temp.buscar_sr("Dez/2025") is None
        assert db_temp.buscar_cgf_resumo("Dez/2025") is None
        assert db_temp.listar_auditoria_itens("Dez/2025") == []
        assert db_temp.listar_ret_itens("Dez/2025") == []
        assert db_temp.listar_concilia_itens("Dez/2025") == []
        assert db_temp.listar_execucoes_excel_final(periodo="Dez/2025") == []

    def test_registrar_execucao_excel_final_separa_por_etapa(self, db_temp):
        db_temp.registrar_execucao_excel_final(
            nome_sessao="Sessao Geral",
            periodo="Dez/2025",
            etapa="RET",
            caminho_arquivo="C:/tmp/final.xlsx",
        )
        db_temp.registrar_execucao_excel_final(
            nome_sessao="Sessao Geral",
            periodo="Dez/2025",
            etapa="Auditoria XML",
            caminho_arquivo="C:/tmp/final.xlsx",
        )

        linhas = db_temp.listar_execucoes_excel_final(nome_sessao="Sessao Geral", periodo="Dez/2025")
        etapas = {linha["etapa"] for linha in linhas}

        assert len(linhas) == 2
        assert "RET" in etapas
        assert "Auditoria XML" in etapas
    
    def test_criar_sessao(self, db_temp):
        """Testa a criação de uma nova sessão"""
        sessao_id = db_temp.criar_sessao("Teste Sessão", "Observações de teste")
        
        assert sessao_id > 0
        
        # Verifica se a sessão foi criada
        db_temp.cursor.execute("SELECT * FROM sessoes WHERE id = ?", (sessao_id,))
        sessao = db_temp.cursor.fetchone()
        
        assert sessao is not None
        assert sessao[1] == "Teste Sessão"
        assert sessao[4] == "Observações de teste"
    
    def test_salvar_dados_mes(self, db_temp):
        """Testa o salvamento de dados mensais"""
        # Cria uma sessão
        sessao_id = db_temp.criar_sessao("Teste")
        
        # Dados de exemplo
        dados = [
            {
                'empresa': 'PETROBRAS',
                'molecula': 1.5,
                'transporte': 0.3,
                'logistica': 0.2,
                'volume': 1000
            },
            {
                'empresa': 'GALP',
                'molecula': 1.6,
                'transporte': 0.35,
                'logistica': 0.25,
                'volume': 800
            }
        ]
        
        # Salva dados
        resultado = db_temp.salvar_dados_mes(sessao_id, 1, dados)
        
        assert resultado is True
        
        # Verifica se os dados foram salvos
        db_temp.cursor.execute("SELECT COUNT(*) FROM dados_mes WHERE sessao_id = ? AND mes = ?", 
                              (sessao_id, 1))
        count = db_temp.cursor.fetchone()[0]
        
        assert count == 2
    
    def test_salvar_dados_mes_substitui_existente(self, db_temp):
        """Testa se salvar novamente substitui os dados antigos"""
        sessao_id = db_temp.criar_sessao("Teste")
        
        dados1 = [{'empresa': 'PETROBRAS', 'molecula': 1.5, 'transporte': 0.3, 
                   'logistica': 0.2, 'volume': 1000}]
        dados2 = [{'empresa': 'GALP', 'molecula': 1.6, 'transporte': 0.35, 
                   'logistica': 0.25, 'volume': 800}]
        
        db_temp.salvar_dados_mes(sessao_id, 1, dados1)
        db_temp.salvar_dados_mes(sessao_id, 1, dados2)
        
        # Deve haver apenas 1 registro (o último)
        db_temp.cursor.execute("SELECT COUNT(*) FROM dados_mes WHERE sessao_id = ? AND mes = ?", 
                              (sessao_id, 1))
        count = db_temp.cursor.fetchone()[0]
        
        assert count == 1
        
        # Verifica se é o registro correto
        db_temp.cursor.execute("SELECT empresa FROM dados_mes WHERE sessao_id = ? AND mes = ?", 
                              (sessao_id, 1))
        empresa = db_temp.cursor.fetchone()[0]
        
        assert empresa == 'GALP'
    
    def test_carregar_dados_mes(self, db_temp):
        """Testa o carregamento de dados mensais"""
        sessao_id = db_temp.criar_sessao("Teste")
        
        dados_originais = [
            {
                'empresa': 'PETROBRAS',
                'molecula': 1.5,
                'transporte': 0.3,
                'logistica': 0.2,
                'volume': 1000
            }
        ]
        
        db_temp.salvar_dados_mes(sessao_id, 1, dados_originais)
        dados_carregados = db_temp.carregar_dados_mes(sessao_id, 1)
        
        assert len(dados_carregados) == 1
        assert dados_carregados[0]['empresa'] == 'PETROBRAS'
        assert dados_carregados[0]['molecula'] == 1.5
        assert dados_carregados[0]['volume'] == 1000
    
    def test_salvar_resultado(self, db_temp):
        """Testa o salvamento de resultados"""
        sessao_id = db_temp.criar_sessao("Teste")
        
        resultado = db_temp.salvar_resultado(
            sessao_id=sessao_id,
            vol_tot=90000.0,
            vp_tot=180000.0,
            vf_tot=175000.0,
            custo_tot=180000.0,
            pmpv=2.0,
            cg=-0.021,
            final=1.979
        )
        
        assert resultado is True
        
        # Verifica se foi salvo
        db_temp.cursor.execute("SELECT * FROM resultados WHERE sessao_id = ?", (sessao_id,))
        res = db_temp.cursor.fetchone()
        
        assert res is not None
        assert res[2] == 90000.0  # volume_total
        assert res[3] == 180000.0  # vp_total
        assert res[4] == 175000.0  # vf_total
        assert res[5] == 180000.0  # custo_total
        assert res[6] == 2.0  # pmpv_trimestral
        assert res[7] == -0.021  # conta_grafica
        assert res[8] == 1.979  # preco_final
    
    def test_dados_com_campos_faltantes(self, db_temp):
        """Testa o salvamento com campos faltantes (valores padrão)"""
        sessao_id = db_temp.criar_sessao("Teste")
        
        dados = [
            {
                'empresa': 'TESTE',
                # molecula, transporte, logistica e volume ausentes
            }
        ]
        
        resultado = db_temp.salvar_dados_mes(sessao_id, 1, dados)
        assert resultado is True
        
        dados_carregados = db_temp.carregar_dados_mes(sessao_id, 1)
        assert dados_carregados[0]['molecula'] == 0
        assert dados_carregados[0]['transporte'] == 0
        assert dados_carregados[0]['logistica'] == 0
        assert dados_carregados[0]['volume'] == 0
