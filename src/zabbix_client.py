import requests


class ZabbixClient:
  def __init__(self, server, user, password):
    self.server = server
    self.user = user
    self.password = password
    self.auth_token = self.authenticate()

  def authenticate(self):
    url = f"{self.server}/api_jsonrpc"
    headers = {'Content-Type': 'application/json'}
    payload = {
      "jsonrpc": "2.0",
      "method": "user.login",
      "params": {
        "user": self.user,
        "password": self.password
      },
      "id": 1
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json().get('result')

  def set_trapper_item(self, host_name, item_key, item_value):
    url = f"{self.server}/api_jsonrpc"
    headers = {'Content-Type': 'application/json'}
    payload = {
      "jsonrpc": "2.0",
      "method": "item.create",
      "params": {
        "name": f"Item for {item_key}",
        "key_": item_key,
        "host": host_name,
        "type": 2,  # Zabbix trapper
        "value_type": 3  # Numeric (unsigned)
      },
      "auth": self.auth_token,
      "id": 1
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()

  def check_trigger(self, trigger_name):
    url = f"{self.server}/api_jsonrpc"
    headers = {'Content-Type': 'application/json'}
    payload = {
      "jsonrpc": "2.0",
      "method": "trigger.get",
      "params": {
        "output": "extend",
        "filter": {
          "description": trigger_name
        }
    },
      "auth": self.auth_token,
      "id": 1
    }
    response = requests.post(url, json=payload, headers=headers)
    return response.json()