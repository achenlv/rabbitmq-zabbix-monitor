import requests
from typing import Dict, Any
from app.utils.config import config

class RabbitMQClient:
  def __init__(self, cluster_node: str):
    self.cluster_config = self._get_cluster_config(cluster_node)
    self.base_url = f"http://{cluster_node}:{self.cluster_config['port']}/api"
    self.auth = (self.cluster_config['user'], self.cluster_config['password'])

  def _get_cluster_config(self, cluster_node: str) -> Dict[str, Any]:
    clusters = config.get_rabbitmq_config()['clusters']
    cluster = next(
      (c for c in clusters if cluster_node in c['nodes']), 
      None
    )
    if not cluster:
      raise ValueError(f"No configuration found for cluster node: {cluster_node}")
    return cluster

  def get_queue_info(self, vhost: str, queue: str) -> Dict[str, Any]:
    url = f"{self.base_url}/queues/{vhost}/{queue}"
    response = requests.get(url, auth=self.auth)
    response.raise_for_status()
    return response.json()