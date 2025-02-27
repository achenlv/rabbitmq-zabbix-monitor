from flask import request
from app.core.config import Config
from app.core.zabbix import ZabbixClient
from flask_restx import Resource, fields
from app.api import zabbix_ns, zabbix_data_point, api

# Initialize configuration
config = Config()
zabbix_client = ZabbixClient(config.get_config())

# Define Zabbix-specific models
host_model = zabbix_ns.model('Host', {
  'hostid': fields.String(description='Host ID'),
  'host': fields.String(description='Host name'),
  'name': fields.String(description='Visible name'),
  'status': fields.Integer(description='Host status')
})

result_model = zabbix_ns.model('Result', {
  'success': fields.Boolean(description='Operation success status'),
  'message': fields.String(description='Result message or error')
})

@zabbix_ns.route('/hosts')
class HostList(Resource):
  @zabbix_ns.doc('list_hosts')
  @zabbix_ns.marshal_list_with(host_model)
  def get(self):
    """Get Zabbix hosts"""
    params = {
      "output": ["hostid", "host", "name", "status"]
    }
    
    result = zabbix_client.api_call("host.get", params)
    
    if "error" in result:
      zabbix_ns.abort(400, result["error"])
    
    return result.get("result", [])

@zabbix_ns.route('/hosts/<hostname>')
@zabbix_ns.param('hostname', 'The host name')
class Host(Resource):
  @zabbix_ns.doc('get_host')
  @zabbix_ns.marshal_with(host_model)
  def get(self, hostname):
    """Get a specific Zabbix host"""
    result = zabbix_client.get_host(hostname)
    
    if "error" in result:
      zabbix_ns.abort(400, result["error"])
    
    if not result.get("result"):
      zabbix_ns.abort(404, "Host not found")
    
    return result.get("result", [])[0]

@zabbix_ns.route('/send')
class SendValue(Resource):
  @zabbix_ns.doc('send_value')
  @zabbix_ns.expect(zabbix_data_point)
  @zabbix_ns.marshal_with(result_model)
  def post(self):
    """Send a value to Zabbix"""
    data = request.json or {}
    
    # Fall back to query parameters if JSON is empty or not provided
    hostname = data.get('host') or request.args.get('host')
    key = data.get('key') or request.args.get('key')
    value = data.get('value') or request.args.get('value')
    
    if not all([hostname, key, value is not None]):
      zabbix_ns.abort(400, "Missing required fields: host, key, value")
    
    result = zabbix_client.send_value(hostname, key, value)
    
    if not result.get("success", False):
      zabbix_ns.abort(400, result.get("error", "Unknown error"))
    
    return result
  
  @zabbix_ns.doc('send_value_get')
  @zabbix_ns.param('host', 'Zabbix host name')
  @zabbix_ns.param('key', 'Item key')
  @zabbix_ns.param('value', 'Item value')
  @zabbix_ns.marshal_with(result_model)
  def get(self):
    """Send a value to Zabbix (GET method for compatibility)"""
    hostname = request.args.get('host')
    key = request.args.get('key')
    value = request.args.get('value')
    
    if not all([hostname, key, value is not None]):
      zabbix_ns.abort(400, "Missing required parameters: host, key, value")
    
    result = zabbix_client.send_value(hostname, key, value)
    
    if not result.get("success", False):
      zabbix_ns.abort(400, result.get("error", "Unknown error"))
    
    return result

@zabbix_ns.route('/send-batch')
class SendBatch(Resource):
  @zabbix_ns.doc('send_batch')
  @zabbix_ns.expect([zabbix_data_point])
  @zabbix_ns.marshal_with(result_model)
  def post(self):
    """Send multiple values to Zabbix"""
    data = request.json
    
    if not data or not isinstance(data, list):
      zabbix_ns.abort(400, "Expected a list of data points")
    
    for point in data:
      if not all([point.get('host'), point.get('key'), point.get('value') is not None]):
        zabbix_ns.abort(400, "Each data point must have host, key, and value")
    
    result = zabbix_client.send_values_to_zabbix(data)
    
    if not result.get("success", False):
      zabbix_ns.abort(400, result.get("error", "Unknown error"))
    
    return result