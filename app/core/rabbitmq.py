import logging
import requests
from typing import Dict, Optional, List, Any
from urllib.parse import quote
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

class RabbitMQClient:
  def __init__(self, cluster_config: Dict[str, Any]):
    """Initialize RabbitMQ client with cluster configuration"""
    self.cluster_id = cluster_config.get('id', 'unknown')
    self.description = cluster_config.get('description', 'Unknown Cluster')
    
    # Extract nodes information
    self.node_configs = cluster_config.get('nodes', [])
    if not self.node_configs:
        raise ValueError(f"No nodes defined for cluster {self.cluster_id}")
        
    # Get hostnames of all nodes
    self.nodes = [node['hostname'] for node in self.node_configs]
    
    # Get primary node or default to first node
    primary_nodes = [n for n in self.node_configs if n.get('primary', False)]
    self.primary_node = primary_nodes[0] if primary_nodes else self.node_configs[0]
    
    # Extract authentication details
    auth_config = cluster_config.get('auth', {})
    self.user = auth_config.get('user', 'guest')
    self.password = auth_config.get('password', 'guest')
    
    # Default API port from primary node
    self.port = self.primary_node.get('api_port', 15672)
    
    # Setup HTTP session
    self.session = requests.Session()
    self.session.auth = (self.user, self.password)
    self.session.headers.update({'Content-Type': 'application/json'})
    
    # Setup monitoring info
    monitoring_config = cluster_config.get('monitoring', {})
    self.monitoring_enabled = monitoring_config.get('enabled', False)
    self.default_zabbix_host = monitoring_config.get('default_zabbix_host', '')
    
    # Initialize current node index for failover
    self._current_node_index = 0
    
    logger.info(f"Initialized RabbitMQ client for cluster {self.cluster_id} with {len(self.nodes)} nodes")
  
  def _get_next_node(self) -> str:
    """Get next available node using round-robin"""
    node = self.nodes[self._current_node_index]
    self._current_node_index = (self._current_node_index + 1) % len(self.nodes)
    return node
  
  def _get_node_config(self, hostname: str) -> Dict[str, Any]:
    """Get configuration for a specific node by hostname"""
    for node in self.node_configs:
      if node['hostname'] == hostname:
          return node
    raise ValueError(f"Node {hostname} not found in cluster {self.cluster_id}")
  
  def _make_request(self, method: str, path: str, node: Optional[str] = None,
                    **kwargs) -> Optional[Dict]:
    """Make HTTP request to RabbitMQ API with failover support"""
    errors = []
    tried_nodes = set()
    
    # If specific node requested, try it first
    if node:
      try:
        node_config = self._get_node_config(node)
        api_port = node_config.get('api_port', self.port)
        url = f"http://{node}:{api_port}/api/{path}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
      except Exception as e:
        errors.append(f"Failed to connect to specified node {node}: {str(e)}")
        tried_nodes.add(node)
    
    # Try other nodes if specific node failed or wasn't specified
    while len(tried_nodes) < len(self.nodes):
      try:
        current_node = self._get_next_node()
        if current_node in tried_nodes:
          continue
        
        node_config = self._get_node_config(current_node)
        api_port = node_config.get('api_port', self.port)
        url = f"http://{current_node}:{api_port}/api/{path}"
        
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
      except Exception as e:
        errors.append(f"Failed to connect to node {current_node}: {str(e)}")
        tried_nodes.add(current_node)
      
    # All nodes failed
    error_msg = "\n".join(errors)
    logger.error(f"Failed to connect to any RabbitMQ node:\n{error_msg}")
    raise RequestException(f"All RabbitMQ nodes are unavailable:\n{error_msg}")
  
  def get_queue_message_count(self, node: str, vhost: str, queue: str) -> Optional[int]:
    """Get message count for specific queue"""
    try:
      encoded_vhost = quote(vhost, safe='')
      encoded_queue = quote(queue, safe='')
      path = f"queues/{encoded_vhost}/{encoded_queue}"
      
      queue_data = self._make_request('GET', path, node)
      
      if queue_data and 'messages' in queue_data:
        return queue_data['messages']
      else:
        logger.error(f"Invalid queue data received for {vhost}/{queue}")
        return None
              
    except Exception as e:
      logger.error(f"Failed to get queue message count for {vhost}/{queue}: {str(e)}")
      return None
  
  def check_node_health(self, node: str) -> bool:
    """Check if a specific node is healthy"""
    try:
      path = "healthchecks/node"
      self._make_request('GET', path, node)
      return True
    except Exception as e:
      logger.error(f"Health check failed for node {node}: {str(e)}")
      return False
  
  def get_cluster_status(self) -> Dict:
    """Get cluster status information"""
    try:
      return self._make_request('GET', 'cluster-name')
    except Exception as e:
      logger.error(f"Failed to get cluster status: {str(e)}")
      return {}
  
  def get_queues(self, vhost: Optional[str] = None) -> List[Dict]:
    """Get all queues, optionally filtered by vhost"""
    try:
      path = "queues"
      if vhost:
        encoded_vhost = quote(vhost, safe='')
        path = f"queues/{encoded_vhost}"
          
      return self._make_request('GET', path) or []
    except Exception as e:
      logger.error(f"Failed to get queues: {str(e)}")
      return []
  
  def get_node_info(self, node: str) -> Dict:
    """Get detailed information about a node"""
    try:
      encoded_node = quote(node, safe='')
      path = f"nodes/{encoded_node}"
      return self._make_request('GET', path, node) or {}
    except Exception as e:
      logger.error(f"Failed to get node info for {node}: {str(e)}")
      return {}
  
  def get_zabbix_host_for_node(self, node: str) -> str:
    """Get the Zabbix hostname associated with a RabbitMQ node"""
    try:
      node_config = self._get_node_config(node)
      return node_config.get('zabbix_host', self.default_zabbix_host)
    except Exception as e:
      logger.error(f"Failed to get Zabbix host for node {node}: {str(e)}")
      return self.default_zabbix_host
    
  def get_vhosts(self) -> List[Dict]:
    """Get all virtual hosts from the cluster"""
    try:
        return self._make_request('GET', 'vhosts') or []
    except Exception as e:
        logger.error(f"Failed to get vhosts: {str(e)}")
        return []

  def get_queues_in_vhost(self, vhost: Optional[str] = None) -> List[Dict]:
    """Get all queues in a specific vhost or across all vhosts"""
    try:
        if vhost:
            encoded_vhost = quote(vhost, safe='')
            path = f"queues/{encoded_vhost}"
            return self._make_request('GET', path) or []
        else:
            # Get all queues across all vhosts
            return self._make_request('GET', 'queues') or []
    except Exception as e:
        logger.error(f"Failed to get queues: {str(e)}")
        return []

  def get_messages_ready_count(self, vhost: Optional[str] = None, queue: Optional[str] = None) -> Dict:
    """
    Get messages_ready count for one queue, all queues in a vhost, or all queues
    
    Returns a dictionary with queue names as keys and message counts as values
    """
    result = {}
    
    try:
        # Case 1: Specific queue in specific vhost
        if vhost and queue:
            encoded_vhost = quote(vhost, safe='')
            encoded_queue = quote(queue, safe='')
            path = f"queues/{encoded_vhost}/{encoded_queue}"
            
            queue_data = self._make_request('GET', path)
            if queue_data and 'messages_ready' in queue_data:
                result[f"{vhost}/{queue}"] = queue_data['messages_ready']
                
        # Case 2: All queues in specific vhost
        elif vhost:
            encoded_vhost = quote(vhost, safe='')
            path = f"queues/{encoded_vhost}"
            
            queues = self._make_request('GET', path) or []
            for q in queues:
                queue_name = q.get('name', 'unknown')
                if 'messages_ready' in q:
                    result[f"{vhost}/{queue_name}"] = q['messages_ready']
                    
        # Case 3: All queues in all vhosts
        else:
            queues = self._make_request('GET', 'queues') or []
            for q in queues:
                vhost_name = q.get('vhost', 'unknown')
                queue_name = q.get('name', 'unknown')
                if 'messages_ready' in q:
                    result[f"{vhost_name}/{queue_name}"] = q['messages_ready']
                    
        return result
    except Exception as e:
        logger.error(f"Failed to get messages_ready count: {str(e)}")
        return {}    