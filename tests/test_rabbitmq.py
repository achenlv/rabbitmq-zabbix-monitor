# test_rabbitmq.py
import sys
import os
import logging
from app.utils.config import config
from app.core.rabbitmq import RabbitMQClient

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_rabbitmq_client():
    """Test the RabbitMQ client with the new configuration"""
    try:
        # Get RabbitMQ configuration
        rabbitmq_config = config.get_rabbitmq_config()
        
        logger.info(f"Found {len(rabbitmq_config.get('clusters', []))} clusters in config")
        
        # Test each cluster
        for cluster in rabbitmq_config.get('clusters', []):
            cluster_id = cluster.get('id', 'unknown')
            logger.info(f"Testing cluster: {cluster_id}")
            
            try:
                # Create client
                client = RabbitMQClient(cluster)
                logger.info(f"Created client for cluster {cluster_id} with {len(client.nodes)} nodes")
                
                # Test connection to primary node
                primary_node = client.primary_node['hostname']
                logger.info(f"Testing connection to primary node: {primary_node}")
                
                is_healthy = client.check_node_health(primary_node)
                logger.info(f"Node {primary_node} health: {'OK' if is_healthy else 'FAILED'}")
                
                # Try to get cluster name
                cluster_name = client.get_cluster_status()
                logger.info(f"Cluster name: {cluster_name.get('name', 'unknown')}")
                
                # Get queues
                queues = client.get_queues()
                logger.info(f"Found {len(queues)} queues in cluster {cluster_id}")
                
            except Exception as e:
                logger.error(f"Error testing cluster {cluster_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")

if __name__ == "__main__":
    test_rabbitmq_client()