import requests
import json
from typing import Dict, List, Any, Optional, Tuple


class RabbitMQClient:
  def __init__(self, config: Dict):
    self.config = config
    self.clusters = config.get('rabbitmq', {}).get('clusters', [])
    
  def get_cluster_by_id(self, cluster_id: str) -> Optional[Dict]:
    """Get cluster config by its ID"""
    for cluster in self.clusters:
      if cluster.get('id') == cluster_id:
        return cluster
    return None
  
  def get_node_info(self, cluster_id: str, node_hostname: str) -> Optional[Dict]:
    """Get specific node info from a cluster"""
    cluster = self.get_cluster_by_id(cluster_id)
    if not cluster:
      return None
      
    for node in cluster.get('nodes', []):
      if node.get('hostname') == node_hostname:
        return node
    return None
  
  def get_auth_for_cluster(self, cluster_id: str) -> Tuple[str, str]:
    """Get auth credentials for a cluster"""
    cluster = self.get_cluster_by_id(cluster_id)
    if not cluster:
      return None, None
      
    auth = cluster.get('auth', {})
    return auth.get('user'), auth.get('password')
  
  def get_primary_node(self, cluster_id: str) -> Optional[Dict]:
    """Get primary node for a cluster"""
    cluster = self.get_cluster_by_id(cluster_id)
    if not cluster:
      return None
      
    for node in cluster.get('nodes', []):
      if node.get('primary', False):
        return node
    # If no primary specified, return first node
    if cluster.get('nodes'):
      return cluster.get('nodes')[0]
    return None
  
  def get_queue_info(self, cluster_id: str, vhost: str, queue_name: str) -> Dict:
    """
    Get information about a specific queue in a RabbitMQ cluster
    """
    node = self.get_primary_node(cluster_id)
    if not node:
      return {"error": "Cluster not found or no nodes available"}
      
    user, password = self.get_auth_for_cluster(cluster_id)
    if not user or not password:
      return {"error": "Auth information not available"}
    
    # URL encode vhost for API call
    import urllib.parse
    encoded_vhost = urllib.parse.quote(vhost, safe='')
    
    api_url = f"http://{node['hostname']}:{node['api_port']}/api/queues/{encoded_vhost}/{queue_name}"
    
    try:
      response = requests.get(api_url, auth=(user, password))
      response.raise_for_status()
      return response.json()
    except requests.exceptions.RequestException as e:
      return {"error": f"Failed to get queue info: {str(e)}"}
  
  def get_all_queues(self, cluster_id: str) -> List[Dict]:
    """
    Get all queues from a RabbitMQ cluster
    """
    node = self.get_primary_node(cluster_id)
    if not node:
      return {"error": "Cluster not found or no nodes available"}
      
    user, password = self.get_auth_for_cluster(cluster_id)
    if not user or not password:
      return {"error": "Auth information not available"}
    
    api_url = f"http://{node['hostname']}:{node['api_port']}/api/queues"
    
    try:
      response = requests.get(api_url, auth=(user, password))
      response.raise_for_status()
      return response.json()
    except requests.exceptions.RequestException as e:
      return {"error": f"Failed to get all queues: {str(e)}"}