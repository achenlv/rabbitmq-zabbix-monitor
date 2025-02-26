# app/core/email.py
import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import List, Dict, Optional
from datetime import datetime
from app.utils.config import config

logger = logging.getLogger(__name__)

class EmailSender:
    def __init__(self):
        """Initialize email sender with config"""
        self.config = config.get_email_config()
        self.smtp_server = self.config.get('smtp_server', '')
        self.smtp_port = int(self.config.get('smtp_port', 25))
        self.smtp_user = self.config.get('smtp_user', '')
        self.smtp_password = self.config.get('smtp_password', '')
        self.from_address = self.config.get('from_address', 'rabbitmq-monitor@example.com')
        self.templates = self.config.get('templates', {})
        self.alert_configs = self.config.get('alerts', {})
        
    def send_drift_alert(self, queue_info: Dict, current_value: int, previous_value: int, 
                        increase_percentage: float) -> bool:
        """
        Send email alert for queue size drift
        
        Args:
            queue_info: Dictionary with queue information (vhost, queue name, etc.)
            current_value: Current message_ready count
            previous_value: Previous message_ready count
            increase_percentage: Percentage increase
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            if 'drift' not in self.alert_configs:
                logger.error("Drift alert configuration not found")
                return False
                
            alert_config = self.alert_configs['drift']
            vhost = queue_info.get('vhost', 'unknown')
            queue = queue_info.get('queue', 'unknown')
            host = queue_info.get('zabbix_host', 'unknown')
            cluster_id = queue_info.get('cluster_id', 'unknown')
            
            # Get recipients
            to_list = alert_config.get('to', [])
            cc_list = alert_config.get('cc', [])
            
            if not to_list:
                logger.error("No recipients specified for drift alert")
                return False
            
            # Get subject with placeholders replaced
            subject = alert_config.get('subject', 'Queue Size Drift Alert')
            subject = subject.format(
                vhost=vhost,
                queue=queue,
                host=host,
                cluster=cluster_id,
                percentage=round(increase_percentage, 1)
            )
            
            # Build email content
            html_content = self._build_drift_alert_content(
                queue_info, current_value, previous_value, increase_percentage
            )
            
            # Send email
            return self._send_email(to_list, cc_list, subject, html_content)
            
        except Exception as e:
            logger.error(f"Error sending drift alert: {str(e)}")
            return False
    
    def _build_drift_alert_content(self, queue_info: Dict, current_value: int, 
                                  previous_value: int, increase_percentage: float) -> str:
        """Build HTML content for drift alert email"""
        try:
            # Try to load template if configured
            template_name = self.alert_configs.get('drift', {}).get('template')
            html_content = self._load_template(template_name)
            
            # If template loading failed, use default template
            if not html_content:
                html_content = """
                <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; }
                        .header { background-color: #f0f0f0; padding: 10px; border-bottom: 1px solid #ddd; }
                        .content { padding: 20px; }
                        table { border-collapse: collapse; width: 100%; }
                        th, td { text-align: left; padding: 8px; border: 1px solid #ddd; }
                        th { background-color: #f2f2f2; }
                        .alert { color: #721c24; background-color: #f8d7da; padding: 10px; border-radius: 4px; }
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h2>RabbitMQ Queue Size Drift Alert</h2>
                    </div>
                    <div class="content">
                        <p>A significant increase in queue size has been detected:</p>
                        
                        <div class="alert">
                            <p><strong>Alert:</strong> Queue size increased by {increase_percentage:.1f}%</p>
                        </div>
                        
                        <h3>Queue Details</h3>
                        <table>
                            <tr><th>Cluster</th><td>{cluster_id}</td></tr>
                            <tr><th>Virtual Host</th><td>{vhost}</td></tr>
                            <tr><th>Queue Name</th><td>{queue}</td></tr>
                            <tr><th>Host</th><td>{host}</td></tr>
                            <tr><th>Previous Value</th><td>{previous_value}</td></tr>
                            <tr><th>Current Value</th><td>{current_value}</td></tr>
                            <tr><th>Increase</th><td>{increase} ({increase_percentage:.1f}%)</td></tr>
                            <tr><th>Timestamp</th><td>{timestamp}</td></tr>
                        </table>
                        
                        <p>Please investigate this increase to ensure it's not causing issues with your system.</p>
                    </div>
                </body>
                </html>
                """
            
            # Fill in template variables
            vhost = queue_info.get('vhost', 'unknown')
            queue = queue_info.get('queue', 'unknown')
            host = queue_info.get('zabbix_host', 'unknown')
            cluster_id = queue_info.get('cluster_id', 'unknown')
            increase = current_value - previous_value
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            html_content = html_content.format(
                vhost=vhost,
                queue=queue,
                host=host,
                cluster_id=cluster_id,
                previous_value=previous_value,
                current_value=current_value,
                increase=increase,
                increase_percentage=increase_percentage,
                timestamp=timestamp
            )
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error building drift alert content: {str(e)}")
            # Return simple fallback content
            return f"""
            <html><body>
            <h2>RabbitMQ Queue Size Drift Alert</h2>
            <p>Queue {queue_info.get('vhost', '')}/{queue_info.get('queue', '')} has increased from {previous_value} to {current_value} messages ({increase_percentage:.1f}%).</p>
            </body></html>
            """
    
    def _load_template(self, template_name: Optional[str]) -> Optional[str]:
        """Load HTML template from file"""
        if not template_name or template_name not in self.templates:
            return None
            
        template_path = self.templates.get(template_name)
        if not template_path or not os.path.exists(template_path):
            logger.warning(f"Template file not found: {template_path}")
            return None
            
        try:
            with open(template_path, 'r') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading template {template_path}: {str(e)}")
            return None
    
    def _send_email(self, to_list: List[str], cc_list: List[str], subject: str, html_content: str) -> bool:
        """Send email using SMTP"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_address
            msg['To'] = ', '.join(to_list)
            
            if cc_list:
                msg['Cc'] = ', '.join(cc_list)
                recipients = to_list + cc_list
            else:
                recipients = to_list
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.smtp_user and self.smtp_password:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_password)
                
                server.sendmail(self.from_address, recipients, msg.as_string())
                
            logger.info(f"Sent email alert to {', '.join(recipients)}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False