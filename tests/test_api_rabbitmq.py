# tests/test_api_rabbitmq.py
import unittest
from unittest.mock import patch, MagicMock
import json
from flask import Flask
from app.api import api
from app.api.endpoints.rabbitmq import rabbitmq_ns, ClusterList, Cluster, QueueList, Queue
from app.core.rabbitmq import RabbitMQClient

class TestRabbitMQAPI(unittest.TestCase):
    """Test cases for the RabbitMQ API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a Flask app
        self.app = Flask(__name__)
        api.init_app(self.app)
        
        # Create a test client
        self.client = self.app.test_client()
        
        # Sample configuration for testing
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
        
        # Sample queue data for testing
        self.test_queues = [
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
        
        # Sample queue info for testing
        self.test_queue_info = {
            'name': 'test-queue',
            'vhost': '/',
            'messages': 42,
            'consumers': 2,
            'state': 'running',
            'durable': True,
            'auto_delete': False,
            'exclusive': False
        }
    
    @patch('app.api.endpoints.rabbitmq.config')
    def test_list_clusters(self, mock_config):
        """Test listing all RabbitMQ clusters"""
        # Mock the config.get method
        mock_config.get.return_value = self.test_config['rabbitmq']
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], 'test-cluster')
        self.assertEqual(data[0]['description'], 'Test Cluster')
        self.assertEqual(len(data[0]['nodes']), 2)
        self.assertNotIn('auth', data[0])  # Auth should be removed
    
    @patch('app.api.endpoints.rabbitmq.rabbitmq_client')
    def test_get_cluster(self, mock_client):
        """Test getting a specific RabbitMQ cluster"""
        # Mock the get_cluster_by_id method
        mock_client.get_cluster_by_id.return_value = self.test_config['rabbitmq']['clusters'][0]
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters/test-cluster')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['id'], 'test-cluster')
        self.assertEqual(data['description'], 'Test Cluster')
        self.assertEqual(len(data['nodes']), 2)
        
        # Verify the client was called correctly
        mock_client.get_cluster_by_id.assert_called_once_with('test-cluster')
    
    @patch('app.api.endpoints.rabbitmq.rabbitmq_client')
    def test_get_cluster_not_found(self, mock_client):
        """Test getting a non-existent RabbitMQ cluster"""
        # Mock the get_cluster_by_id method to return None
        mock_client.get_cluster_by_id.return_value = None
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters/non-existent')
        
        # Verify the response
        self.assertEqual(response.status_code, 404)
        
        # Verify the client was called correctly
        mock_client.get_cluster_by_id.assert_called_once_with('non-existent')
    
    @patch('app.api.endpoints.rabbitmq.rabbitmq_client')
    def test_list_queues(self, mock_client):
        """Test listing all queues for a cluster"""
        # Mock the get_all_queues method
        mock_client.get_all_queues.return_value = self.test_queues
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters/test-cluster/queues')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], 'queue1')
        self.assertEqual(data[0]['vhost'], '/')
        self.assertEqual(data[0]['messages'], 10)
        self.assertEqual(data[1]['name'], 'queue2')
        self.assertEqual(data[1]['vhost'], 'test')
        self.assertEqual(data[1]['messages'], 20)
        
        # Verify the client was called correctly
        mock_client.get_all_queues.assert_called_once_with('test-cluster')
    
    @patch('app.api.endpoints.rabbitmq.rabbitmq_client')
    def test_list_queues_error(self, mock_client):
        """Test listing queues with an error"""
        # Mock the get_all_queues method to return an error
        mock_client.get_all_queues.return_value = {"error": "Connection failed"}
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters/test-cluster/queues')
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was called correctly
        mock_client.get_all_queues.assert_called_once_with('test-cluster')
    
    @patch('app.api.endpoints.rabbitmq.rabbitmq_client')
    def test_get_queue(self, mock_client):
        """Test getting information about a specific queue"""
        # Mock the get_queue_info method
        mock_client.get_queue_info.return_value = self.test_queue_info
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters/test-cluster/queues/%2F/test-queue')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'test-queue')
        self.assertEqual(data['vhost'], '/')
        self.assertEqual(data['messages'], 42)
        self.assertEqual(data['consumers'], 2)
        self.assertEqual(data['state'], 'running')
        
        # Verify the client was called correctly
        mock_client.get_queue_info.assert_called_once_with('test-cluster', '/', 'test-queue')
    
    @patch('app.api.endpoints.rabbitmq.rabbitmq_client')
    def test_get_queue_error(self, mock_client):
        """Test getting queue information with an error"""
        # Mock the get_queue_info method to return an error
        mock_client.get_queue_info.return_value = {"error": "Queue not found"}
        
        # Make a request to the API
        response = self.client.get('/api/rabbitmq/clusters/test-cluster/queues/%2F/non-existent')
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was called correctly
        mock_client.get_queue_info.assert_called_once_with('test-cluster', '/', 'non-existent')

if __name__ == "__main__":
    unittest.main()
