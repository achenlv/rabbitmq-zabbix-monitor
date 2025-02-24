import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any

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
    config_path = os.getenv('CONFIG_PATH', 'config/config.json')
    with open(config_path, 'r') as f:
      self._config = json.load(f)

  @property
  def config(self) -> Dict[str, Any]:
    return self._config

  def get_rabbitmq_config(self) -> Dict[str, Any]:
    return self._config['rabbitmq']

  def get_zabbix_config(self) -> Dict[str, Any]:
    return self._config['zabbix']

  def get_email_config(self) -> Dict[str, Any]:
    return self._config['email']

  def get_monitoring_config(self) -> Dict[str, Any]:
    return self._config['monitoring']

config = ConfigLoader()