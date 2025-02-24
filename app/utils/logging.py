import logging
import os
from flask import current_app, request, redirect
from werkzeug.local import LocalProxy
from logging.handlers import RotatingFileHandler

def get_log_dir():
  try:
    return current_app.config['LOG_DIR']
  except RuntimeError:
    return 'log'

class RequestFormatter(logging.Formatter):
  """
  Add remote address to log record in formatted log output.
  """
  def format(self, record):
    record.remote_addr = request.remote_addr if request else 'N/A'
    return super().format(record)

def setup_logging():
  log_dir = get_log_dir()

  os.makedirs(log_dir, exist_ok=True)

  formatter = RequestFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(remote_addr)s - %(message)s'
  )

  file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'api.log'),
    maxBytes=10485760,  # 10MB
    backupCount=5
  )

  file_handler.setFormatter(formatter)
  
  # Iestata konsoles apstrādātāju
  console_handler = logging.StreamHandler()
  console_handler.setFormatter(formatter)
  
  # Konfigurē saknes žurnālu
  root_logger = logging.getLogger()
  root_logger.setLevel(logging.INFO)
  
  # Noņem esošos apstrādātājus, ja tādi ir
  root_logger.handlers.clear()
  
  # Pievieno apstrādātājus
  root_logger.addHandler(file_handler)
  root_logger.addHandler(console_handler)
  
  # Apspiež werkzeug žurnālu veidošanu
  logging.getLogger('werkzeug').setLevel(logging.WARNING)
  
  return root_logger