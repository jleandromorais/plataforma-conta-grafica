"""
Sistema de Alertas por Email - Plataforma Conta Gráfica

Responsabilidades:
- Renderizar template HTML com dados de alertas
- Enviar emails via SMTP (smtplib nativo)
- Suportar múltiplos destinatários
- Tratamento robusto de erros
- Logs de envio para auditoria
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Any, Optional
import socket
import os

logger = logging.getLogger(__name__)


class AlertEmailer:
    """Sistema de envio de alertas por email"""

    def __init__(self, 
                 smtp_host: str,
                 smtp_port: int,
                 smtp_user: str,
                 smtp_password: str,
                 alert_from: str,
                 alert_to: str,
                 use_tls: bool = True):
        """
        Inicializa configuração SMTP
        
        Args:
            smtp_host: Servidor SMTP (ex: smtp.gmail.com)
            smtp_port: Porta SMTP (587 para TLS, 25 para plain)
            smtp_user: Usuário de autenticação
            smtp_password: Senha de autenticação
            alert_from: Email remetente
            alert_to: Email(s) destinatário(s) - suporta lista separada por vírgula
            use_tls: Usar TLS (True por padrão)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.alert_from = alert_from
        # Suporta múltiplos destinatários
        self.alert_to_list = [e.strip() for e in alert_to.split(',') if e.strip()]
        self.use_tls = use_tls
        self.hostname = socket.gethostname()

    def send_alerts(self, alerts: List[Dict[str, Any]], 
                   dry_run: bool = False) -> bool:
        """
        Envia email com alertas encontrados
        
        Args:
            alerts: Lista de dicionários com alertas
            dry_run: Se True, não envia (apenas log)
            
        Returns:
            True se sucesso, False se erro
        """
        if not alerts:
            logger.info("✓ Nenhum alerta para enviar")
            return True

        try:
            # Renderizar template
            html_content = self._render_template(alerts)
            
            # Criar mensagem
            msg = self._create_message(html_content, alerts)
            
            # Log antes de enviar
            logger.info(f"📧 Preparando envio para: {', '.join(self.alert_to_list)}")
            logger.info(f"   Total de alertas: {len(alerts)}")
            
            if dry_run:
                logger.info("🔄 DRY RUN: Email não será enviado")
                logger.debug(f"Conteúdo do email:\n{html_content}")
                return True
            
            # Enviar email
            self._send_via_smtp(msg)
            logger.info(f"✅ Email enviado com sucesso para {len(self.alert_to_list)} destinatário(s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao enviar email: {str(e)}")
            return False

    def _render_template(self, alerts: List[Dict[str, Any]]) -> str:
        """
        Renderiza template HTML com dados de alertas
        
        Args:
            alerts: Lista de alertas
            
        Returns:
            HTML renderizado
        """
        try:
            # Carregar template
            template_path = os.path.join(
                os.path.dirname(__file__),
                'email_template.html'
            )
            
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except FileNotFoundError:
            logger.warning(f"Template não encontrado em {template_path}, usando inline")
            template = self._get_default_template()
        
        # Agrupar alertas por severidade
        critical_alerts = [a for a in alerts if a.get('severity') == 'CRITICAL']
        warning_alerts = [a for a in alerts if a.get('severity') == 'WARNING']
        info_alerts = [a for a in alerts if a.get('severity') == 'INFO']
        
        # Renderizar seções de alertas
        critical_section = self._render_alert_section(critical_alerts, 'CRÍTICO')
        warning_section = self._render_alert_section(warning_alerts, 'AVISO')
        info_section = self._render_alert_section(info_alerts, 'INFORMAÇÃO')
        
        # Substituir placeholders
        now = datetime.now()
        replacements = {
            '{{alert_timestamp}}': now.strftime('%d/%m/%Y %H:%M:%S'),
            '{{alert_date}}': now.strftime('%Y%m%d'),
            '{{execution_timestamp}}': now.isoformat(),
            '{{hostname}}': self.hostname,
            '{{critical_count}}': str(len(critical_alerts)),
            '{{warning_count}}': str(len(warning_alerts)),
            '{{info_count}}': str(len(info_alerts)),
            '{{total_count}}': str(len(alerts)),
            '{{critical_alerts_section}}': critical_section,
            '{{warning_alerts_section}}': warning_section,
            '{{info_alerts_section}}': info_section,
        }
        
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
        
        return template

    def _render_alert_section(self, alerts: List[Dict[str, Any]], 
                             severity_label: str) -> str:
        """
        Renderiza seção de alertas por severidade
        
        Args:
            alerts: Lista de alertas da severidade
            severity_label: Label da severidade (CRÍTICO, AVISO, etc)
            
        Returns:
            HTML da seção ou string vazia se sem alertas
        """
        if not alerts:
            return ""
        
        severity_map = {
            'CRITICAL': 'critical',
            'WARNING': 'warning',
            'INFO': 'info'
        }
        severity_class = severity_map.get(alerts[0].get('severity', ''), 'info')
        
        html = f"""
        <div class="alerts-section">
            <h3>⚠️ Alertas - {severity_label} ({len(alerts)})</h3>
        """
        
        for alert in alerts:
            html += self._render_alert_item(alert, severity_class)
        
        html += "</div>"
        return html

    def _render_alert_item(self, alert: Dict[str, Any], 
                          severity_class: str) -> str:
        """
        Renderiza item individual de alerta
        
        Args:
            alert: Dados do alerta
            severity_class: Classe CSS de severidade
            
        Returns:
            HTML do alerta
        """
        severity = alert.get('severity', 'INFO')
        alert_type = alert.get('type', 'UNKNOWN')
        message = alert.get('message', 'Sem descrição')
        action = alert.get('action', 'Sem ação recomendada')
        timestamp = alert.get('timestamp', '')
        
        # Extrair detalhes adicionais
        details_html = ""
        for key, value in alert.items():
            if key not in ['type', 'severity', 'timestamp', 'message', 'action']:
                details_html += f"<strong>{key}:</strong> {value}<br>"
        
        html = f"""
        <div class="alert-item {severity_class}">
            <div class="alert-header">
                <span class="alert-title">{alert_type}</span>
                <span class="alert-severity {severity_class}">{severity}</span>
            </div>
            <div class="alert-message">📌 {message}</div>
        """
        
        if details_html:
            html += f"""
            <div class="alert-details">
                {details_html}
            </div>
            """
        
        html += f"""
            <div class="alert-action">
                <span class="action-label">→ Ação:</span>{action}
            </div>
        </div>
        """
        
        return html

    def _create_message(self, html_content: str, 
                       alerts: List[Dict[str, Any]]) -> MIMEMultipart:
        """
        Cria objeto de mensagem MIME
        
        Args:
            html_content: Conteúdo HTML do email
            alerts: Lista de alertas
            
        Returns:
            Objeto MIMEMultipart configurado
        """
        msg = MIMEMultipart('alternative')
        
        # Contagem por severidade
        critical = len([a for a in alerts if a.get('severity') == 'CRITICAL'])
        warning = len([a for a in alerts if a.get('severity') == 'WARNING'])
        
        # Subject descritivo
        subject = f"[ALERTA] {critical} Crítico(s), {warning} Aviso(s) - Conta Gráfica"
        if not critical and not warning:
            subject = "[MONITORAMENTO] Relatório de Alertas - Conta Gráfica"
        
        msg['Subject'] = subject
        msg['From'] = self.alert_from
        msg['To'] = ', '.join(self.alert_to_list)
        msg['X-Mailer'] = 'CGF-Monitoring-System/1.0'
        
        # Versão text/plain (fallback)
        text_content = self._render_text_version(alerts)
        part_text = MIMEText(text_content, 'plain', _charset='utf-8')
        msg.attach(part_text)
        
        # Versão HTML
        part_html = MIMEText(html_content, 'html', _charset='utf-8')
        msg.attach(part_html)
        
        return msg

    def _render_text_version(self, alerts: List[Dict[str, Any]]) -> str:
        """
        Renderiza versão texto do email (fallback)
        
        Args:
            alerts: Lista de alertas
            
        Returns:
            Conteúdo em texto puro
        """
        lines = [
            "=" * 70,
            "ALERTA DE MONITORAMENTO - PLATAFORMA CONTA GRÁFICA",
            "=" * 70,
            f"Timestamp: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
            f"Hostname: {self.hostname}",
            "",
            "RESUMO",
            "-" * 70,
            f"Total de alertas: {len(alerts)}",
            f"Críticos: {len([a for a in alerts if a.get('severity') == 'CRITICAL'])}",
            f"Avisos: {len([a for a in alerts if a.get('severity') == 'WARNING'])}",
            f"Informações: {len([a for a in alerts if a.get('severity') == 'INFO'])}",
            "",
            "ALERTAS DETALHADOS",
            "-" * 70,
        ]
        
        for i, alert in enumerate(alerts, 1):
            lines.extend([
                f"\n[{i}] {alert.get('type', 'UNKNOWN')} - {alert.get('severity', 'INFO')}",
                f"    Mensagem: {alert.get('message', 'N/A')}",
                f"    Ação: {alert.get('action', 'N/A')}",
            ])
        
        lines.extend([
            "",
            "=" * 70,
            "Este é um email automático do Sistema de Monitoramento.",
            "Não responda. Contate: data-engineering@empresa.com",
            "=" * 70,
        ])
        
        return "\n".join(lines)

    def _send_via_smtp(self, msg: MIMEMultipart):
        """
        Envia mensagem via SMTP com tratamento de erros
        
        Args:
            msg: Objeto MIMEMultipart
            
        Raises:
            Exception: Se falha ao conectar ou enviar
        """
        connection = None
        try:
            # Conectar ao servidor
            logger.debug(f"Conectando a {self.smtp_host}:{self.smtp_port}")
            
            if self.use_tls:
                connection = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                connection.starttls()
            else:
                connection = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            
            # Autenticar
            logger.debug(f"Autenticando como {self.smtp_user}")
            connection.login(self.smtp_user, self.smtp_password)
            
            # Enviar
            connection.sendmail(
                self.alert_from,
                self.alert_to_list,
                msg.as_string()
            )
            
        except smtplib.SMTPAuthenticationError as e:
            raise Exception(f"Erro de autenticação SMTP: {str(e)}")
        except smtplib.SMTPException as e:
            raise Exception(f"Erro SMTP: {str(e)}")
        except socket.timeout as e:
            raise Exception(f"Timeout ao conectar SMTP: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro inesperado ao enviar email: {str(e)}")
        finally:
            if connection:
                try:
                    connection.quit()
                except:
                    pass

    def _get_default_template(self) -> str:
        """
        Template inline padrão (fallback se arquivo não existir)
        
        Returns:
            HTML template
        """
        return """
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 800px; margin: 0 auto; background: white; border: 1px solid #ddd;">
                <div style="background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
                            color: white; padding: 30px; text-align: center;">
                    <h1 style="margin: 0; font-size: 24px;">🚨 Alerta de Monitoramento</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">Plataforma Conta Gráfica</p>
                </div>
                <div style="padding: 30px;">
                    <h2>Resumo: {{critical_count}} Crítico(s), {{warning_count}} Aviso(s)</h2>
                    {{critical_alerts_section}}
                    {{warning_alerts_section}}
                    {{info_alerts_section}}
                    <div style="background: #e8f5e9; border-left: 4px solid #388e3c; padding: 20px; margin-top: 30px;">
                        <h3 style="color: #388e3c; margin-top: 0;">Próximas Ações</h3>
                        <ul>
                            <li>Revisar alertas críticos com prioridade máxima</li>
                            <li>Consultar logs em: <code>/logs/alerts_{{alert_date}}.log</code></li>
                            <li>Contatar o time de infraestrutura se necessário</li>
                        </ul>
                    </div>
                </div>
                <div style="background: #f5f5f5; padding: 20px; text-align: center; 
                            font-size: 11px; color: #999; border-top: 1px solid #ddd;">
                    Timestamp: {{execution_timestamp}} | Servidor: {{hostname}}
                </div>
            </div>
        </body>
        </html>
        """


def create_emailer(smtp_config: Dict[str, Any]) -> AlertEmailer:
    """
    Factory para criar instância de emailer
    
    Args:
        smtp_config: Dict com chaves: 
                     smtp_host, smtp_port, smtp_user, smtp_password,
                     alert_from, alert_to, use_tls (opcional)
    
    Returns:
        Instância AlertEmailer
    """
    return AlertEmailer(
        smtp_host=smtp_config.get('smtp_host'),
        smtp_port=int(smtp_config.get('smtp_port', 587)),
        smtp_user=smtp_config.get('smtp_user'),
        smtp_password=smtp_config.get('smtp_password'),
        alert_from=smtp_config.get('alert_from'),
        alert_to=smtp_config.get('alert_to'),
        use_tls=smtp_config.get('use_tls', True)
    )