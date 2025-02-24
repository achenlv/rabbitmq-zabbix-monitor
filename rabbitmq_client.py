import logging
import requests
from typing import Dict, Optional
from urllib.parse import quote
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

class RabbitMQClient:
    def __init__(self, cluster_config: Dict):
        self.nodes = cluster_config['nodes']
        self.user = cluster_config['user']
        self.password = cluster_config['password']
        self.port = cluster_config['port']
        self.session = requests.Session()
        self.session.auth = (self.user, self.password)
        self.session.headers.update({'Content-Type': 'application/json'})
        self._current_node_index = 0

    def _get_next_node(self) -> str:
        node = self.nodes[self._current_node_index]
        self._current_node_index = (self._current_node_index + 1) % len(self.nodes)
        return node

    def _make_request(self, method: str, path: str, node: Optional[str] = None, **kwargs) -> Optional[Dict]:
        errors = []
        tried_nodes = set()

        if node:
            try:
                url = f"http://{node}:{self.port}/api/{path}"
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                errors.append(f"Failed to connect to specified node {node}: {str(e)}")
                tried_nodes.add(node)

        while len(tried_nodes) < len(self.nodes):
            try:
                current_node = self._get_next_node()
                if current_node in tried_nodes:
                    continue

                url = f"http://{current_node}:{self.port}/api/{path}"
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()

            except Exception as e:
                errors.append(f"Failed to connect to node {current_node}: {str(e)}")
                tried_nodes.add(current_node)

        error_msg = "\n".join(errors)
        logger.error(f"Failed to connect to any RabbitMQ node:\n{error_msg}")
        raise RequestException(f"All RabbitMQ nodes are unavailable:\n{error_msg}")

    def get_queue_message_count(self, node: str, vhost: str, queue: str) -> Optional[int]:
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
        try:
            path = "healthcheck"
            self._make_request('GET', path, node)
            return True
        except Exception:
            return False

    def get_cluster_status(self) -> Dict:
        try:
            return self._make_request('GET', 'cluster-name')
        except Exception as e:
            logger.error(f"Failed to get cluster status: {str(e)}")
            return {}
