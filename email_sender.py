import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self, config):
        self.config = config
        self.email_config = config.get_email_config()
        self.template_cache = {}

    def _load_template(self, template_name: str) -> Optional[str]:
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
        alert_config = self.email_config['alerts'].get(alert_type)
        if not alert_config:
            logger.error(f"Alert configuration not found for type: {alert_type}")
            return

        template = self._load_template(alert_config['template'])
        if not template:
            logger.error(f"Failed to load template for alert type: {alert_type}")
            return

        try:
            subject = alert_config['subject'].format(**context)
            body = template.format(**context)

            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_address']
            msg['To'] = ', '.join(alert_config['to'])
            if alert_config.get('cc'):
                msg['Cc'] = ', '.join(alert_config['cc'])
