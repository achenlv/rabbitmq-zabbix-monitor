from typing import Dict, List, Any, Optional
from app.core.rabbitmq import RabbitMQClient
from app.core.zabbix import ZabbixClient
from app.core.notification import NotificationClient

class MonitoringService:
  def __init__(self, config: Dict):
    self.config = config
    self.monitoring_config = config.get('monitoring', {})
    self.threshold = self.monitoring_config.get('threshold', 1000)
    self.queues = self.monitoring_config.get('queues', [])
    
    # Initialize clients
    self.rabbitmq_client = RabbitMQClient(config)
    self.zabbix_client = ZabbixClient(config)
    self.notification_client = NotificationClient(config)
  
  def get_node_from_queue_config(self, queue_config: Dict) -> Optional[Dict]:
    """Get node information for a queue configuration"""
    cluster_node = queue_config.get('cluster_node')
    
    # Find the cluster this node belongs to
    for cluster in self.config.get('rabbitmq', {}).get('clusters', []):
      for node in cluster.get('nodes', []):
        if node.get('hostname') == cluster_node:
          return {
            'cluster_id': cluster.get('id'),
            'node': node
          }
    
    return None
  
  def collect_queue_metrics(self) -> List[Dict]:
    """
    Collect metrics for all configured queues
    
    Returns:
        List of queue metric data points
    """
    results = []
    
    for queue_config in self.queues:
      cluster_node = queue_config.get('cluster_node')
      vhost = queue_config.get('vhost')
      queue_name = queue_config.get('queue')
      zabbix_host = queue_config.get('zabbix_host')
      
      if not all([cluster_node, vhost, queue_name, zabbix_host]):
        continue
      
      # Get node info to find cluster ID
      node_info = self.get_node_from_queue_config(queue_config)
      if not node_info:
        continue
      
      # Get queue info from RabbitMQ
      queue_info = self.rabbitmq_client.get_queue_info(
        node_info['cluster_id'], 
        vhost, 
        queue_name
      )
      
      if "error" in queue_info:
        continue
      
      # Extract metrics
      messages = queue_info.get('messages', 0)
      consumers = queue_info.get('consumers', 0)
      state = queue_info.get('state', 'unknown')
      
      # Create data points for Zabbix
      results.append({
        'host': zabbix_host,
        'metrics': {
          'queue.messages': messages,
          'queue.consumers': consumers,
          'queue.state': 1 if state == 'running' else 0
        },
        'queue_info': {
          'vhost': vhost,
          'queue': queue_name,
          'messages': messages,
          'consumers': consumers,
          'state': state
        }
      })
    
    return results
  
  def send_metrics_to_zabbix(self, metrics: List[Dict]) -> Dict:
    """
    Send collected metrics to Zabbix
    
    Args:
        metrics: List of metric data points
        
    Returns:
        Dict with success status and results
    """
    zabbix_data_points = []
    alert_data = []
    
    for metric in metrics:
      host = metric.get('host')
      queue_info = metric.get('queue_info', {})
      
      # Add data points for Zabbix
      for key, value in metric.get('metrics', {}).items():
        # Create a key specific to this queue
        item_key = f"rabbitmq.{queue_info.get('vhost')}.{queue_info.get('queue')}.{key}"
        zabbix_data_points.append({
          'host': host,
          'key': item_key,
          'value': value
        })
      
      # Check thresholds for alerting
      messages = queue_info.get('messages', 0)
      if messages > self.threshold:
        alert_data.append({
          'type': 'threshold',
          'queue_info': queue_info
        })
    
    # Send data to Zabbix
    result = self.zabbix_client.send_values_to_zabbix(zabbix_data_points)
    
    # Send alerts if needed
    for alert in alert_data:
      self.notification_client.send_alert(
        alert.get('type'), 
        alert.get('queue_info')
      )
    
    return result
  
  def run_monitoring_cycle(self) -> Dict:
    """
    Run a complete monitoring cycle:
    1. Collect metrics from RabbitMQ
    2. Send metrics to Zabbix
    3. Send alerts if thresholds are exceeded
    
    Returns:
        Dict with results of the monitoring cycle
    """
    metrics = self.collect_queue_metrics()
    result = self.send_metrics_to_zabbix(metrics)
    
    return {
      'metrics_collected': len(metrics),
      'zabbix_result': result,
      'success': result.get('success', False)
    }

  def collect_all_queue_metrics(self) -> List[Dict]:
    """
    Collect metrics for ALL queues on ALL vhosts on ALL clusters
    
    Returns:
        List of queue metric data points
    """
    results = []
    
    # Iterate through all clusters
    for cluster in self.config.get('rabbitmq', {}).get('clusters', []):
      cluster_id = cluster.get('id')
      
      # Skip clusters without monitoring enabled
      if not cluster.get('monitoring', {}).get('enabled', False):
        continue
      
      # Get default Zabbix host for this cluster
      default_zabbix_host = cluster.get('monitoring', {}).get('default_zabbix_host')
      
      # Get all queues from this cluster
      all_queues = self.rabbitmq_client.get_all_queues(cluster_id)
      
      # Skip if there was an error
      if isinstance(all_queues, dict) and "error" in all_queues:
        continue
      
      # Process each queue
      for queue_info in all_queues:
        vhost = queue_info.get('vhost', '')
        queue_name = queue_info.get('name', '')
        
        # Find the correct Zabbix host
        zabbix_host = default_zabbix_host
        
        # Try to find a specific mapping for this queue in the config
        for q_config in self.monitoring_config.get('queues', []):
          if (q_config.get('vhost') == vhost and 
              q_config.get('queue') == queue_name):
            zabbix_host = q_config.get('zabbix_host', zabbix_host)
            break
        
        # If we don't have a Zabbix host, skip this queue
        if not zabbix_host:
          continue
        
        # Extract metrics
        messages = queue_info.get('messages', 0)
        consumers = queue_info.get('consumers', 0)
        state = queue_info.get('state', 'unknown')
        
        # Create data points for Zabbix with the required key format
        results.append({
          'host': zabbix_host,
          'metrics': {
            f'rabbitmq.test.queue.size[{vhost},{queue_name}]': messages,
            f'rabbitmq.test.queue.consumers[{vhost},{queue_name}]': consumers,
            f'rabbitmq.test.queue.state[{vhost},{queue_name}]': 1 if state == 'running' else 0
          },
          'queue_info': {
            'vhost': vhost,
            'queue': queue_name,
            'messages': messages,
            'consumers': consumers,
            'state': state
          }
        })
    
    return results

  def send_all_metrics_to_zabbix(self) -> Dict:
    """
    Collect and send ALL metrics from ALL queues to Zabbix
    
    Returns:
        Dict with success status and results
    """
    # Collect all metrics
    metrics = self.collect_all_queue_metrics()
    
    # Prepare data for Zabbix
    zabbix_data_points = []
    alert_data = []
    
    for metric in metrics:
      host = metric.get('host')
      queue_info = metric.get('queue_info', {})
      
      # Add data points for Zabbix
      for key, value in metric.get('metrics', {}).items():
        zabbix_data_points.append({
          'host': host,
          'key': key,
          'value': value
        })
      
      # Check thresholds for alerting
      messages = queue_info.get('messages', 0)
      if messages > self.threshold:
        alert_data.append({
          'type': 'threshold',
          'queue_info': queue_info
        })
    
    # Send data to Zabbix
    result = self.zabbix_client.send_values_to_zabbix(zabbix_data_points)
    
    # Send alerts if needed
    for alert in alert_data:
      self.notification_client.send_alert(
        alert.get('type'), 
        alert.get('queue_info')
      )
    
    return {
      'metrics_collected': len(metrics),
      'data_points_sent': len(zabbix_data_points),
      'zabbix_result': result,
      'success': result.get('success', False)
    }  