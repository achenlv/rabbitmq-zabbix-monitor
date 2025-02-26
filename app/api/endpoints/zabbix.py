from flask import Blueprint, jsonify, request
from app.core.config import Config
from app.core.zabbix import ZabbixClient

bp = Blueprint('zabbix', __name__, url_prefix='/api/zabbix')

# Initialize configuration
config = Config()
zabbix_client = ZabbixClient(config.get_config())

@bp.route('/hosts', methods=['GET'])
def get_hosts():
  """Get Zabbix hosts"""
  params = {
    "output": ["hostid", "host", "name", "status"]
  }
  
  result = zabbix_client.api_call("host.get", params)
  
  if "error" in result:
    return jsonify(result), 400
  
  return jsonify(result.get("result", []))

@bp.route('/hosts/<hostname>', methods=['GET'])
def get_host(hostname):
  """Get a specific Zabbix host"""
  result = zabbix_client.get_host(hostname)
  
  if "error" in result:
    return jsonify(result), 400
  
  if not result.get("result"):
    return jsonify({"error": "Host not found"}), 404
  
  return jsonify(result.get("result", [])[0])

@bp.route('/send', methods=['POST', 'GET'])
def send_value():
  """Send a value to Zabbix - supports both query params and JSON body"""
  # Try to get data from JSON body first
  data = request.json or {}
  
  # Fall back to query parameters if JSON is empty or not provided
  hostname = data.get('host') or request.args.get('host')
  key = data.get('key') or request.args.get('key')
  value = data.get('value') or request.args.get('value')
  
  if not all([hostname, key, value is not None]):
    return jsonify({"error": "Missing required fields: host, key, value"}), 400
  
  result = zabbix_client.send_value(hostname, key, value)
  
  if not result.get("success", False):
    return jsonify(result), 400
  
  return jsonify(result)

@bp.route('/send-batch', methods=['POST'])
def send_batch():
  """Send multiple values to Zabbix"""
  data = request.json
  
  if not data or not isinstance(data, list):
    return jsonify({"error": "Expected a list of data points"}), 400
  
  for point in data:
    if not all([point.get('host'), point.get('key'), point.get('value') is not None]):
      return jsonify({"error": "Each data point must have host, key, and value"}), 400
  
  result = zabbix_client.send_values_to_zabbix(data)
  
  if not result.get("success", False):
    return jsonify(result), 400
  
  return jsonify(result)