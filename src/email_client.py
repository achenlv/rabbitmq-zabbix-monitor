class EmailClient:
  def __init__(self, mail_server, mail_from, mail_to):
    self.mail_server = mail_server
    self.mail_from = mail_from
    self.mail_to = mail_to

  def send_email(self, subject, body):
    import smtplib
    from email.mime.text import MIMEText

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = self.mail_from
    msg['To'] = self.mail_to

    with smtplib.SMTP(self.mail_server) as server:
      server.sendmail(self.mail_from, [self.mail_to], msg.as_string())