import json
from typing import Dict, List, Optional

class Config:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def get_rabbitmq_clusters(self) -> List[Dict]:
        return self.config['rabbitmq']['clusters']

    def get_zabbix_config(self) -> Dict:
        return self.config['zabbix']

    def get_monitored_queues(self) -> List[Dict]:
        return self.config['monitoring']['queues']

    def get_monitored_queue(self, vhost: str, queue: str, cluster_node: str) -> Optional[Dict]:
        for q in self.get_monitored_queues():
            if (q['vhost'] == vhost and q['queue'] == queue and q['cluster_node'] == cluster_node):
                return q
        return None

    def get_threshold(self) -> int:
        return self.config['monitoring'].get('threshold', 15)

    def get_email_config(self) -> Dict:
        return self.config['email']
