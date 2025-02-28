import os
import json
from typing import Dict, Any, Optional

class Config:
  def __init__(self, config_path: str = "config/config.json"):
    self.config_path = config_path
    self._config = self._load_config()
  
  def _load_config(self) -> Dict:
    """Load configuration from file"""
    try:
      with open(self.config_path, 'r') as f:
        return json.load(f)
    except Exception as e:
      print(f"Error loading configuration: {str(e)}")
      return {}
  
  def get_config(self) -> Dict:
    """Get the entire configuration"""
    return self._config
  
  def get(self, section: str, default: Any = None) -> Any:
    """Get a specific section of the configuration"""
    return self._config.get(section, default)