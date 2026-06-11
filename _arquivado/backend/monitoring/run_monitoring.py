"""
Orquestrador Principal de Monitoramento - Plataforma Conta Gráfica

Responsabilidades:
- Carregar configurações do .env
- Conectar ao PostgreSQL
- Executar detector de anomalias
- Registrar alertas em banco de dados
- Enviar emails via alerter
- Manter logs estruturados
- Retornar exit code apropriado
"""

import os
import sys
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

# Importar módulos do monitoring
from monitoring.anomaly_detector import create_detector
from monitoring.alerter import create_emailer

# Logger de módulo — substituído pelo logger configurado em main()
logger = logging.getLogger('monitoring')

# ============================================================================
# CONFIGURAÇÃO DE LOGGING
# ============================================================================

def setup_logging(log_dir: str = 'logs') -> logging.Logger:
    """
    Configura logging estruturado com arquivo e console
    
    Args:
        log_dir: Diretório para armazenar logs
        
    Returns:
        Logger configurado
    """
    # Criar diretório se não existir
    Path(log_dir).mkdir(exist_ok=True)
    
    # Nome do arquivo de log com data
    log_file = os.path.join(log_dir, f"alerts_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configurar logger
    logger = logging.getLogger('monitoring')
    logger.setLevel(logging.DEBUG)
    
    # Remover handlers existentes
    logger.handlers.clear()
    
    # Handler de arquivo
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Handler de console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Formato
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, log_file


# ============================================================================
# CONEXÃO COM BANCO DE DADOS
# ============================================================================

def create_db_connection(db_config: Dict[str, str]):
    """
    Cria conexão com PostgreSQL
    
    Args:
        db_config: Dict com chaves db_host, db_port, db_name, db_user, db_password
        
    Returns:
        Connection object ou None se erro
    """
    try:
        import psycopg2
        from psycopg2 import pool
        
        connection = psycopg2.connect(
            host=db_config.get('db_host', 'localhost'),
            port=int(db_config.get('db_port', 5432)),
            database=db_config.get('db_name'),
            user=db_config.get('db_user'),
            password=db_config.get('db_password')
        )
        
        return connection
    except ImportError:
        try:
            from sqlalchemy import create_engine
            
            conn_string = f"postgresql://{db_config.get('db_user')}:{db_config.get('db_password')}@" \
                         f"{db_config.get('db_host', 'localhost')}:{db_config.get('db_port', 5432)}/" \
                         f"{db_config.get('db_name')}"
            
            engine = create_engine(conn_string, echo=False)
            return engine.connect()
        except Exception as e:
            raise Exception(f"Erro ao conectar com DB: {str(e)}")


# ============================================================================
# GERENCIAMENTO DE ALERTAS EM BANCO DE DADOS
# ============================================================================

def create_monitoring_alerts_table(db_connection):
    """
    Cria tabela marts.monitoring_alerts se não existir
    
    Args:
        db_connection: Conexão com PostgreSQL
    """
    sql = """
    CREATE TABLE IF NOT EXISTS marts.monitoring_alerts (
        alert_id SERIAL PRIMARY KEY,
        alert_date DATE NOT NULL DEFAULT CURRENT_DATE,
        alert_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        alert_type VARCHAR(50) NOT NULL,
        severity VARCHAR(20) NOT NULL,
        message TEXT NOT NULL,
        action TEXT,
        alert_details JSONB,
        email_sent BOOLEAN DEFAULT FALSE,
        email_sent_at TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_alert_date (alert_date),
        INDEX idx_severity (severity),
        INDEX idx_alert_type (alert_type)
    );
    
    -- Comentários
    COMMENT ON TABLE marts.monitoring_alerts IS 'Registro histórico de alertas do sistema de monitoramento';
    COMMENT ON COLUMN marts.monitoring_alerts.alert_details IS 'Dados completos do alerta em JSON';
    COMMENT ON COLUMN marts.monitoring_alerts.email_sent IS 'Flag indicando se email foi enviado';
    """
    
    try:
        # Tentar com psycopg2
        if hasattr(db_connection, 'cursor'):
            cursor = db_connection.cursor()
            cursor.execute(sql)
            db_connection.commit()
            cursor.close()
        # Tentar com sqlalchemy
        else:
            db_connection.execute(sql)
            db_connection.commit()
        
        logger.info("✓ Tabela marts.monitoring_alerts verificada/criada")
    except Exception as e:
        logger.warning(f"⚠ Não foi possível criar tabela: {str(e)}")


def insert_alerts_to_db(db_connection, alerts: List[Dict[str, Any]], 
                       email_sent: bool = False) -> int:
    """
    Insere alertas na tabela marts.monitoring_alerts
    
    Args:
        db_connection: Conexão com PostgreSQL
        alerts: Lista de alertas
        email_sent: Se email foi enviado com sucesso
        
    Returns:
        Quantidade de alertas inseridos
    """
    if not alerts:
        return 0
    
    try:
        import json
        
        inserted = 0
        now = datetime.now()
        
        for alert in alerts:
            sql = """
            INSERT INTO marts.monitoring_alerts 
            (alert_type, severity, message, action, alert_details, email_sent, email_sent_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                alert.get('type'),
                alert.get('severity'),
                alert.get('message'),
                alert.get('action'),
                json.dumps(alert, default=str),
                email_sent,
                now if email_sent else None
            )
            
            try:
                # Tentar com psycopg2
                if hasattr(db_connection, 'cursor'):
                    cursor = db_connection.cursor()
                    cursor.execute(sql, values)
                    inserted += 1
                    cursor.close()
                # Tentar com sqlalchemy
                else:
                    db_connection.execute(sql, values)
                    inserted += 1
            except Exception as e:
                logger.error(f"Erro ao inserir alerta {alert.get('type')}: {str(e)}")
        
        if hasattr(db_connection, 'cursor'):
            db_connection.commit()
        else:
            db_connection.commit()
        
        logger.info(f"✓ {inserted} alerta(s) inserido(s) em marts.monitoring_alerts")
        return inserted
        
    except Exception as e:
        logger.error(f"Erro ao inserir alertas em DB: {str(e)}")
        return 0


# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Função principal do orquestrador de monitoramento
    
    Fluxo:
    1. Carregar configurações do .env
    2. Configurar logging
    3. Conectar ao PostgreSQL
    4. Executar detector de anomalias
    5. Se alertas encontrados:
       - Registrar em banco de dados
       - Enviar emails
       - Log estruturado
    6. Retornar exit code apropriado
    
    Returns:
        0 se sem alertas, 1 se alertas foram processados
    """
    
    # ========================================================================
    # 1. CARREGAR CONFIGURAÇÕES
    # ========================================================================
    
    # Carregar .env
    load_dotenv()
    
    # Validar variáveis obrigatórias
    required_vars = [
        'DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD',
        'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASSWORD',
        'ALERT_FROM', 'ALERT_TO'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Variáveis de ambiente obrigatórias faltando: {', '.join(missing_vars)}")
        return 1
    
    # ========================================================================
    # 2. CONFIGURAR LOGGING
    # ========================================================================
    
    try:
        logger, log_file = setup_logging()
        logger.info("=" * 80)
        logger.info("INICIANDO MONITORAMENTO - PLATAFORMA CONTA GRÁFICA")
        logger.info("=" * 80)
    except Exception as e:
        print(f"❌ Erro ao configurar logging: {str(e)}")
        return 1
    
    # ========================================================================
    # 3. CONECTAR AO BANCO DE DADOS
    # ========================================================================
    
    logger.info("Conectando ao PostgreSQL...")
    
    db_config = {
        'db_host': os.getenv('DB_HOST'),
        'db_port': os.getenv('DB_PORT'),
        'db_name': os.getenv('DB_NAME'),
        'db_user': os.getenv('DB_USER'),
        'db_password': os.getenv('DB_PASSWORD')
    }
    
    try:
        db_connection = create_db_connection(db_config)
        logger.info(f"✓ Conectado ao banco: {db_config['db_name']} @ {db_config['db_host']}")
    except Exception as e:
        logger.error(f"❌ Erro ao conectar ao banco de dados: {str(e)}")
        return 1
    
    # ========================================================================
    # 4. CRIAR TABELA DE MONITORAMENTO
    # ========================================================================
    
    try:
        create_monitoring_alerts_table(db_connection)
    except Exception as e:
        logger.warning(f"⚠ Erro ao criar tabela de monitoramento: {str(e)}")
    
    # ========================================================================
    # 5. EXECUTAR DETECTOR DE ANOMALIAS
    # ========================================================================
    
    logger.info("Iniciando detecção de anomalias...")
    
    try:
        detector = create_detector(db_connection)
        alerts = detector.detect_all()
        
        summary = detector.get_summary()
        logger.info(f"✓ Detecção concluída: {summary['CRITICAL']} críticos, "
                   f"{summary['WARNING']} avisos, {summary['INFO']} info")
        
    except Exception as e:
        logger.error(f"❌ Erro durante detecção de anomalias: {str(e)}")
        alerts = []
    
    # ========================================================================
    # 6. PROCESSAR ALERTAS
    # ========================================================================
    
    exit_code = 0
    
    if not alerts:
        logger.info("✓ Nenhuma anomalia detectada. Sistema em status normal.")
        
        # Email de status OK (opcional)
        summary_msg = f"Monitoramento executado com sucesso. Nenhuma anomalia em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        logger.info(summary_msg)
        
    else:
        logger.warning(f"🚨 {len(alerts)} ALERTA(S) DETECTADO(S)")
        logger.warning("=" * 80)
        
        # Registrar em banco de dados
        logger.info("Registrando alertas em banco de dados...")
        
        try:
            insert_alerts_to_db(db_connection, alerts, email_sent=False)
        except Exception as e:
            logger.error(f"Erro ao registrar em DB: {str(e)}")
        
        # Enviar emails
        logger.info("Enviando alertas por email...")
        
        try:
            emailer = create_emailer({
                'smtp_host': os.getenv('SMTP_HOST'),
                'smtp_port': os.getenv('SMTP_PORT'),
                'smtp_user': os.getenv('SMTP_USER'),
                'smtp_password': os.getenv('SMTP_PASSWORD'),
                'alert_from': os.getenv('ALERT_FROM'),
                'alert_to': os.getenv('ALERT_TO'),
                'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true'
            })
            
            if emailer.send_alerts(alerts, dry_run=False):
                logger.info("✅ Alertas enviados com sucesso")
                
                # Marcar como enviados em DB
                try:
                    insert_alerts_to_db(db_connection, alerts, email_sent=True)
                except Exception as e:
                    logger.error(f"Erro ao atualizar status de envio: {str(e)}")
                
                exit_code = 1
            else:
                logger.error("❌ Erro ao enviar alertas")
                exit_code = 1
                
        except Exception as e:
            logger.error(f"❌ Erro ao tentar enviar emails: {str(e)}")
            exit_code = 1
        
        logger.warning("=" * 80)
    
    # ========================================================================
    # 7. FINALIZAR
    # ========================================================================
    
    logger.info(f"Monitoramento finalizado com exit code: {exit_code}")
    logger.info(f"Logs disponíveis em: {log_file}")
    logger.info("=" * 80)
    
    try:
        if hasattr(db_connection, 'close'):
            db_connection.close()
    except:
        pass
    
    return exit_code


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)