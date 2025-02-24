import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, config):
        self.config = config
        self.email_config = config.get_email_config()
        self.template_cache = {}  # Cache for loaded templates

    def _load_template(self, template_name: str) -> Optional[str]:
        """Load template from file and cache it"""
        if template_name in self.template_cache:
            return self.template_cache[template_name]

        template_path = self.email_config['templates'].get(template_name)
        if not template_path:
            logger.error(f"Template {template_name} not configured")
            return None

        try:
            path = Path(template_path)
            if not path.exists():
                logger.error(f"Template file not found: {template_path}")
                return None

            with path.open('r') as f:
                template = f.read()
                self.template_cache[template_name] = template
                return template
        except Exception as e:
            logger.error(f"Failed to load template {template_name}: {str(e)}")
            return None

    def _send_email(self, alert_type: str, context: Dict):
        """Send email using configured template and settings"""
        alert_config = self.email_config['alerts'].get(alert_type)
        if not alert_config:
            logger.error(f"Alert configuration not found for type: {alert_type}")
            return

        # Load template
        template = self._load_template(alert_config['template'])
        if not template:
            logger.error(f"Failed to load template for alert type: {alert_type}")
            return

        try:
            # Format subject and body
            subject = alert_config['subject'].format(**context)
            body = template.format(**context)

            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_address']
            msg['To'] = ', '.join(alert_config['to'])
            if alert_config.get('cc'):
                msg['Cc'] = ', '.join(alert_config['cc'])
            msg['Subject'] = subject

            msg.attach(MIMEText(body, 'html'))

            # Send email
            with smtplib.SMTP(self.email_config['smtp_server'], 
                            self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['smtp_user'],
                           self.email_config['smtp_password'])
                
                recipients = alert_config['to'] + (alert_config.get('cc', []))
                server.send_message(msg, to_addrs=recipients)
                
                logger.info(f"Sent {alert_type} alert email for {context.get('vhost', '')}/{context.get('queue', '')}")
                
        except Exception as e:
            logger.error(f"Failed to send {alert_type} alert email: {str(e)}")
            # Try to send error notification
            if alert_type != 'error':  # Prevent recursive error sending
                error_context = {
                    'error_type': 'Email Sending Failed',
                    'error_details': str(e),
                    'original_context': context
                }
                self._send_email('error', error_context)

    def send_drift_alert(self, context: Dict):
        """Send drift alert email"""
        self._send_email('drift', context)

    def send_threshold_alert(self, context: Dict):
        """Send threshold exceeded alert email"""
        self._send_email('threshold', context)

    def send_error_alert(self, error_type: str, error_details: str, 
                        context: Optional[Dict] = None):
        """Send error alert email"""
        error_context = {
            'error_type': error_type,
            'error_details': error_details,
            'context': context or {}
        }
        self._send_email('error', error_context)