import sqlite3
from pathlib import Path
from typing import Dict, List


class DatabasePMPV:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            raiz_projeto = Path(__file__).resolve().parents[2]
            db_path = str(raiz_projeto / "pmpv_data.db")
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
            CREATE TABLE IF NOT EXISTS auditoria_itens (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo        TEXT NOT NULL,
                empresa        TEXT,
                tipo           TEXT,
                numero         TEXT,
                valor_total    REAL DEFAULT 0,
                icms           REAL DEFAULT 0,
                pis            REAL DEFAULT 0,
                cofins         REAL DEFAULT 0,
                volume_total   REAL DEFAULT 0,
                cgr_liquido    REAL DEFAULT 0,
                data_registro  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ret_itens (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo          TEXT NOT NULL,
                arquivo          TEXT,
                tipo_encargo     TEXT,
                empresa          TEXT,
                nota_tipo        TEXT,
                numero_nd        TEXT,
                data_vencimento  TEXT,
                valor_total      REAL DEFAULT 0,
                moeda            TEXT DEFAULT 'BRL',
                contrib_ec       TEXT,
                data_registro    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS concilia_itens (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo       TEXT NOT NULL,
                arquivo       TEXT,
                categoria     TEXT,
                valor         REAL DEFAULT 0,
                status        TEXT,
                metodo        TEXT,
                data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sr_resultados (
                periodo          TEXT PRIMARY KEY,
                vp               REAL DEFAULT 0,
                vf               REAL DEFAULT 0,
                pr               REAL DEFAULT 0,
                sr               REAL DEFAULT 0,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cgf_resumo (
                periodo                 TEXT PRIMARY KEY,
                volume_faturado         REAL DEFAULT 0,
                volume_canceladas       REAL DEFAULT 0,
                volume_devolucoes       REAL DEFAULT 0,
                volume_consumo_proprio  REAL DEFAULT 0,
                volume_final            REAL DEFAULT 0,
                data_atualizacao        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS excel_final_sessoes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                nome             TEXT NOT NULL,
                caminho_arquivo  TEXT NOT NULL,
                ativo            INTEGER DEFAULT 1,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def atualizar_campos_consolidacao(self, periodo: str, **campos: float):
        """Atualiza vários campos de consolidação em uma única operação."""
        campos_validos = {
            chave: valor
            for chave, valor in campos.items()
            if chave in {"cgr", "cgf", "ret", "rp", "rpv", "scg"}
        }
        if not campos_validos:
            return

        self._garantir_periodo(periodo)
        atribuicoes = ", ".join(f"{campo} = ?" for campo in campos_validos)
        valores = list(campos_validos.values())
        self.cursor.execute(f"""
            UPDATE consolidacao
            SET {atribuicoes}, data_atualizacao = CURRENT_TIMESTAMP
            WHERE periodo = ?
        """, (*valores, periodo))
        self.conn.commit()

    def salvar_rpv(self, periodo: str, rpv: float):
        self.atualizar_campos_consolidacao(periodo, rpv=rpv)

    def salvar_scg(self, periodo: str, scg: float):
        self.atualizar_campos_consolidacao(periodo, scg=scg)

    def calcular_e_salvar_rpv(self, periodo: str) -> float:
        """Compatibilidade legada: delega o cálculo oficial ao serviço."""
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        dados = self.buscar_consolidacao(periodo) or {}
        rpv = ServicosConsolidacao.calcular_rpv(
            dados.get("cgr") or 0.0,
            dados.get("cgf") or 0.0,
        )
        self.salvar_rpv(periodo, rpv)
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
        """Compatibilidade legada: delega o cálculo oficial ao serviço."""
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        dados = self.buscar_consolidacao(periodo)
        if not dados:
            return 0.0

        scg = ServicosConsolidacao.calcular_scg(
            dados.get("cgr") or 0.0,
            dados.get("cgf") or 0.0,
            dados.get("ret") or 0.0,
            dados.get("rp") or 0.0,
        )
        self.salvar_scg(periodo, scg)
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

    def listar_consolidacao_completa(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM consolidacao ORDER BY data_criacao DESC")
        return [dict(row) for row in self.cursor.fetchall()]

    def apagar_periodo(self, periodo: str):
        self.cursor.execute("DELETE FROM consolidacao WHERE periodo = ?", (periodo,))
        self.conn.commit()
        
        
        
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

    # ==========================================
    # AUDITORIA XML
    # ==========================================

    def salvar_auditoria_itens(self, periodo: str, itens: List[Dict]):
        """Apaga os itens existentes do período e salva a nova lista."""
        self.cursor.execute("DELETE FROM auditoria_itens WHERE periodo = ?", (periodo,))
        for it in itens:
            self.cursor.execute("""
                INSERT INTO auditoria_itens
                    (periodo, empresa, tipo, numero, valor_total, icms, pis, cofins, volume_total, cgr_liquido)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                periodo,
                it.get("empresa", ""),
                it.get("tipo", ""),
                it.get("numero", ""),
                it.get("valor_total", 0.0),
                it.get("icms", 0.0),
                it.get("pis", 0.0),
                it.get("cofins", 0.0),
                it.get("volume_total", 0.0),
                it.get("cgr_liquido", 0.0),
            ))
        self.conn.commit()

    def listar_auditoria_itens(self, periodo: str | None = None) -> List[Dict]:
        if periodo:
            self.cursor.execute(
                "SELECT * FROM auditoria_itens WHERE periodo = ? ORDER BY empresa, tipo", (periodo,)
            )
        else:
            self.cursor.execute(
                "SELECT * FROM auditoria_itens ORDER BY periodo DESC, empresa, tipo"
            )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_periodos_auditoria(self) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT periodo FROM auditoria_itens ORDER BY periodo DESC"
        )
        return [r[0] for r in self.cursor.fetchall()]

    # ==========================================
    # RET
    # ==========================================

    def salvar_ret_itens(self, periodo: str, itens: List[Dict]):
        """Apaga os itens existentes do período e salva a nova lista."""
        self.cursor.execute("DELETE FROM ret_itens WHERE periodo = ?", (periodo,))
        for it in itens:
            self.cursor.execute("""
                INSERT INTO ret_itens
                    (periodo, arquivo, tipo_encargo, empresa, nota_tipo, numero_nd,
                     data_vencimento, valor_total, moeda, contrib_ec)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                periodo,
                it.get("arquivo", ""),
                it.get("tipo_encargo", ""),
                it.get("empresa", ""),
                it.get("nota_tipo", ""),
                it.get("numero_nd", ""),
                it.get("data_vencimento", ""),
                it.get("valor_total", 0.0),
                it.get("moeda_detectada", "BRL"),
                it.get("contrib_ec", ""),
            ))
        self.conn.commit()

    def listar_ret_itens(self, periodo: str | None = None) -> List[Dict]:
        if periodo:
            self.cursor.execute(
                "SELECT * FROM ret_itens WHERE periodo = ? ORDER BY tipo_encargo, empresa", (periodo,)
            )
        else:
            self.cursor.execute(
                "SELECT * FROM ret_itens ORDER BY periodo DESC, tipo_encargo, empresa"
            )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_periodos_ret(self) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT periodo FROM ret_itens ORDER BY periodo DESC"
        )
        return [r[0] for r in self.cursor.fetchall()]

    # ==========================================
    # CONCILIAÇÃO RP
    # ==========================================

    def salvar_concilia_itens(self, periodo: str, itens: List[Dict]):
        """Apaga os itens existentes do período e salva a nova lista."""
        self.cursor.execute("DELETE FROM concilia_itens WHERE periodo = ?", (periodo,))
        for it in itens:
            self.cursor.execute("""
                INSERT INTO concilia_itens (periodo, arquivo, categoria, valor, status, metodo)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                periodo,
                it.get("arquivo", it.get("file_name", "")),
                it.get("categoria", it.get("category", "")),
                it.get("valor", it.get("amount", 0.0)),
                it.get("status", ""),
                it.get("metodo", it.get("method", "")),
            ))
        self.conn.commit()

    def listar_concilia_itens(self, periodo: str | None = None) -> List[Dict]:
        if periodo:
            self.cursor.execute(
                "SELECT * FROM concilia_itens WHERE periodo = ? ORDER BY categoria, arquivo", (periodo,)
            )
        else:
            self.cursor.execute(
                "SELECT * FROM concilia_itens ORDER BY periodo DESC, categoria, arquivo"
            )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_periodos_concilia(self) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT periodo FROM concilia_itens ORDER BY periodo DESC"
        )
        return [r[0] for r in self.cursor.fetchall()]

    # ==========================================
    # SR
    # ==========================================

    def salvar_sr(self, periodo: str, vp: float, vf: float, pr: float, sr: float):
        self.cursor.execute("""
            INSERT OR REPLACE INTO sr_resultados (periodo, vp, vf, pr, sr, data_atualizacao)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, vp, vf, pr, sr))
        self.conn.commit()

    def buscar_sr(self, periodo: str) -> Dict:
        self.cursor.execute("SELECT * FROM sr_resultados WHERE periodo = ?", (periodo,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def listar_sr(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM sr_resultados ORDER BY data_atualizacao DESC")
        return [dict(r) for r in self.cursor.fetchall()]

    # ==========================================
    # CGF RESUMO
    # ==========================================

    def salvar_cgf_resumo(self, periodo: str, volume_faturado: float, volume_canceladas: float,
                           volume_devolucoes: float, volume_consumo_proprio: float, volume_final: float):
        self.cursor.execute("""
            INSERT OR REPLACE INTO cgf_resumo
                (periodo, volume_faturado, volume_canceladas, volume_devolucoes,
                 volume_consumo_proprio, volume_final, data_atualizacao)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, volume_faturado, volume_canceladas, volume_devolucoes,
              volume_consumo_proprio, volume_final))
        self.conn.commit()

    def buscar_cgf_resumo(self, periodo: str) -> Dict:
        self.cursor.execute("SELECT * FROM cgf_resumo WHERE periodo = ?", (periodo,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def listar_cgf_resumos(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM cgf_resumo ORDER BY data_atualizacao DESC")
        return [dict(r) for r in self.cursor.fetchall()]

    def salvar_sessao_excel_final(self, nome: str, caminho_arquivo: str, ativo: bool = True) -> int:
        if ativo:
            self.cursor.execute("UPDATE excel_final_sessoes SET ativo = 0")
        self.cursor.execute(
            """
            INSERT INTO excel_final_sessoes (nome, caminho_arquivo, ativo, data_atualizacao)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (nome, caminho_arquivo, 1 if ativo else 0),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def buscar_sessao_excel_final_ativa(self) -> Dict | None:
        self.cursor.execute(
            "SELECT * FROM excel_final_sessoes WHERE ativo = 1 ORDER BY data_atualizacao DESC LIMIT 1"
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    # ==========================================
    # SESSÕES COM VOLUMES (PMPV)
    # ==========================================

    def listar_sessoes_com_volumes(self) -> List[Dict]:
        """
        Lista todas as sessões salvas com seus respectivos VP e VF.

        - VP = soma de 'volume' (m³/dia) de todos os registros de dados_mes da sessão.
        - VF = volume_total gravado em resultados (vol × dias de cada empresa).
        """
        self.cursor.execute("""
            SELECT
                s.id,
                s.nome,
                strftime('%d/%m/%Y %H:%M', s.data_criacao) AS data_criacao,
                COALESCE((
                    SELECT r2.volume_total
                    FROM resultados r2
                    WHERE r2.sessao_id = s.id
                    ORDER BY r2.id DESC
                    LIMIT 1
                ), 0.0) AS vf,
                COALESCE((
                    SELECT SUM(dm.volume)
                    FROM dados_mes dm
                    WHERE dm.sessao_id = s.id
                ), 0.0) AS vp
            FROM sessoes s
            ORDER BY s.data_criacao DESC
        """)
        return [dict(row) for row in self.cursor.fetchall()]

    def fechar(self):
        if self.conn: self.conn.close()