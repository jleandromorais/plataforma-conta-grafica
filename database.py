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
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
    
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
        
        # Tabela de PMPV MENSAL — valor R$/m³ por período
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS pmpv_mensal (
                periodo           TEXT PRIMARY KEY,
                pmpv              REAL NOT NULL,
                data_atualizacao  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
                            
                            CREATE TABLE IF NOT EXISTS  consolidacao(
                                id INTEGER PRIMARY KEY  AUTOINCREMENT,
                                periodo TEXT NOT NULL,
                                
                                
                                --TOATIS DE  CADA MODULO
                                
                                cgr REAL DEFAULT 0,
                                ret REAL DEFAULT 0,
                                rp REAL DEFAULT 0,
                                
                                
                                --VALORES PARA FORMULA FINAL
                                rpv REAL DEFAULT 0,
                                cgf REAL DEFAULT 0,
                                
                                --RESULTADO FINAL
                                scg REAL DEFAULT 0,
                                
                                
                                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                observacoes TEXT
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
    
    # ==========================================
    # FUNÇÕES DE CONSOLIDAÇÃO
    # ==========================================
    
    def _garantir_periodo(self, periodo: str):
        """Cria o período na tabela consolidacao se ainda não existir."""
        self.cursor.execute("SELECT id FROM consolidacao WHERE periodo = ?", (periodo,))
        if not self.cursor.fetchone():
            self.criar_periodo_consolidacao(periodo)

    def criar_periodo_consolidacao(self, periodo: str, obs: str = "") -> int:
        """Cria um novo período de consolidação"""
        self.cursor.execute(
            "INSERT INTO consolidacao (periodo, observacoes) VALUES (?, ?)", 
            (periodo, obs)
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def atualizar_cgr(self, periodo: str, valor: float):
        self._garantir_periodo(periodo)
        """Atualiza o CGR (Auditoria XML)"""
        self.cursor.execute("""
            UPDATE consolidacao
            SET cgr = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (valor, periodo))
        self.conn.commit()
    
    def atualizar_ret(self, periodo: str, valor: float):
        self._garantir_periodo(periodo)
        """Atualiza o RET (Módulo RET)"""
        self.cursor.execute("""
            UPDATE consolidacao
            SET ret = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (valor, periodo))
        self.conn.commit()
    
    def atualizar_rp(self, periodo: str, valor: float):
        self._garantir_periodo(periodo)
        """Atualiza o RP (Conciliação)"""
        self.cursor.execute("""
            UPDATE consolidacao
            SET rp = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (valor, periodo))
        self.conn.commit()
            
    def atualizar_cgf(self, periodo: str, valor: float):
        """Atualiza somente o CGF (Volume Faturado)."""
        self._garantir_periodo(periodo)
        self.cursor.execute("""
            UPDATE consolidacao
            SET cgf = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (valor, periodo))
        self.conn.commit()

    def calcular_e_salvar_rpv(self, periodo: str) -> float:
        """Calcula RPV = CGR − CGF, salva no banco e retorna o valor."""
        self._garantir_periodo(periodo)
        self.cursor.execute("SELECT cgr, cgf FROM consolidacao WHERE periodo = ?", (periodo,))
        row = self.cursor.fetchone()
        if not row:
            return 0.0
        dados = dict(row)
        rpv = (dados.get('cgr') or 0.0) - (dados.get('cgf') or 0.0)
        self.cursor.execute("""
            UPDATE consolidacao
            SET rpv = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (rpv, periodo))
        self.conn.commit()
        return rpv

    def atualizar_rpv_cgf(self, periodo: str, rpv: float, cgf: float):
        """Atualiza RPV e CGF (valores manuais)"""
        self.cursor.execute("""
            UPDATE consolidacao
            SET rpv = ?, cgf = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (rpv, cgf, periodo))
        self.conn.commit()
        
    def calcular_scg(self, periodo: str) -> float:
        """Calcula o SCG e salva"""
        self.cursor.execute("SELECT * FROM consolidacao WHERE periodo = ?", (periodo,))
        row = self.cursor.fetchone()
        
        if not row:
            return 0.0
        
        dados = dict(row)
        cgr = dados.get('cgr', 0)
        cgf = dados.get('cgf', 0)
        rpv = dados.get('rpv', 0)
        ret = dados.get('ret', 0)
        rp = dados.get('rp', 0)
        
        # Fórmula: SCG = RPV(CGR + CGF) + RET + RP
        scg = rpv * (cgr + cgf) + ret + rp
        
        self.cursor.execute("""
            UPDATE consolidacao
            SET scg = ?, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (scg, periodo))
        self.conn.commit()
        return scg
    
    def buscar_consolidacao(self, periodo: str) -> dict:
        """Busca dados de consolidação de um período"""
        self.cursor.execute("SELECT * FROM consolidacao WHERE periodo = ?", (periodo,))
        row = self.cursor.fetchone()
        return dict(row) if row else None
    
    def listar_periodos(self) -> List:
        """Lista todos os períodos de consolidação"""
        self.cursor.execute("SELECT periodo, scg, data_atualizacao FROM consolidacao ORDER BY data_criacao DESC")
        return [dict(row) for row in self.cursor.fetchall()]
        
        
        
    # ==========================================
    # PMPV MENSAL
    # ==========================================

    def salvar_pmpv_mensal(self, periodo: str, pmpv: float):
        """Grava (ou substitui) o PMPV em R$/m³ para um período mensal."""
        self.cursor.execute("""
            INSERT OR REPLACE INTO pmpv_mensal (periodo, pmpv, data_atualizacao)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (periodo, pmpv))
        self.conn.commit()

    def buscar_pmpv_mensal(self, periodo: str):
        """Retorna o PMPV em R$/m³ para o período, ou None se não encontrado."""
        self.cursor.execute(
            "SELECT pmpv FROM pmpv_mensal WHERE periodo = ?", (periodo,)
        )
        row = self.cursor.fetchone()
        return float(row["pmpv"]) if row else None

    def listar_pmpv_mensal(self) -> List[Dict]:
        """Lista todos os PMPVs mensais salvos, do mais recente ao mais antigo."""
        self.cursor.execute(
            "SELECT periodo, pmpv, data_atualizacao FROM pmpv_mensal ORDER BY data_atualizacao DESC"
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def fechar(self):
        if self.conn: self.conn.close()