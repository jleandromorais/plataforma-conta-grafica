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
        """
        1.2 - Detecta falhas de qualidade de dados nas últimas 24h
        
        Verifica:
        - Registros com status = 'FAILED' em data_quality_checks
        - Últimas 24 horas
        - Agrupa por tipo de validação
        """
        query = """
        SELECT 
            check_name,
            COUNT(*) as failure_count,
            MAX(check_timestamp) as last_failure,
            STRING_AGG(DISTINCT error_message, '; ')::TEXT as error_details
        FROM data_quality_checks
        WHERE 
            status = 'FAILED'
            AND check_timestamp >= NOW() - INTERVAL '24 hours'
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
        """
        1.3 - Detecta atraso de importação > 3 dias
        
        Verifica:
        - Última importação bem-sucedida por fonte
        - Se > 3 dias atrás = ALERTA
        """
        query = """
        SELECT 
            source_name,
            MAX(import_timestamp) as last_import,
            NOW() - MAX(import_timestamp) as delay_duration,
            COUNT(*) as total_imports
        FROM import_log
        WHERE status = 'SUCCESS'
        GROUP BY source_name
        HAVING NOW() - MAX(import_timestamp) > INTERVAL '3 days'
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
                    'message': f"Importação de '{row[0]}' atrasada: {round(delay_hours / 24, 1)} dias",
                    'action': "Verificar conectividade com a fonte e logs de importação"
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTA: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar import delay: {str(e)}")

    def _detect_zero_volume(self):
        """
        1.4 - Detecta volume CGF zerado ou NULL
        
        Verifica:
        - Registros com volume = 0 ou NULL no último período
        - Compara com média histórica
        """
        query = """
        SELECT 
            DATE(data_referencia) as data_ref,
            COUNT(*) as total_registros,
            COUNT(CASE WHEN volume IS NULL OR volume = 0 THEN 1 END) as zero_null_count,
            ROUND(100.0 * COUNT(CASE WHEN volume IS NULL OR volume = 0 THEN 1 END) 
                / NULLIF(COUNT(*), 0), 2) as zero_percent,
            ROUND(AVG(CASE WHEN volume > 0 THEN volume END), 2) as avg_volume
        FROM cgf_dados
        WHERE data_referencia >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(data_referencia)
        HAVING COUNT(CASE WHEN volume IS NULL OR volume = 0 THEN 1 END) > 
               COUNT(*) * 0.10
        ORDER BY data_ref DESC
        """
        
        try:
            result = self.db.execute(query).fetchall()
            
            for row in result:
                alert = {
                    'type': 'ZERO_VOLUME',
                    'severity': 'CRITICAL',
                    'timestamp': datetime.now().isoformat(),
                    'data_referencia': row[0].isoformat() if row[0] else None,
                    'total_registros': row[1],
                    'zero_null_count': row[2],
                    'zero_percent': row[3],
                    'avg_volume': row[4],
                    'message': f"Volume zerado/NULL em {row[0]}: {row[3]}% dos registros",
                    'action': "Investigar fonte de dados e validar importação"
                }
                self.alerts.append(alert)
                logger.error(f"ALERTA CRÍTICO: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar zero volume: {str(e)}")

    def _detect_duplicate_period(self):
        """
        1.5 - Detecta período duplicado
        
        Verifica:
        - Períodos que aparecem mais de 1x para mesma conta/origem
        - Isso indica importação duplicada
        """
        query = """
        SELECT 
            data_referencia,
            conta_id,
            COUNT(*) as occurrences,
            STRING_AGG(DISTINCT origem::TEXT, ', ')::TEXT as origens,
            COUNT(DISTINCT origem) as num_origens
        FROM cgf_dados
        WHERE data_referencia >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY data_referencia, conta_id
        HAVING COUNT(*) > 1
        ORDER BY occurrences DESC, data_referencia DESC
        """
        
        try:
            result = self.db.execute(query).fetchall()
            
            for row in result:
                alert = {
                    'type': 'DUPLICATE_PERIOD',
                    'severity': 'WARNING',
                    'timestamp': datetime.now().isoformat(),
                    'data_referencia': row[0].isoformat() if row[0] else None,
                    'conta_id': row[1],
                    'occurrences': row[2],
                    'origens': row[3],
                    'num_origens': row[4],
                    'message': f"Período duplicado: Conta {row[1]} em {row[0]} ({row[2]}x)",
                    'action': "Revisar e remover registros duplicados, verificar lógica de importação"
                }
                self.alerts.append(alert)
                logger.warning(f"ALERTA: {alert['message']}")
        except Exception as e:
            logger.error(f"Erro ao detectar duplicate period: {str(e)}")

    def _detect_abnormal_rejection_rate(self):
        """
        1.6 - Detecta taxa anormal de rejeição
        
        Verifica:
        - Taxa de rejeição por fonte
        - Se > 5% em período recente = ALERTA
        """
        query = """
        SELECT 
            source_name,
            DATE(import_timestamp) as import_date,
            COUNT(*) as total_processed,
            COUNT(CASE WHEN status = 'REJECTED' THEN 1 END) as rejected_count,
            ROUND(100.0 * COUNT(CASE WHEN status = 'REJECTED' THEN 1 END) 
                / NULLIF(COUNT(*), 0), 2) as rejection_rate
        FROM import_log
        WHERE import_timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY source_name, DATE(import_timestamp)
        HAVING ROUND(100.0 * COUNT(CASE WHEN status = 'REJECTED' THEN 1 END) 
                / NULLIF(COUNT(*), 0), 2) > 5.0
        ORDER BY rejection_rate DESC
        """
        
        try:
            result = self.db.execute(query).fetchall()
            
            for row in result:
                alert = {
                    'type': 'ABNORMAL_REJECTION_RATE',
                    'severity': 'WARNING',
                    'timestamp': datetime.now().isoformat(),
                    'source_name': row[0],
                    'import_date': row[1].isoformat() if row[1] else None,
                    'total_processed': row[1],
                    'rejected_count': row[2],
                    'rejection_rate': row[4],
                    'message': f"Taxa de rejeição anormal em '{row[0]}': {row[4]}% em {row[1]}",
                    'action': "Analisar motivos de rejeição e contatar fonte de dados"
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