"""
Testes para o módulo database.py
"""
import pytest
import sqlite3
import os
from pathlib import Path
from database import DatabasePMPV


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
        assert res[3] == 180000.0  # custo_total
        assert res[4] == 2.0  # pmpv_trimestral
        assert res[5] == -0.021  # conta_grafica
        assert res[6] == 1.979  # preco_final
    
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
