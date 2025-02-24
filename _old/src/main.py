#!/usr/bin/env python3
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

from config import Config
from rabbitmq_client import RabbitMQClient
from zabbix_client import ZabbixClient
from email_sender import EmailSender
from utils import setup_logging, get_alert_key

logger = logging.getLogger(__name__)

class QueueMonitor:
    def __init__(self, config_path: str):
        self.config = Config(config_path)
        self.rabbitmq_clients = {}  # Dictionary to store RabbitMQ clients for each cluster
        self._initialize_rabbitmq_clients()
        self.zabbix = ZabbixClient(self.config)
        self.email = EmailSender(self.config)
        self.sent_alerts = set()  # Track sent alerts to prevent duplicates
        
    def _initialize_rabbitmq_clients(self):
        """Initialize RabbitMQ clients for each cluster"""
        for cluster_config in self.config.get_rabbitmq_clusters():
            client = RabbitMQClient(cluster_config)
            for node in cluster_config['nodes']:
                self.rabbitmq_clients[node] = client

    def _get_rabbitmq_client(self, node: str) -> Optional[RabbitMQClient]:
        """Get the appropriate RabbitMQ client for a given node"""
        return self.rabbitmq_clients.get(node)
        
    def process_queue_metrics(self, vhost: str, queue: str, count: int, cluster_node: str):
        """Process queue metrics and handle alerts"""
        item_key = f"rabbitmq.test.queue.size[{vhost},{queue}]"
        
        # Ensure Zabbix item exists
        if not self.zabbix.item_exists(cluster_node, item_key):
            self.zabbix.create_item(cluster_node, item_key)
            
        # Get previous value
        prev_count = self.zabbix.get_last_value(cluster_node, item_key)
        
        # Update Zabbix
        self.zabbix.send_value(cluster_node, item_key, count)
        
        # Check if this is a monitored queue
        monitored_queue = self.config.get_monitored_queue(vhost, queue, cluster_node)
        if monitored_queue:
            if prev_count is not None and count > prev_count:
                logger.warning(
                    f"Queue size increase detected: {vhost}/{queue} on {cluster_node} "
                    f"from {prev_count} to {count}"
                )
                
                # Generate unique alert key
                alert_key = get_alert_key(cluster_node, vhost, queue)
                
                # Only send alert if we haven't sent one for this instance
                if alert_key not in self.sent_alerts:
                    context = {
                        "node": cluster_node,
                        "vhost": vhost,
                        "queue": queue,
                        "previous_count": prev_count,
                        "current_count": count,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Send drift alert
                    self.email.send_drift_alert(context)
                    self.sent_alerts.add(alert_key)
                    
                    # Send threshold alert if count exceeds threshold
                    threshold = self.config.get_threshold()
                    if count > threshold:
                        self.email.send_threshold_alert(context)
            else:
                # Reset alert tracking if queue size has decreased
                alert_key = get_alert_key(cluster_node, vhost, queue)
                self.sent_alerts.discard(alert_key)

    def _check_queue(self, cluster_node: str, vhost: str, queue: str) -> Optional[int]:
        """Check queue message count with failover support"""
        client = self._get_rabbitmq_client(cluster_node)
        if not client:
            logger.error(f"No RabbitMQ client found for node {cluster_node}")
            return None

        try:
            return client.get_queue_message_count(cluster_node, vhost, queue)
        except Exception as e:
            logger.error(f"Failed to get queue metrics from {cluster_node}: {str(e)}")
            return None

    def run(self):
        """Main monitoring loop"""
        try:
            for monitored_queue in self.config.get_monitored_queues():
                cluster_node = monitored_queue['cluster_node']
                vhost = monitored_queue['vhost']
                queue = monitored_queue['queue']
                zabbix_host = monitored_queue['zabbix_host']
                
                count = self._check_queue(cluster_node, vhost, queue)
                if count is not None:
                    logger.info(f"Processing {cluster_node} {vhost}/{queue}: {count} messages")
                    self.process_queue_metrics(vhost, queue, count, zabbix_host)
                        
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")
            sys.exit(1)

def main():
    setup_logging()
    monitor = QueueMonitor(os.path.join(os.path.dirname(__file__), '../config/config.json'))
    monitor.run()

if __name__ == "__main__":
    main()