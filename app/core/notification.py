import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
from string import Template

class NotificationClient:
  def __init__(self, config: Dict):
    self.config = config.get('email', {})
    self.smtp_server = self.config.get('smtp_server')
    self.smtp_port = self.config.get('smtp_port', 25)
    self.smtp_user = self.config.get('smtp_user')
    self.smtp_password = self.config.get('smtp_password')
    self.from_address = self.config.get('from_address')
    self.templates = self.config.get('templates', {})
    self.alerts = self.config.get('alerts', {})
  
  def _load_template(self, template_name: str) -> Optional[Template]:
    """Load an email template from file"""
    template_path = self.templates.get(template_name)
    if not template_path:
      return None
      
    try:
      with open(template_path, 'r') as file:
        return Template(file.read())
    except Exception as e:
      print(f"Error loading template {template_path}: {str(e)}")
      return None
  
  def send_alert(self, alert_type: str, context: Dict) -> Dict:
    """
    Send an alert email
    
    Args:
        alert_type: Type of alert (drift, threshold, error)
        context: Dictionary of values to substitute in the template
        
    Returns:
        Dict with success status and message
    """
    if alert_type not in self.alerts:
      return {"success": False, "error": f"Unknown alert type: {alert_type}"}
    
    alert_config = self.alerts[alert_type]
    template_name = alert_config.get('template')
    subject_template = alert_config.get('subject', '')
    to_addresses = alert_config.get('to', [])
    cc_addresses = alert_config.get('cc', [])
    
    if not to_addresses:
      return {"success": False, "error": "No recipients specified"}
    
    # Load the email template
    template = self._load_template(template_name)
    if not template:
      return {"success": False, "error": f"Failed to load template: {template_name}"}
    
    # Create the email
    msg = MIMEMultipart()
    msg['From'] = self.from_address
    msg['To'] = ', '.join(to_addresses)
    if cc_addresses:
      msg['Cc'] = ', '.join(cc_addresses)
    
    # Format the subject
    try:
      subject = subject_template.format(**context)
    except Exception:
      subject = subject_template
    msg['Subject'] = subject
    
    # Format the email body
    try:
      body = template.substitute(**context)
    except Exception as e:
      return {"success": False, "error": f"Error formatting template: {str(e)}"}
    
    msg.attach(MIMEText(body, 'html'))
    
    # Send the email
    try:
      smtp = smtplib.SMTP(self.smtp_server, self.smtp_port)
      
      if self.smtp_user and self.smtp_password:
        smtp.login(self.smtp_user, self.smtp_password)
      
      all_recipients = to_addresses + cc_addresses
      smtp.sendmail(self.from_address, all_recipients, msg.as_string())
      smtp.quit()
      
      return {"success": True, "message": f"Alert sent to {', '.join(all_recipients)}"}
    except Exception as e:
      return {"success": False, "error": f"Failed to send email: {str(e)}"}