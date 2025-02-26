import os
import subprocess
import json
import tempfile
import platform
import shutil
from typing import Dict, List, Any, Optional

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
  
  def _find_zabbix_sender(self) -> Optional[str]:
    """Find the zabbix_sender executable"""
    # Check if it's in the PATH
    zabbix_sender_path = shutil.which("zabbix_sender")
    if zabbix_sender_path:
      return zabbix_sender_path
      
    # Common locations
    if platform.system() == "Windows":
      for path in [
        r"C:\Program Files\Zabbix Agent\zabbix_sender.exe",
        r"C:\Program Files\Zabbix Agent 2\zabbix_sender.exe",
        r"C:\zabbix\bin\zabbix_sender.exe"
      ]:
        if os.path.exists(path):
          return path
    else:  # Linux/Mac
      for path in [
        "/usr/bin/zabbix_sender",
        "/usr/local/bin/zabbix_sender",
        "/usr/local/sbin/zabbix_sender"
      ]:
        if os.path.exists(path):
          return path
    
    return None
  
  def _get_psk_file_path(self) -> Optional[str]:
    """Get the path to the PSK file"""
    # Check Windows/default path first
    if self.tls_psk_file and os.path.exists(self.tls_psk_file):
      return self.tls_psk_file
    
    # Check Linux path if on Linux
    if platform.system() != "Windows" and self.tls_psk_file_linux and os.path.exists(self.tls_psk_file_linux):
      return self.tls_psk_file_linux
    
    # Return the configured path even if it doesn't exist
    # This allows zabbix_sender to report the specific error
    if platform.system() != "Windows" and self.tls_psk_file_linux:
      return self.tls_psk_file_linux
    else:
      return self.tls_psk_file
  
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
      import requests
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
      import requests
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
    # Find zabbix_sender
    zabbix_sender_path = self._find_zabbix_sender()
    if not zabbix_sender_path:
      return {"success": False, "error": "zabbix_sender not found in PATH or common locations"}
    
    # Build the command
    cmd = [
      zabbix_sender_path,
      "-z", self.server,
      "-p", str(self.port),
      "-s", hostname,
      "-k", key,
      "-o", str(value)
    ]
    
    # Add TLS options if configured
    if self.tls_connect == "psk":
      psk_file_path = self._get_psk_file_path()
      
      cmd.extend([
        "--tls-connect", "psk",
        "--tls-psk-identity", self.tls_psk_identity,
        "--tls-psk-file", psk_file_path
      ])
    
    try:
      # Print the command (for debugging)
      print(f"Executing: {' '.join(cmd)}")
      
      # Execute the command
      process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      stdout, stderr = process.communicate()
      
      stdout_str = stdout.decode('utf-8')
      stderr_str = stderr.decode('utf-8')
      
      # If we have a stderr message, that's an error
      if stderr_str and stderr_str.strip():
        return {
          "success": False, 
          "error": stderr_str,
          "command": " ".join(cmd)
        }
      
      # If we have stdout but no stderr, consider it a success
      # even if the return code is non-zero
      return {
        "success": True,
        "message": stdout_str,
        "command": " ".join(cmd),
        "returncode": process.returncode
      }
    except Exception as e:
      return {"success": False, "error": str(e)}
  
  def send_values_to_zabbix(self, data_points: List[Dict]) -> Dict:
    """
    Send multiple values to Zabbix
    data_points: List of dictionaries with keys: host, key, value
    """
    if not data_points:
      return {"success": True, "message": "No data points to send"}
    
    # For multiple points, use the batch file method
    # Create a temporary file for the data
    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as temp_file:
      for point in data_points:
        temp_file.write(f"{point['host']} {point['key']} {point['value']}\n")
      temp_file_path = temp_file.name
    
    # Find zabbix_sender
    zabbix_sender_path = self._find_zabbix_sender()
    if not zabbix_sender_path:
      os.unlink(temp_file_path)  # Clean up
      return {"success": False, "error": "zabbix_sender not found in PATH or common locations"}
    
    # Build the command
    cmd = [
      zabbix_sender_path,
      "-z", self.server,
      "-p", str(self.port),
      "-i", temp_file_path
    ]
    
    # Add TLS options if configured
    if self.tls_connect == "psk":
      psk_file_path = self._get_psk_file_path()
      
      cmd.extend([
        "--tls-connect", "psk",
        "--tls-psk-identity", self.tls_psk_identity,
        "--tls-psk-file", psk_file_path
      ])
    
    try:
      # Print the command (for debugging)
      print(f"Executing: {' '.join(cmd)}")
      
      # Execute the command
      process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      stdout, stderr = process.communicate()
      
      # Clean up the temporary file
      os.unlink(temp_file_path)
      
      stdout_str = stdout.decode('utf-8')
      stderr_str = stderr.decode('utf-8')
      
      # If we have a stderr message, that's an error
      if stderr_str and stderr_str.strip():
        return {
          "success": False, 
          "error": stderr_str,
          "command": " ".join(cmd)
        }
      
      # If we have stdout but no stderr, consider it a success
      # even if the return code is non-zero (zabbix_sender can be picky)
      return {
        "success": True,
        "message": stdout_str,
        "command": " ".join(cmd),
        "returncode": process.returncode
      }
    except Exception as e:
      # Clean up the temporary file
      if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)
      return {"success": False, "error": str(e)}
    
  def get_item_history(self, hostname: str, key: str, limit: int = 2) -> List[Dict]:
    """
    Get the most recent values for a specific item from Zabbix
    
    Args:
        hostname: The host name in Zabbix
        key: The item key
        limit: Number of historical values to retrieve (default: 2)
        
    Returns:
        List of dictionaries with historical values, newest first
    """
    if not self._auth:
      self.authenticate()
      
    if not self._auth:
      return []
    
    # First, get the host ID
    host_result = self.get_host(hostname)
    if not host_result.get("result"):
      return []
    
    host_id = host_result.get("result")[0].get("hostid")
    
    # Then, get the item ID
    item_params = {
      "output": ["itemid", "key_", "lastvalue", "prevvalue"],
      "hostids": host_id,
      "filter": {
        "key_": key
      }
    }
    
    item_result = self.api_call("item.get", item_params)
    if not item_result.get("result"):
      return []
    
    item_id = item_result.get("result")[0].get("itemid")
    
    # Get the history type (0 = numeric float, 3 = numeric unsigned)
    item_type = item_result.get("result")[0].get("value_type", 3)
    
    # Get the history
    history_params = {
      "output": "extend",
      "history": item_type,
      "itemids": item_id,
      "sortfield": "clock",
      "sortorder": "DESC",
      "limit": limit
    }
    
    history_result = self.api_call("history.get", history_params)
    
    if not history_result.get("result"):
      # If no history, use the lastvalue and prevvalue from item.get
      item = item_result.get("result")[0]
      return [
        {
          "value": item.get("lastvalue"),
          "clock": "latest"
        },
        {
          "value": item.get("prevvalue"),
          "clock": "previous"
        }
      ]
    
    return history_result.get("result", [])