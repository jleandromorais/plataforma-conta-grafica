"""
Detector de Anomalias - Plataforma Conta Gráfica

Monitora 5 tipos de anomalias:
1. Data Quality Failures (últimas 24h)
2. Atraso de Importação > 3 dias
3. Volume CGF zerado ou NULL
4. Período duplicado
5. Taxa anormal de rejeição

Retorna lista de dicionários com alertas estruturados.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detector de anomalias em dados da Plataforma CGF"""

    def __init__(self, db_connection):
        """
        Inicializa detector com conexão PostgreSQL
        
        Args:
            db_connection: conexão sqlalchemy.create_engine()
        """
        self.db = db_connection
        self.alerts = []

    def detect_all(self) -> List[Dict[str, Any]]:
        """
        Executa todos os detectores de anomalia
        
        Returns:
            Lista de alertas encontrados (vazio se nenhum)
        """
        self.alerts = []
        
        try:
            self._detect_data_quality_failures()
            logger.info(f"✓ Data Quality Failures verificado")
        except Exception as e:
            logger.error(f"✗ Erro em data_quality_failures: {e}")

        try:
            self._detect_import_delay()
            logger.info(f"✓ Import Delay verificado")
        except Exception as e:
            logger.error(f"✗ Erro em import_delay: {e}")

        try:
            self._detect_zero_volume()
            logger.info(f"✓ Zero Volume verificado")
        except Exception as e:
            logger.error(f"✗ Erro em zero_volume: {e}")

        try:
            self._detect_duplicate_period()
            logger.info(f"✓ Duplicate Period verificado")
        except Exception as e:
            logger.error(f"✗ Erro em duplicate_period: {e}")

        try:
            self._detect_abnormal_rejection_rate()
            logger.info(f"✓ Abnormal Rejection Rate verificado")
        except Exception as e:
            logger.error(f"✗ Erro em rejection_rate: {e}")

        return self.alerts

    def _detect_data_quality_failures(self):
        """Detecta falhas de qualidade de dados nas últimas 24h via marts.data_quality_results."""
        query = """
        SELECT
            check_name,
            COUNT(*) AS failure_count,
            MAX(run_ts) AS last_failure,
            STRING_AGG(DISTINCT dag_id, '; ')::TEXT AS dag_ids
        FROM marts.data_quality_results
        WHERE
            status = 'FAIL'
            AND run_ts >= NOW() - INTERVAL '24 hours'
        GROUP BY check_name
        ORDER BY failure_count DESC
        """
        try:
            result = self.db.execute(query).fetchall()
            for row in result:
                alert = {
                    'type': 'DATA_QUALITY_FAILURE',
                    'severity': 'CRITICAL',
                    'timestamp': datetime.now().isoformat(),
                    'check_name': row[0],
                    'failure_count': row[1],
                    'last_failure': row[2].isoformat() if row[2] else None,
                    'error_details': row[3],
                    'message': f"Falha de qualidade em '{row[0]}': {row[1]} ocorrência(s) em 24h",
                    'action': "Revisar logs de validação de dados e corrigir erros de entrada"
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTA CRÍTICO: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar data quality failures: {str(e)}")

    def _detect_import_delay(self):
        """Detecta DAGs sem carga há mais de 3 dias via marts.import_log."""
        query = """
        SELECT
            tabela_destino,
            MAX(executado_em) AS last_import,
            NOW() - MAX(executado_em) AS delay_duration,
            COUNT(*) AS total_imports
        FROM marts.import_log
        WHERE status = 'OK'
        GROUP BY tabela_destino
        HAVING NOW() - MAX(executado_em) > INTERVAL '3 days'
        ORDER BY delay_duration DESC
        """
        try:
            result = self.db.execute(query).fetchall()
            for row in result:
                delay_hours = row[2].total_seconds() / 3600
                alert = {
                    'type': 'IMPORT_DELAY',
                    'severity': 'WARNING',
                    'timestamp': datetime.now().isoformat(),
                    'source_name': row[0],
                    'last_import': row[1].isoformat() if row[1] else None,
                    'delay_hours': round(delay_hours, 1),
                    'delay_days': round(delay_hours / 24, 1),
                    'message': f"Tabela '{row[0]}' sem carga há {round(delay_hours / 24, 1)} dias",
                    'action': "Verificar DAG no Airflow e logs de importação"
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTA: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar import delay: {str(e)}")

    def _detect_zero_volume(self):
        """Detecta períodos CGF com volume_final_cgf zerado ou NULL em staging.cgf."""
        query = """
        SELECT
            periodo,
            COUNT(*) AS total_registros,
            COUNT(CASE WHEN volume_final_cgf IS NULL OR volume_final_cgf = 0 THEN 1 END) AS zero_null_count,
            ROUND(100.0 * COUNT(CASE WHEN volume_final_cgf IS NULL OR volume_final_cgf = 0 THEN 1 END)
                / NULLIF(COUNT(*), 0), 2) AS zero_percent
        FROM staging.cgf
        WHERE importado_em >= NOW() - INTERVAL '7 days'
        GROUP BY periodo
        HAVING COUNT(CASE WHEN volume_final_cgf IS NULL OR volume_final_cgf = 0 THEN 1 END) > 0
        ORDER BY periodo DESC
        """
        try:
            result = self.db.execute(query).fetchall()
            for row in result:
                alert = {
                    'type': 'ZERO_VOLUME',
                    'severity': 'CRITICAL',
                    'timestamp': datetime.now().isoformat(),
                    'periodo': row[0],
                    'total_registros': row[1],
                    'zero_null_count': row[2],
                    'zero_percent': float(row[3]) if row[3] else 0,
                    'message': f"Volume CGF zerado/NULL no período {row[0]}: {row[3]}% dos registros",
                    'action': "Investigar ETL CGF e validar arquivo de origem"
                }
                self.alerts.append(alert)
                logger.error(f"ALERTA CRÍTICO: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar zero volume: {str(e)}")

    def _detect_duplicate_period(self):
        """Detecta períodos PMPV duplicados em staging.pmpv_agregados."""
        query = """
        SELECT
            periodo,
            COUNT(*) AS occurrences
        FROM staging.pmpv_agregados
        GROUP BY periodo
        HAVING COUNT(*) > 1
        ORDER BY occurrences DESC
        """
        try:
            result = self.db.execute(query).fetchall()
            for row in result:
                alert = {
                    'type': 'DUPLICATE_PERIOD',
                    'severity': 'WARNING',
                    'timestamp': datetime.now().isoformat(),
                    'periodo': row[0],
                    'occurrences': row[1],
                    'message': f"Período PMPV duplicado: {row[0]} aparece {row[1]}x",
                    'action': "Verificar lógica de importação e remover duplicatas"
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTA: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar duplicate period: {str(e)}")

    def _detect_abnormal_rejection_rate(self):
        """Detecta alta taxa de falhas DQ por DAG via marts.data_quality_results (últimos 7 dias)."""
        query = """
        SELECT
            dag_id,
            DATE(run_ts) AS run_date,
            COUNT(*) AS total_checks,
            COUNT(CASE WHEN status = 'FAIL' THEN 1 END) AS failed_checks,
            ROUND(100.0 * COUNT(CASE WHEN status = 'FAIL' THEN 1 END)
                / NULLIF(COUNT(*), 0), 2) AS failure_rate
        FROM marts.data_quality_results
        WHERE run_ts >= NOW() - INTERVAL '7 days'
        GROUP BY dag_id, DATE(run_ts)
        HAVING ROUND(100.0 * COUNT(CASE WHEN status = 'FAIL' THEN 1 END)
                / NULLIF(COUNT(*), 0), 2) > 5.0
        ORDER BY failure_rate DESC
        """
        try:
            result = self.db.execute(query).fetchall()
            for row in result:
                alert = {
                    'type': 'ABNORMAL_REJECTION_RATE',
                    'severity': 'WARNING',
                    'timestamp': datetime.now().isoformat(),
                    'dag_id': row[0],
                    'run_date': row[1].isoformat() if row[1] else None,
                    'total_checks': row[2],
                    'failed_checks': row[3],
                    'failure_rate': float(row[4]) if row[4] else 0,
                    'message': f"Taxa de falha DQ anormal em '{row[0]}': {row[4]}% em {row[1]}",
                    'action': "Revisar DAG e fontes de dados"
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTA: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar rejection rate: {str(e)}")

    def get_summary(self) -> Dict[str, int]:
        """
        Retorna resumo de alertas por severidade
        
        Returns:
            Dict com contagem por severidade
        """
        summary = {
            'CRITICAL': len([a for a in self.alerts if a.get('severity') == 'CRITICAL']),
            'WARNING': len([a for a in self.alerts if a.get('severity') == 'WARNING']),
            'INFO': len([a for a in self.alerts if a.get('severity') == 'INFO']),
            'TOTAL': len(self.alerts)
        }
        return summary


def create_detector(db_connection) -> AnomalyDetector:
    """Factory para criar instância do detector"""
    return AnomalyDetector(db_connection)