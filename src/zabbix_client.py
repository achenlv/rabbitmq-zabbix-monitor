from pyzabbix import ZabbixAPI, ZabbixMetric, ZabbixSender

class ZabbixClient:
  def __init__(self, server, username, password):
    self.zapi = ZabbixAPI(server)
    self.zapi.login(username, password)

  def create_trapper_item(self, host_name, item_key, item_name):
    """
    Create a trapper item for a given host
    """
    host_id = self.get_host_id(host_name)
    if not host_id:
      raise ValueError(f"Host '{host_name}' not found.")
    
    item = self.zapi.item.create(
      hostid=host_id,
      name=item_name,
      key_=item_key,
      type=2,  # Zabbix trapper
      value_type=3  # Numeric unsigned
    )
    return item

  def get_host_id(self, host_name):
    """
    Get the host id for a given host name
    """
    hosts = self.zapi.host.get(filter={"host": host_name})
    if hosts:
      return hosts[0]['hostid']
    return None

  def set_trapper_item_value(self, host_name, item_key, item_value):
    """
    Send data to Zabbix server using ZabbixSender.
    """
    metrics = [ZabbixMetric(host_name, item_key, item_value)]
    zbx = ZabbixSender(self.zapi.url)
    result = zbx.send(metrics)
    return result

  def check_trigger(self, trigger_name):
    """
    Check if a trigger exists by name
    """
    triggers = self.zapi.trigger.get(filter={"description": trigger_name})
    return triggers

  def get_last_item_value(self, item_id, limit=1):
    """
    Get the last value of an item
    """
    history = self.zapi.history.get(
      history=3,
      itemids=item_id,
      sortfield="clock",
      sortorder="DESC",
      limit=limit
    )
    if history:
      return [h['value'] for h in history]
    return []

  def get_event_details(self, host, trigger_id):
    """
    Get event details for a given host and trigger
    """
    events = self.zapi.event.get(
      hostids=host,
      objectids=trigger_id,
      sortfield="clock",
      sortorder="DESC",
      limit=1,
      selectTags="extend"
    )
    if events:
      return events[0]
    return None

  def get_trigger_details(self, trigger_id):
    """
    Get trigger details by trigger ID
    """
    triggers = self.zapi.trigger.get(
      triggerids=trigger_id,
      selectHosts=["host"],
      selectItems=["itemid"],
      selectTags="extend"
    )
    if triggers:
      return triggers[0]
    return None

  def get_item_id(self, host, key):
    """
    Get the item ID for a given host and key.
    """
    items = self.zapi.item.get(filter={"host": host, "key_": key})
    if items:
      return items[0]['itemid']
    return None

  def send_data(self, host, key, value):
    """
    Send data to Zabbix server using ZabbixSender.
    """
    item_id = self.get_item_id(host, key)
    if not item_id:
      self.create_trapper_item(host, key, f"Item for {key}")
      item_id = self.get_item_id(host, key)
    
    metrics = [ZabbixMetric(host, key, value)]
    zbx = ZabbixSender(self.zapi.url)
    result = zbx.send(metrics)
    return result

  def get_drift_from_last_values(self, item_id):
    """
    Get the drift from the last and previous values of a Zabbix item
    """
    values = self.get_last_item_value(item_id, limit=2)
    if len(values) < 2:
      return None
    return float(values[0]) - float(values[1])