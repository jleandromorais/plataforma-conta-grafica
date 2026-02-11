import sqlite3
from typing import Dict, List

class DatabasePMPV:
    def __init__(self, db_path: str = "pmpv_data.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._conectar()
        self._criar_tabelas()
    
    def _conectar(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.conn.row_factory = sqlite3.Row
    
    def _criar_tabelas(self):
        # Tabela de SESSÕES
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_modificacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                observacoes TEXT
            )
        """)
        
        # Tabela de DADOS DOS MESES (Inputs)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS dados_mes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id INTEGER NOT NULL,
                mes INTEGER NOT NULL,
                empresa TEXT NOT NULL,
                molecula REAL,
                transporte REAL,
                logistica REAL,
                volume REAL,
                FOREIGN KEY (sessao_id) REFERENCES sessoes (id) ON DELETE CASCADE
            )
        """)
        
        # Tabela de RESULTADOS (Outputs) - ATUALIZADA
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS resultados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sessao_id INTEGER NOT NULL,
                volume_total REAL,
                custo_total REAL,
                pmpv_trimestral REAL,
                conta_grafica REAL,    -- Novo Campo
                preco_final REAL,      -- Novo Campo
                data_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sessao_id) REFERENCES sessoes (id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()
    
    def criar_sessao(self, nome: str, observacoes: str = "") -> int:
        self.cursor.execute("INSERT INTO sessoes (nome, observacoes) VALUES (?, ?)", (nome, observacoes))
        self.conn.commit()
        return self.cursor.lastrowid
    
    def salvar_dados_mes(self, sessao_id: int, mes: int, dados: List[Dict]) -> bool:
        try:
            self.cursor.execute("DELETE FROM dados_mes WHERE sessao_id = ? AND mes = ?", (sessao_id, mes))
            
            for linha in dados:
                self.cursor.execute("""
                    INSERT INTO dados_mes (sessao_id, mes, empresa, molecula, transporte, logistica, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    sessao_id, mes, linha.get('empresa'), 
                    linha.get('molecula', 0), linha.get('transporte', 0), 
                    linha.get('logistica', 0), linha.get('volume', 0)
                ))
            
            self.cursor.execute("UPDATE sessoes SET data_modificacao = CURRENT_TIMESTAMP WHERE id = ?", (sessao_id,))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro DB: {e}")
            return False

    def salvar_resultado(self, sessao_id: int, vol_tot: float, custo_tot: float, 
                        pmpv: float, cg: float, final: float) -> bool:
        try:
            self.cursor.execute("""
                INSERT INTO resultados (sessao_id, volume_total, custo_total, pmpv_trimestral, conta_grafica, preco_final)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (sessao_id, vol_tot, custo_tot, pmpv, cg, final))
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Erro ao salvar resultado: {e}")
            return False

    def carregar_dados_mes(self, sessao_id: int, mes: int) -> List[Dict]:
        self.cursor.execute("SELECT * FROM dados_mes WHERE sessao_id = ? AND mes = ?", (sessao_id, mes))
        return [dict(row) for row in self.cursor.fetchall()]

    def fechar(self):
        if self.conn: self.conn.close()