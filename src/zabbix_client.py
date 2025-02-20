import requests


class ZabbixClient:
  def __init__(self, server, username, password):
    self.server = server
    self.username = username
    self.password = password
    self.auth_token = self.authenticate()

  def authenticate(self):
    url = f"{self.server}/api_jsonrpc.php"
    headers = {'Content-Type': 'application/json'}
    payload = {
      "jsonrpc": "2.0",
      "method": "user.login",
      "params": {
        "username": self.username,
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
  
  def get_last_item_value(self, item_id):
    url = f"{self.server}/api_jsonrpc.php"
    headers = {'Content-Type': 'application/json'}
    payload = {
      "jsonrpc": "2.0",
      "method": "history.get",
      "params": {
        "output": "extend",
        "history": 3,
        "itemids": item_id,
        "sortfield": "clock",
        "sortorder": "DESC",
        "limit": 1
      },
      "auth": self.auth_token,
      "id": 1
    }
    response = requests.post(url, json=payload, headers=headers)
    result = response.json().get('result')
    if result:
      return int(result[0]['value'])
    return 0

  def get_event_details(self, event_id):
    url = f"{self.server}/api_jsonrpc.php"
    headers = {'Content-Type': 'application/json'}
    payload = {
      "jsonrpc": "2.0",
      "method": "event.get",
      "params": {
        "output": "extend",
        "eventids": event_id,
        "selectTags": "extend"
      },
      "auth": self.auth_token,
      "id": 1
    }
    response = requests.post(url, json=payload, headers=headers)
    print(f"Response from get_event_details: {response.json()}")
    result = response.json().get('result')
    if result:
      return result[0]
    return None