# tests/test_rabbitmq.py
import sys
import os
import logging
import unittest
from unittest.mock import patch, MagicMock
from app.utils.config import config
from app.core.rabbitmq import RabbitMQClient

# Setup logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TestRabbitMQClient(unittest.TestCase):
    """Test cases for the RabbitMQClient class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a sample configuration for testing
        self.test_config = {
            'rabbitmq': {
                'clusters': [
                    {
                        'id': 'test-cluster',
                        'description': 'Test Cluster',
                        'nodes': [
                            {
                                'hostname': 'rabbitmq-test-01.example.com',
                                'api_port': 15672,
                                'primary': True
                            },
                            {
                                'hostname': 'rabbitmq-test-02.example.com',
                                'api_port': 15672
                            }
                        ],
                        'auth': {
                            'user': 'test-user',
                            'password': 'test-password'
                        }
                    }
                ]
            }
        }
        
        # Create the client with the test configuration
        self.client = RabbitMQClient(self.test_config)
    
    def test_get_cluster_by_id(self):
        """Test getting a cluster by ID"""
        # Test with valid cluster ID
        cluster = self.client.get_cluster_by_id('test-cluster')
        self.assertIsNotNone(cluster)
        self.assertEqual(cluster['id'], 'test-cluster')
        self.assertEqual(cluster['description'], 'Test Cluster')
        
        # Test with invalid cluster ID
        cluster = self.client.get_cluster_by_id('non-existent-cluster')
        self.assertIsNone(cluster)
    
    def test_get_node_info(self):
        """Test getting node information"""
        # Test with valid node
        node_info = self.client.get_node_info('test-cluster', 'rabbitmq-test-01.example.com')
        self.assertIsNotNone(node_info)
        self.assertEqual(node_info['hostname'], 'rabbitmq-test-01.example.com')
        self.assertEqual(node_info['api_port'], 15672)
        self.assertTrue(node_info['primary'])
        
        # Test with invalid node
        node_info = self.client.get_node_info('test-cluster', 'non-existent-node')
        self.assertIsNone(node_info)
        
        # Test with invalid cluster
        node_info = self.client.get_node_info('non-existent-cluster', 'rabbitmq-test-01.example.com')
        self.assertIsNone(node_info)
    
    def test_get_auth_for_cluster(self):
        """Test getting authentication credentials for a cluster"""
        # Test with valid cluster
        user, password = self.client.get_auth_for_cluster('test-cluster')
        self.assertEqual(user, 'test-user')
        self.assertEqual(password, 'test-password')
        
        # Test with invalid cluster
        user, password = self.client.get_auth_for_cluster('non-existent-cluster')
        self.assertIsNone(user)
        self.assertIsNone(password)
    
    def test_get_primary_node(self):
        """Test getting the primary node for a cluster"""
        # Test with valid cluster
        primary_node = self.client.get_primary_node('test-cluster')
        self.assertIsNotNone(primary_node)
        self.assertEqual(primary_node['hostname'], 'rabbitmq-test-01.example.com')
        self.assertTrue(primary_node['primary'])
        
        # Test with invalid cluster
        primary_node = self.client.get_primary_node('non-existent-cluster')
        self.assertIsNone(primary_node)
    
    @patch('app.core.rabbitmq.requests.get')
    def test_get_queue_info(self, mock_get):
        """Test getting information about a specific queue"""
        # Mock the response from the RabbitMQ API
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'name': 'test-queue',
            'vhost': '/',
            'durable': True,
            'auto_delete': False,
            'exclusive': False,
            'messages': 42,
            'consumers': 2,
            'state': 'running'
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test with valid parameters
        queue_info = self.client.get_queue_info('test-cluster', '/', 'test-queue')
        self.assertIsNotNone(queue_info)
        self.assertEqual(queue_info['name'], 'test-queue')
        self.assertEqual(queue_info['messages'], 42)
        self.assertEqual(queue_info['consumers'], 2)
        self.assertEqual(queue_info['state'], 'running')
        
        # Verify the API call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs['auth'], ('test-user', 'test-password'))
        self.assertTrue('rabbitmq-test-01.example.com:15672/api/queues/' in args[0])
    
    @patch('app.core.rabbitmq.requests.get')
    def test_get_all_queues(self, mock_get):
        """Test getting all queues from a cluster"""
        # Mock the response from the RabbitMQ API
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                'name': 'queue1',
                'vhost': '/',
                'messages': 10,
                'consumers': 1,
                'state': 'running'
            },
            {
                'name': 'queue2',
                'vhost': 'test',
                'messages': 20,
                'consumers': 2,
                'state': 'running'
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test with valid cluster
        queues = self.client.get_all_queues('test-cluster')
        self.assertIsNotNone(queues)
        self.assertEqual(len(queues), 2)
        self.assertEqual(queues[0]['name'], 'queue1')
        self.assertEqual(queues[1]['name'], 'queue2')
        
        # Verify the API call was made correctly
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs['auth'], ('test-user', 'test-password'))
        self.assertTrue('rabbitmq-test-01.example.com:15672/api/queues' in args[0])

def test_rabbitmq_client_with_config():
    """Test the RabbitMQ client with the actual configuration"""
    try:
        # Get RabbitMQ configuration
        rabbitmq_config = config.get_rabbitmq_config()
        
        logger.info(f"Found {len(rabbitmq_config.get('clusters', []))} clusters in config")
        
        # Create client with full config
        full_config = {'rabbitmq': rabbitmq_config}
        client = RabbitMQClient(full_config)
        
        # Test each cluster
        for cluster in rabbitmq_config.get('clusters', []):
            cluster_id = cluster.get('id', 'unknown')
            logger.info(f"Testing cluster: {cluster_id}")
            
            try:
                # Get primary node
                primary_node = client.get_primary_node(cluster_id)
                if primary_node:
                    logger.info(f"Primary node for cluster {cluster_id}: {primary_node['hostname']}")
                    
                    # Get all queues
                    queues = client.get_all_queues(cluster_id)
                    if isinstance(queues, list):
                        logger.info(f"Found {len(queues)} queues in cluster {cluster_id}")
                    else:
                        logger.error(f"Error getting queues: {queues.get('error', 'Unknown error')}")
                else:
                    logger.error(f"No primary node found for cluster {cluster_id}")
                
            except Exception as e:
                logger.error(f"Error testing cluster {cluster_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in test: {str(e)}")

if __name__ == "__main__":
    # Run the unit tests
    unittest.main()
    
    # Alternatively, run the integration test with actual config
    # test_rabbitmq_client_with_config()
