import json
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigLoader:
  _instance = None
  _config = None

  def __new__(cls):
    if cls._instance is None:
      cls._instance = super().__new__(cls)
    return cls._instance

  def __init__(self):
    if self._config is None:
      self.load_config()

  def load_config(self):
    """Load configuration from JSON file"""
    config_path = os.getenv('CONFIG_PATH', 'config/config.json')
    try:
      with open(config_path, 'r') as f:
        self._config = json.load(f)
      logger.info(f"Configuration loaded from {config_path}")
    except Exception as e:
      logger.error(f"Error loading configuration from {config_path}: {str(e)}")
      # Initialize with empty config
      self._config = {}

  def reload_config(self):
    """Reload configuration from file"""
    self._config = None
    self.load_config()
    return self._config

  @property
  def config(self) -> Dict[str, Any]:
    """Get the entire configuration dictionary"""
    return self._config

  def get_app_config(self) -> Dict[str, Any]:
    """Get the application configuration"""
    return self._config.get('app', {})

  def get_rabbitmq_config(self) -> Dict[str, Any]:
    """Get the RabbitMQ configuration"""
    return self._config.get('rabbitmq', {'clusters': []})

  def get_zabbix_config(self) -> Dict[str, Any]:
    """Get the Zabbix configuration"""
    return self._config.get('zabbix', {})

  def get_email_config(self) -> Dict[str, Any]:
    """Get the email configuration"""
    return self._config.get('email', {})

  def get_monitoring_config(self) -> Dict[str, Any]:
    """Get the monitoring configuration"""
    return self._config.get('monitoring', {'queues': []})

config = ConfigLoader()