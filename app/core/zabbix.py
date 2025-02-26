import os
import subprocess
import json
import tempfile
from typing import Dict, List, Any, Optional
import requests
from requests.auth import HTTPBasicAuth

class ZabbixClient:
  def __init__(self, config: Dict):
    self.config = config.get('zabbix', {})
    self.url = self.config.get('url')
    self.api_url = f"{self.url}/api_jsonrpc.php" if self.url else None
    self.user = self.config.get('user')
    self.password = self.config.get('password')
    self.token = self.config.get('token')
    self.server = self.config.get('server')
    self.port = self.config.get('port', 10051)
    
    # TLS/PSK settings
    self.tls_connect = self.config.get('tls_connect')
    self.tls_psk_identity = self.config.get('tls_psk_identity')
    self.tls_psk_file = self.config.get('tls_psk_file')
    self.tls_psk_file_linux = self.config.get('tls_psk_file_linux')
    self.psk_key = self.config.get('psk_key')
    
    # Authentication token
    self._auth = None
    
  def _get_psk_file_path(self) -> Optional[str]:
    """
    Get a valid PSK file path for the current environment.
    Will create a temporary PSK file if the configured file doesn't exist.
    """
    # Check if the configured PSK file exists
    if self.tls_psk_file and os.path.exists(self.tls_psk_file):
      return self.tls_psk_file
    
    # Check Linux path if on Linux
    if self.tls_psk_file_linux and os.path.exists(self.tls_psk_file_linux):
      return self.tls_psk_file_linux
    
    # If neither exist but we have a PSK key in config, create a temp file
    if self.psk_key:
      try:
        # Create a temporary PSK file
        tmp_dir = tempfile.gettempdir()
        tmp_psk_path = os.path.join(tmp_dir, 'zabbix_psk.key')
        
        with open(tmp_psk_path, 'w') as f:
          f.write(self.psk_key)
        
        # Make sure file permissions are secure
        os.chmod(tmp_psk_path, 0o600)
        
        return tmp_psk_path
      except Exception as e:
        print(f"Failed to create temporary PSK file: {str(e)}")
    
    return None
  
  def authenticate(self) -> Optional[str]:
    """Authenticate with Zabbix API and get auth token"""
    if not self.api_url:
      return None
      
    if self.token:
      self._auth = self.token
      return self.token
    
    payload = {
      "jsonrpc": "2.0",
      "method": "user.login",
      "params": {
        "user": self.user,
        "password": self.password
      },
      "id": 1
    }
    
    try:
      response = requests.post(self.api_url, json=payload)
      response.raise_for_status()
      data = response.json()
      
      if "result" in data:
        self._auth = data["result"]
        return self._auth
      
      return None
    except Exception as e:
      print(f"Authentication error: {str(e)}")
      return None
  
  def api_call(self, method: str, params: Dict) -> Dict:
    """Make a call to the Zabbix API"""
    if not self._auth:
      self.authenticate()
      
    if not self._auth:
      return {"error": "Not authenticated"}
    
    payload = {
      "jsonrpc": "2.0",
      "method": method,
      "params": params,
      "auth": self._auth,
      "id": 1
    }
    
    try:
      response = requests.post(self.api_url, json=payload)
      response.raise_for_status()
      return response.json()
    except Exception as e:
      return {"error": f"API call failed: {str(e)}"}
  
  def get_host(self, hostname: str) -> Dict:
    """Get host information from Zabbix"""
    params = {
      "filter": {
        "host": [hostname]
      },
      "output": ["hostid", "host", "name"]
    }
    
    return self.api_call("host.get", params)
  
  def send_value(self, hostname: str, key: str, value: Any) -> Dict:
    """
    Send a value to Zabbix using zabbix_sender with PSK authentication
    """
    # Create a temporary file for the data
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
      temp_file.write(f"{hostname} {key} {value}")
      temp_file_path = temp_file.name
    
    # Build the command
    cmd = ["zabbix_sender",
           "-z", self.server,
           "-p", str(self.port),
           "-i", temp_file_path]
    
    # Add TLS options if configured
    if self.tls_connect == "psk":
      psk_file_path = self._get_psk_file_path()
      
      if not psk_file_path:
        os.unlink(temp_file_path)  # Clean up data file
        return {
          "success": False, 
          "error": "PSK file not found and could not create temporary PSK file"
        }
      
      cmd.extend([
        "--tls-connect", "psk",
        "--tls-psk-identity", self.tls_psk_identity,
        "--tls-psk-file", psk_file_path
      ])
    
    try:
      # Execute the command
      process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      stdout, stderr = process.communicate()
      
      # Clean up the temporary file
      os.unlink(temp_file_path)
      
      if process.returncode == 0:
        return {"success": True, "message": stdout.decode('utf-8')}
      else:
        return {"success": False, "error": stderr.decode('utf-8')}
    except Exception as e:
      # Clean up the temporary file
      if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)
      return {"success": False, "error": str(e)}
  
  def send_values_to_zabbix(self, data_points: List[Dict]) -> Dict:
    """
    Send multiple values to Zabbix
    data_points: List of dictionaries with keys: host, key, value
    """
    # Create a temporary file for the data
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
      for point in data_points:
        temp_file.write(f"{point['host']} {point['key']} {point['value']}\n")
      temp_file_path = temp_file.name
    
    # Build the command
    cmd = ["zabbix_sender",
           "-z", self.server,
           "-p", str(self.port),
           "-i", temp_file_path]
    
    # Add TLS options if configured
    if self.tls_connect == "psk":
      psk_file_path = self._get_psk_file_path()
      
      if not psk_file_path:
        os.unlink(temp_file_path)  # Clean up data file
        return {
          "success": False, 
          "error": "PSK file not found and could not create temporary PSK file"
        }
      
      cmd.extend([
        "--tls-connect", "psk",
        "--tls-psk-identity", self.tls_psk_identity,
        "--tls-psk-file", psk_file_path
      ])
    
    try:
      # Execute the command
      process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      stdout, stderr = process.communicate()
      
      # Clean up the temporary file
      os.unlink(temp_file_path)
      
      if process.returncode == 0:
        return {"success": True, "message": stdout.decode('utf-8')}
      else:
        return {"success": False, "error": stderr.decode('utf-8')}
    except Exception as e:
      # Clean up the temporary file
      if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)
      return {"success": False, "error": str(e)}