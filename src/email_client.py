import smtplib
from email.mime.text import MIMEText

class EmailClient:
  def __init__(self, mail_server, mail_from, mail_to, mail_cc=None):
    self.mail_server = mail_server
    self.mail_from = mail_from
    self.mail_to = mail_to
    self.mail_cc = mail_cc

  def send_email(self, subject, body):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = self.mail_from
    msg['To'] = self.mail_to
    if self.mail_cc:
      msg['Cc'] = self.mail_cc

    recipients = [self.mail_to]
    if self.mail_cc:
      recipients.append(self.mail_cc)

    with smtplib.SMTP(self.mail_server) as server:
      server.sendmail(self.mail_from, recipients, msg.as_string())

  def read_template(self, template_path, context):
    with open(template_path, 'r') as file:
      template = file.read()
    return template.format(**context)