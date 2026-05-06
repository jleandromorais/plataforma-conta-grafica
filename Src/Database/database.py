import sqlite3
from pathlib import Path
from typing import Dict, List

from Src.common.periodos import normalizar_periodo, variantes_periodo


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
                vp_total REAL,
                vf_total REAL,
                custo_total REAL,
                pmpv_trimestral REAL,
                conta_grafica REAL,    -- Novo Campo
                preco_final REAL,      -- Novo Campo
                data_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sessao_id) REFERENCES sessoes (id) ON DELETE CASCADE
            )
        """)
        self._garantir_coluna("resultados", "vp_total", "REAL")
        self._garantir_coluna("resultados", "vf_total", "REAL")
        
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
            CREATE TABLE IF NOT EXISTS sr_trimestre (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                trimestre        TEXT NOT NULL,
                mes              TEXT NOT NULL,
                vp               REAL DEFAULT 0,
                vf               REAL DEFAULT 0,
                pr               REAL DEFAULT 0,
                selic_mensal     REAL DEFAULT 0,
                diferenca        REAL DEFAULT 0,
                sr_parcela       REAL DEFAULT 0,
                sr_selic         REAL DEFAULT 0,
                sr_anterior      REAL DEFAULT 0,
                total            REAL DEFAULT 0,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(trimestre, mes)
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
            CREATE TABLE IF NOT EXISTS pr_resultados (
                periodo          TEXT PRIMARY KEY,
                scg              REAL DEFAULT 0,
                sr               REAL DEFAULT 0,
                vp               REAL DEFAULT 0,
                pr               REAL DEFAULT 0,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS pv_resultados (
                periodo          TEXT PRIMARY KEY,
                pmpv             REAL DEFAULT 0,
                pr               REAL DEFAULT 0,
                pv               REAL DEFAULT 0,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            CREATE TABLE IF NOT EXISTS excel_final_execucoes (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_sessao      TEXT NOT NULL,
                periodo          TEXT NOT NULL,
                etapa            TEXT NOT NULL,
                execucao         INTEGER NOT NULL DEFAULT 1,
                caminho_arquivo  TEXT NOT NULL,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nome_sessao, periodo, etapa)
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
        # Tabela de configuração geral (chave-valor)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def salvar_trimestre_ativo(self, meses: list[str]) -> None:
        """Salva os 3 meses do trimestre activo (ex: ['Fev/26','Mar/26','Abr/26'])."""
        valor = ",".join(m.strip() for m in meses if m.strip())
        self.cursor.execute("""
            INSERT INTO config (chave, valor, data_atualizacao)
            VALUES ('trimestre_ativo', ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chave) DO UPDATE SET
                valor = excluded.valor,
                data_atualizacao = CURRENT_TIMESTAMP
        """, (valor,))
        self.conn.commit()

    def buscar_trimestre_ativo(self) -> list[str]:
        """Retorna os meses do trimestre activo ou lista vazia se não definido."""
        self.cursor.execute("SELECT valor FROM config WHERE chave = 'trimestre_ativo'")
        row = self.cursor.fetchone()
        if row and row[0]:
            return [m.strip() for m in row[0].split(",") if m.strip()]
        return []

    def buscar_periodos_ret_para_trimestre(self, periodo_alvo: str) -> list[str]:
        """
        Busca em ret_itens os até 3 períodos mensais mais recentes que sejam
        cronologicamente <= periodo_alvo.

        Ordena cronologicamente (ano × 12 + mes) para evitar ordem alfabética
        errada (Fev < Jan na ordem de letras).
        """
        _MESES = {"Jan":1,"Fev":2,"Mar":3,"Abr":4,"Mai":5,"Jun":6,
                  "Jul":7,"Ago":8,"Set":9,"Out":10,"Nov":11,"Dez":12}

        def _para_int(p: str) -> int:
            """'Jan/2026' → 2026*12+1 para comparação cronológica."""
            try:
                abrev, ano = p.strip().split("/")
                return int(ano) * 12 + _MESES.get(abrev.strip().capitalize(), 0)
            except Exception:
                return 0

        _ABREVS = {"Jan","Fev","Mar","Abr","Mai","Jun",
                   "Jul","Ago","Set","Out","Nov","Dez"}

        def _valido(p: str) -> bool:
            parts = (p or "").strip().split("/")
            if len(parts) != 2:
                return False
            ab, an = parts[0].strip().capitalize()[:3], parts[1].strip()
            return ab in _ABREVS and len(an) == 4 and an.isdigit()

        self.cursor.execute("SELECT DISTINCT periodo FROM ret_itens")
        todos = [row[0] for row in self.cursor.fetchall() if row[0] and _valido(row[0])]
        if not todos:
            return []

        alvo_int = _para_int(periodo_alvo)
        anteriores = sorted(
            [p for p in todos if _para_int(p) <= alvo_int],
            key=_para_int
        )
        return anteriores[-3:]

    def _garantir_coluna(self, tabela: str, coluna: str, definicao_sql: str):
        self.cursor.execute(f"PRAGMA table_info({tabela})")
        colunas = {row[1] for row in self.cursor.fetchall()}
        if coluna not in colunas:
            self.cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao_sql}")

    @staticmethod
    def _normalizar_periodo(periodo: str | None) -> str:
        return normalizar_periodo(periodo)

    @staticmethod
    def _variantes_periodo(periodo: str | None) -> tuple[str, ...]:
        return variantes_periodo(periodo)

    def _buscar_por_periodo(self, tabela: str, periodo: str | None, order_by: str = "data_atualizacao DESC, rowid DESC") -> List[Dict]:
        variantes = self._variantes_periodo(periodo)
        if not variantes:
            return []
        placeholders = ", ".join("?" for _ in variantes)
        self.cursor.execute(
            f"SELECT * FROM {tabela} WHERE periodo IN ({placeholders}) ORDER BY {order_by}",
            variantes,
        )
        return [dict(row) for row in self.cursor.fetchall()]

    def _primeiro_por_periodo(self, tabela: str, periodo: str | None, order_by: str = "data_atualizacao DESC, rowid DESC") -> Dict | None:
        linhas = self._buscar_por_periodo(tabela, periodo, order_by=order_by)
        return linhas[0] if linhas else None

    def _merge_registros_periodo(self, registros: List[Dict], periodo: str | None, campos_numericos: tuple[str, ...]) -> Dict | None:
        if not registros:
            return None

        base = dict(registros[0])
        periodo_normalizado = self._normalizar_periodo(periodo or base.get("periodo"))
        if periodo_normalizado:
            base["periodo"] = periodo_normalizado

        for registro in registros[1:]:
            for campo in campos_numericos:
                atual = base.get(campo)
                novo = registro.get(campo)
                if atual in (None, 0, 0.0) and novo not in (None, 0, 0.0):
                    base[campo] = novo
            if (registro.get("data_atualizacao") or "") > (base.get("data_atualizacao") or ""):
                base["data_atualizacao"] = registro.get("data_atualizacao")
        return base

    def _deduplicar_periodos(self, registros: List[Dict], campos_numericos: tuple[str, ...] = ()) -> List[Dict]:
        agrupados: dict[str, List[Dict]] = {}
        ordem: list[str] = []
        for registro in registros:
            chave = self._normalizar_periodo(registro.get("periodo")) or str(registro.get("periodo") or "").strip()
            if chave not in agrupados:
                agrupados[chave] = []
                ordem.append(chave)
            agrupados[chave].append(registro)

        resultado: list[Dict] = []
        for chave in ordem:
            if campos_numericos:
                mesclado = self._merge_registros_periodo(agrupados[chave], chave, campos_numericos)
            else:
                mesclado = dict(agrupados[chave][0])
                mesclado["periodo"] = chave
            if mesclado:
                resultado.append(mesclado)
        return resultado
    
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

    def salvar_resultado(self, sessao_id: int, vol_tot: float, vp_tot: float, vf_tot: float, custo_tot: float,
                        pmpv: float, cg: float, final: float) -> bool:
        try:
            self.cursor.execute("""
                INSERT INTO resultados (
                    sessao_id, volume_total, vp_total, vf_total, custo_total,
                    pmpv_trimestral, conta_grafica, preco_final
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (sessao_id, vol_tot, vp_tot, vf_tot, custo_tot, pmpv, cg, final))
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
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute(
            "SELECT id FROM consolidacao WHERE periodo IN ({}) LIMIT 1".format(", ".join("?" for _ in self._variantes_periodo(periodo))),
            self._variantes_periodo(periodo),
        )
        if not self.cursor.fetchone():
            self.criar_periodo_consolidacao(periodo)

    def criar_periodo_consolidacao(self, periodo: str, obs: str = "") -> int:
        """Cria o período na consolidação se ainda não existir (idempotente)."""
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute(
            "INSERT OR IGNORE INTO consolidacao (periodo, observacoes) VALUES (?, ?)",
            (periodo, obs),
        )
        self.conn.commit()
        self.cursor.execute("SELECT id FROM consolidacao WHERE periodo = ?", (periodo,))
        return self.cursor.fetchone()[0]
    
    def _update_consolidacao(self, periodo: str, **campos):
        """
        UPDATE seguro: usa IN (variantes) para encontrar a linha
        independente do formato salvo ("Jan/26" ou "Jan/2026").
        """
        atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
        valores = list(campos.values())
        variantes = self._variantes_periodo(periodo)
        placeholders = ", ".join("?" for _ in variantes)
        self.cursor.execute(
            f"UPDATE consolidacao SET {atribuicoes}, data_atualizacao = CURRENT_TIMESTAMP "
            f"WHERE periodo IN ({placeholders})",
            (*valores, *variantes),
        )
        self.conn.commit()

    def atualizar_cgr(self, periodo: str, valor: float):
        """Atualiza o CGR (Auditoria XML)."""
        periodo = self._normalizar_periodo(periodo)
        self._garantir_periodo(periodo)
        self._update_consolidacao(periodo, cgr=valor)

    def atualizar_ret(self, periodo: str, valor: float):
        """Atualiza o RET (Módulo RET)."""
        periodo = self._normalizar_periodo(periodo)
        self._garantir_periodo(periodo)
        self._update_consolidacao(periodo, ret=valor)

    def atualizar_rp(self, periodo: str, valor: float):
        """Atualiza o RP (Conciliação)."""
        periodo = self._normalizar_periodo(periodo)
        self._garantir_periodo(periodo)
        self._update_consolidacao(periodo, rp=valor)

    def atualizar_cgf(self, periodo: str, valor: float):
        """Atualiza somente o CGF (Volume Faturado)."""
        periodo = self._normalizar_periodo(periodo)
        self._garantir_periodo(periodo)
        self._update_consolidacao(periodo, cgf=valor)

    def atualizar_campos_consolidacao(self, periodo: str, **campos: float):
        """Atualiza vários campos de consolidação em uma única operação."""
        periodo = self._normalizar_periodo(periodo)
        campos_validos = {
            chave: valor
            for chave, valor in campos.items()
            if chave in {"cgr", "cgf", "ret", "rp", "rpv", "scg"}
        }
        if not campos_validos:
            return
        self._garantir_periodo(periodo)
        self._update_consolidacao(periodo, **campos_validos)

    def salvar_rpv(self, periodo: str, rpv: float):
        self.atualizar_campos_consolidacao(periodo, rpv=rpv)

    def salvar_scg(self, periodo: str, scg: float):
        self.atualizar_campos_consolidacao(periodo, scg=scg)

    def calcular_e_salvar_rpv(self, periodo: str) -> float:
        """Compatibilidade legada: delega o cálculo oficial ao serviço."""
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        periodo = self._normalizar_periodo(periodo)
        dados = self.buscar_consolidacao(periodo) or {}
        rpv = ServicosConsolidacao.calcular_rpv(
            dados.get("cgr") or 0.0,
            dados.get("cgf") or 0.0,
        )
        self.salvar_rpv(periodo, rpv)
        return rpv

    def atualizar_rpv_cgf(self, periodo: str, rpv: float, cgf: float):
        """Atualiza RPV e CGF (valores manuais)."""
        periodo = self._normalizar_periodo(periodo)
        self._garantir_periodo(periodo)
        self._update_consolidacao(periodo, rpv=rpv, cgf=cgf)
        
    def calcular_scg(self, periodo: str) -> float:
        """Compatibilidade legada: delega o cálculo oficial ao serviço."""
        from Src.Services.servicos_consolidacao import ServicosConsolidacao

        periodo = self._normalizar_periodo(periodo)
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
        registros = self._buscar_por_periodo("consolidacao", periodo, order_by="data_atualizacao DESC, id DESC")
        return self._merge_registros_periodo(registros, periodo, ("cgr", "ret", "rp", "rpv", "cgf", "scg"))
    
    def listar_periodos(self) -> List:
        """Lista todos os períodos conhecidos em qualquer tabela do banco."""
        self.cursor.execute("""
            SELECT periodo FROM consolidacao
            UNION
            SELECT DISTINCT periodo FROM auditoria_itens
            UNION
            SELECT DISTINCT periodo FROM ret_itens
            UNION
            SELECT DISTINCT periodo FROM concilia_itens
            UNION
            SELECT periodo FROM cgf_resumo
            UNION
            SELECT periodo FROM pmpv_mensal
            UNION
            SELECT periodo FROM sr_resultados
            UNION
            SELECT periodo FROM pr_resultados
            UNION
            SELECT periodo FROM pv_resultados
            ORDER BY periodo DESC
        """)
        raw = [{"periodo": row[0]} for row in self.cursor.fetchall() if row[0]]
        return self._deduplicar_periodos(raw, ())

    def listar_consolidacao_completa(self, periodo: str | None = None) -> List[Dict]:
        if periodo:
            variantes = self._variantes_periodo(periodo)
            placeholders = ", ".join("?" for _ in variantes)
            self.cursor.execute(
                f"SELECT * FROM consolidacao WHERE periodo IN ({placeholders}) ORDER BY data_criacao DESC",
                variantes,
            )
        else:
            self.cursor.execute("SELECT * FROM consolidacao ORDER BY data_criacao DESC")
        return self._deduplicar_periodos([dict(row) for row in self.cursor.fetchall()], ("cgr", "ret", "rp", "rpv", "cgf", "scg"))

    def apagar_periodo(self, periodo: str):
        variantes = self._variantes_periodo(periodo)
        placeholders = ", ".join("?" for _ in variantes)
        self.cursor.execute(f"DELETE FROM consolidacao WHERE periodo IN ({placeholders})", variantes)
        self.conn.commit()

    def apagar_periodo_completo(self, periodo: str) -> Dict[str, int]:
        variantes = self._variantes_periodo(periodo)
        if not variantes:
            return {}

        placeholders = ", ".join("?" for _ in variantes)
        tabelas = (
            "consolidacao",
            "pmpv_mensal",
            "sr_resultados",
            "pr_resultados",
            "pv_resultados",
            "cgf_resumo",
            "auditoria_itens",
            "ret_itens",
            "concilia_itens",
            "excel_final_execucoes",
        )

        removidos: Dict[str, int] = {}
        for tabela in tabelas:
            self.cursor.execute(f"DELETE FROM {tabela} WHERE periodo IN ({placeholders})", variantes)
            removidos[tabela] = int(self.cursor.rowcount or 0)

        self.conn.commit()
        return removidos
        
        
        
    # ==========================================
    # PMPV MENSAL
    # ==========================================

    def salvar_pmpv_mensal(self, periodo: str, pmpv: float):
        """Grava (ou substitui) o PMPV em R$/m³ para um período mensal."""
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute("""
            INSERT OR REPLACE INTO pmpv_mensal (periodo, pmpv, data_atualizacao)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        """, (periodo, pmpv))
        self.conn.commit()

    def buscar_pmpv_mensal(self, periodo: str):
        """Retorna o PMPV em R$/m³ para o período, ou None se não encontrado."""
        row = self._primeiro_por_periodo("pmpv_mensal", periodo)
        return float(row["pmpv"]) if row else None

    def listar_pmpv_mensal(self) -> List[Dict]:
        """Lista todos os PMPVs mensais salvos, do mais recente ao mais antigo."""
        self.cursor.execute(
            "SELECT periodo, pmpv, data_atualizacao FROM pmpv_mensal ORDER BY data_atualizacao DESC"
        )
        return self._deduplicar_periodos([dict(r) for r in self.cursor.fetchall()], ("pmpv",))

    def salvar_vp_mensal(self, periodo: str, vp: float):
        """Salva/atualiza apenas o Volume Prospectivo em sr_resultados para um período."""
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute(
            """INSERT INTO sr_resultados (periodo, vp)
               VALUES (?, ?)
               ON CONFLICT(periodo) DO UPDATE SET vp = excluded.vp,
                   data_atualizacao = CURRENT_TIMESTAMP""",
            (periodo, vp),
        )
        self.conn.commit()

    # ==========================================
    # AUDITORIA XML
    # ==========================================

    def salvar_auditoria_itens(self, periodo: str, itens: List[Dict]):
        """Apaga os itens existentes do período e salva a nova lista."""
        periodo = self._normalizar_periodo(periodo)
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
            registros = self._buscar_por_periodo("auditoria_itens", periodo, order_by="empresa, tipo, id DESC")
            return registros
        else:
            self.cursor.execute(
                "SELECT * FROM auditoria_itens ORDER BY periodo DESC, empresa, tipo"
            )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_periodos_auditoria(self) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT periodo FROM auditoria_itens ORDER BY periodo DESC"
        )
        vistos = []
        for row in self.cursor.fetchall():
            periodo = self._normalizar_periodo(row[0])
            if periodo and periodo not in vistos:
                vistos.append(periodo)
        return vistos

    # ==========================================
    # RET
    # ==========================================

    def salvar_ret_itens(self, periodo: str, itens: List[Dict]):
        """Apaga os itens existentes do período e salva a nova lista."""
        periodo = self._normalizar_periodo(periodo)
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
            registros = self._buscar_por_periodo("ret_itens", periodo, order_by="tipo_encargo, empresa, id DESC")
            return registros
        else:
            self.cursor.execute(
                "SELECT * FROM ret_itens ORDER BY periodo DESC, tipo_encargo, empresa"
            )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_periodos_ret(self) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT periodo FROM ret_itens ORDER BY periodo DESC"
        )
        vistos = []
        for row in self.cursor.fetchall():
            periodo = self._normalizar_periodo(row[0])
            if periodo and periodo not in vistos:
                vistos.append(periodo)
        return vistos

    # ==========================================
    # CONCILIAÇÃO RP
    # ==========================================

    def salvar_concilia_itens(self, periodo: str, itens: List[Dict]):
        """Apaga os itens existentes do período e salva a nova lista."""
        periodo = self._normalizar_periodo(periodo)
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
            registros = self._buscar_por_periodo("concilia_itens", periodo, order_by="categoria, arquivo, id DESC")
            return registros
        else:
            self.cursor.execute(
                "SELECT * FROM concilia_itens ORDER BY periodo DESC, categoria, arquivo"
            )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_periodos_concilia(self) -> List[str]:
        self.cursor.execute(
            "SELECT DISTINCT periodo FROM concilia_itens ORDER BY periodo DESC"
        )
        vistos = []
        for row in self.cursor.fetchall():
            periodo = self._normalizar_periodo(row[0])
            if periodo and periodo not in vistos:
                vistos.append(periodo)
        return vistos

    # ==========================================
    # SR
    # ==========================================

    def salvar_sr(self, periodo: str, vp: float, vf: float, pr: float, sr: float):
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute("""
            INSERT OR REPLACE INTO sr_resultados (periodo, vp, vf, pr, sr, data_atualizacao)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, vp, vf, pr, sr))
        self.conn.commit()

    def salvar_sr_trimestre(self, trimestre: str, meses: list[dict]):
        """Salva os dados mensais do SR trimestral.
        Cada dict em meses deve ter: mes, vp, vf, pr, selic_mensal,
        diferenca, sr_parcela, sr_selic, sr_anterior, total.
        """
        for m in meses:
            self.cursor.execute("""
                INSERT INTO sr_trimestre
                    (trimestre, mes, vp, vf, pr, selic_mensal,
                     diferenca, sr_parcela, sr_selic, sr_anterior, total,
                     data_atualizacao)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(trimestre, mes) DO UPDATE SET
                    vp=excluded.vp, vf=excluded.vf, pr=excluded.pr,
                    selic_mensal=excluded.selic_mensal,
                    diferenca=excluded.diferenca,
                    sr_parcela=excluded.sr_parcela,
                    sr_selic=excluded.sr_selic,
                    sr_anterior=excluded.sr_anterior,
                    total=excluded.total,
                    data_atualizacao=CURRENT_TIMESTAMP
            """, (
                trimestre, m["mes"],
                m.get("vp", 0), m.get("vf", 0), m.get("pr", 0),
                m.get("selic_mensal", 0), m.get("diferenca", 0),
                m.get("sr_parcela", 0), m.get("sr_selic", 0),
                m.get("sr_anterior", 0), m.get("total", 0),
            ))
        self.conn.commit()

    def buscar_sr_trimestre(self, trimestre: str) -> list[dict]:
        self.cursor.execute(
            "SELECT * FROM sr_trimestre WHERE trimestre=? ORDER BY id",
            (trimestre,)
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def listar_sr_trimestres(self) -> list[str]:
        self.cursor.execute(
            "SELECT DISTINCT trimestre FROM sr_trimestre ORDER BY trimestre DESC"
        )
        return [r[0] for r in self.cursor.fetchall()]

    def buscar_sr(self, periodo: str) -> Dict:
        return self._primeiro_por_periodo("sr_resultados", periodo)

    def listar_sr(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM sr_resultados ORDER BY data_atualizacao DESC")
        return self._deduplicar_periodos([dict(r) for r in self.cursor.fetchall()], ("vp", "vf", "pr", "sr"))

    # ==========================================
    # PR (PREÇO REGULATÓRIO FINAL)
    # ==========================================

    def salvar_pr(self, periodo: str, scg: float, sr: float, vp: float, pr: float):
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute("""
            INSERT OR REPLACE INTO pr_resultados (periodo, scg, sr, vp, pr, data_atualizacao)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, scg, sr, vp, pr))
        self.conn.commit()

    def buscar_pr(self, periodo: str) -> Dict:
        return self._primeiro_por_periodo("pr_resultados", periodo)

    def listar_pr(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM pr_resultados ORDER BY data_atualizacao DESC")
        return self._deduplicar_periodos([dict(r) for r in self.cursor.fetchall()], ("scg", "sr", "vp", "pr"))

    # ==========================================
    # PV (PREÇO FINAL = PMPV + PR)
    # ==========================================

    def salvar_pv(self, periodo: str, pmpv: float, pr: float, pv: float):
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute("""
            INSERT OR REPLACE INTO pv_resultados (periodo, pmpv, pr, pv, data_atualizacao)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, pmpv, pr, pv))
        self.conn.commit()

    def buscar_pv(self, periodo: str) -> Dict:
        return self._primeiro_por_periodo("pv_resultados", periodo)

    def listar_pv(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM pv_resultados ORDER BY data_atualizacao DESC")
        return self._deduplicar_periodos([dict(r) for r in self.cursor.fetchall()], ("pmpv", "pr", "pv"))

    # ==========================================
    # CGF RESUMO
    # ==========================================

    def salvar_cgf_resumo(self, periodo: str, volume_faturado: float, volume_canceladas: float,
                           volume_devolucoes: float, volume_consumo_proprio: float, volume_final: float):
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute("""
            INSERT OR REPLACE INTO cgf_resumo
                (periodo, volume_faturado, volume_canceladas, volume_devolucoes,
                 volume_consumo_proprio, volume_final, data_atualizacao)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (periodo, volume_faturado, volume_canceladas, volume_devolucoes,
              volume_consumo_proprio, volume_final))
        self.conn.commit()

    def buscar_cgf_resumo(self, periodo: str) -> Dict:
        return self._primeiro_por_periodo("cgf_resumo", periodo)

    def listar_cgf_resumos(self) -> List[Dict]:
        self.cursor.execute("SELECT * FROM cgf_resumo ORDER BY data_atualizacao DESC")
        return self._deduplicar_periodos([dict(r) for r in self.cursor.fetchall()], (
            "volume_faturado",
            "volume_canceladas",
            "volume_devolucoes",
            "volume_consumo_proprio",
            "volume_final",
        ))

    def salvar_sessao_excel_final(self, nome: str, caminho_arquivo: str, ativo: bool = True) -> int:
        self.cursor.execute(
            "SELECT id FROM excel_final_sessoes WHERE nome = ? ORDER BY data_atualizacao DESC LIMIT 1",
            (nome,),
        )
        row = self.cursor.fetchone()
        if ativo:
            self.cursor.execute("UPDATE excel_final_sessoes SET ativo = 0")

        if row:
            self.cursor.execute(
                """
                UPDATE excel_final_sessoes
                SET caminho_arquivo = ?, ativo = ?, data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (caminho_arquivo, 1 if ativo else 0, row[0]),
            )
            sessao_id = row[0]
        else:
            self.cursor.execute(
                """
                INSERT INTO excel_final_sessoes (nome, caminho_arquivo, ativo, data_atualizacao)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (nome, caminho_arquivo, 1 if ativo else 0),
            )
            sessao_id = self.cursor.lastrowid
        self.conn.commit()
        return sessao_id

    def buscar_sessao_excel_final_por_nome(self, nome: str) -> Dict | None:
        self.cursor.execute(
            "SELECT * FROM excel_final_sessoes WHERE nome = ? ORDER BY data_atualizacao DESC LIMIT 1",
            (nome,),
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def buscar_sessao_excel_final_ativa(self) -> Dict | None:
        self.cursor.execute(
            "SELECT * FROM excel_final_sessoes WHERE ativo = 1 ORDER BY data_atualizacao DESC LIMIT 1"
        )
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def listar_sessoes_excel_final(self) -> List[Dict]:
        self.cursor.execute(
            """
            SELECT *
            FROM excel_final_sessoes
            ORDER BY ativo DESC, data_atualizacao DESC
            """
        )
        return [dict(r) for r in self.cursor.fetchall()]

    def desativar_sessao_excel_final_ativa(self):
        self.cursor.execute("UPDATE excel_final_sessoes SET ativo = 0 WHERE ativo = 1")
        self.conn.commit()

    def zerar_sessao_excel_final(self, nome_sessao_fixa: str, caminho_fixo: str):
        """Limpa execuções da sessão fixa e a reativa zerada, pronta para novo ciclo."""
        self.cursor.execute("UPDATE excel_final_sessoes SET ativo = 0")
        self.cursor.execute(
            "DELETE FROM excel_final_execucoes WHERE nome_sessao = ?",
            (nome_sessao_fixa,),
        )
        self.cursor.execute(
            "SELECT id FROM excel_final_sessoes WHERE nome = ?",
            (nome_sessao_fixa,),
        )
        row = self.cursor.fetchone()
        if row:
            self.cursor.execute(
                "UPDATE excel_final_sessoes SET caminho_arquivo = ?, ativo = 1, data_atualizacao = CURRENT_TIMESTAMP WHERE id = ?",
                (caminho_fixo, row[0]),
            )
        else:
            self.cursor.execute(
                "INSERT INTO excel_final_sessoes (nome, caminho_arquivo, ativo, data_atualizacao) VALUES (?, ?, 1, CURRENT_TIMESTAMP)",
                (nome_sessao_fixa, caminho_fixo),
            )
        self.conn.commit()

    def registrar_execucao_excel_final(
        self,
        nome_sessao: str,
        periodo: str,
        etapa: str,
        caminho_arquivo: str,
    ) -> int:
        """
        Registra execução por etapa no Excel final cumulativo.

        Chave lógica: nome_sessao + periodo + etapa
        - Se já existir, incrementa o contador `execucao` e atualiza timestamp/caminho.
        - Se não existir, cria com `execucao = 1`.
        """
        periodo = self._normalizar_periodo(periodo)
        self.cursor.execute(
            """
            SELECT id, execucao
            FROM excel_final_execucoes
            WHERE nome_sessao = ? AND periodo = ? AND etapa = ?
            LIMIT 1
            """,
            (nome_sessao, periodo, etapa),
        )
        row = self.cursor.fetchone()

        if row:
            novo_valor = int(row["execucao"] or 0) + 1
            self.cursor.execute(
                """
                UPDATE excel_final_execucoes
                SET execucao = ?, caminho_arquivo = ?, data_atualizacao = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (novo_valor, caminho_arquivo, row["id"]),
            )
            self.conn.commit()
            return novo_valor

        self.cursor.execute(
            """
            INSERT INTO excel_final_execucoes
                (nome_sessao, periodo, etapa, execucao, caminho_arquivo, data_atualizacao)
            VALUES (?, ?, ?, 1, ?, CURRENT_TIMESTAMP)
            """,
            (nome_sessao, periodo, etapa, caminho_arquivo),
        )
        self.conn.commit()
        return 1

    def listar_execucoes_excel_final(self, nome_sessao: str | None = None, periodo: str | None = None) -> List[Dict]:
        if periodo:
            variantes = self._variantes_periodo(periodo)
            placeholders = ", ".join("?" for _ in variantes)
        if nome_sessao and periodo:
            self.cursor.execute(
                """
                SELECT *
                FROM excel_final_execucoes
                WHERE nome_sessao = ? AND periodo IN ({})
                ORDER BY data_atualizacao DESC, etapa
                """.format(placeholders),
                (nome_sessao, *variantes),
            )
        elif nome_sessao:
            self.cursor.execute(
                """
                SELECT *
                FROM excel_final_execucoes
                WHERE nome_sessao = ?
                ORDER BY data_atualizacao DESC, periodo, etapa
                """,
                (nome_sessao,),
            )
        elif periodo:
            self.cursor.execute(
                """
                SELECT *
                FROM excel_final_execucoes
                WHERE periodo IN ({})
                ORDER BY data_atualizacao DESC, nome_sessao, etapa
                """.format(placeholders),
                variantes,
            )
        else:
            self.cursor.execute(
                """
                SELECT *
                FROM excel_final_execucoes
                ORDER BY data_atualizacao DESC, nome_sessao, periodo, etapa
                """
            )
        return [dict(r) for r in self.cursor.fetchall()]

    # ==========================================
    # SESSÕES COM VOLUMES (PMPV)
    # ==========================================

    def listar_sessoes_com_volumes(self, periodo: str | None = None) -> List[Dict]:
        """
        Lista sessões salvas com seus respectivos VP e VF.

        Se `periodo` for fornecido, retorna apenas a sessão mais recente cujo
        nome contenha o período (ex: 'PMPV_Mai_Jul_2025') OU a sessão mais
        recente salva no dia do período — evitando sessões de teste antigas.
        Quando `periodo` é None, retorna todas as sessões.

        - VP = soma de 'volume' informado em dados_mes.
        - VF = volume faturado real do trimestre.
        """
        base_query = """
            SELECT
                s.id,
                s.nome,
                strftime('%d/%m/%Y %H:%M', s.data_criacao) AS data_criacao,
                COALESCE(r.vf_total, (
                    SELECT SUM(dm.volume)
                    FROM dados_mes dm
                    WHERE dm.sessao_id = s.id
                ), 0.0) AS vf,
                COALESCE(r.vp_total, (
                    SELECT SUM(dm2.volume)
                    FROM dados_mes dm2
                    WHERE dm2.sessao_id = s.id
                ), 0.0) AS vp
            FROM sessoes s
            LEFT JOIN (
                SELECT r1.*
                FROM resultados r1
                INNER JOIN (
                    SELECT sessao_id, MAX(id) AS max_id
                    FROM resultados
                    GROUP BY sessao_id
                ) ult ON ult.max_id = r1.id
            ) r ON r.sessao_id = s.id
        """
        if periodo:
            # Retorna apenas a sessão mais recente (a que acabou de ser salva)
            self.cursor.execute(base_query + " ORDER BY s.data_criacao DESC LIMIT 1")
        else:
            self.cursor.execute(base_query + " ORDER BY s.data_criacao DESC")
        return [dict(row) for row in self.cursor.fetchall()]

    def fechar(self):
        if self.conn: self.conn.close()