# tests/test_api_zabbix.py
import unittest
from unittest.mock import patch, MagicMock
import json
from flask import Flask
from app.api import api
from app.api.endpoints.zabbix import zabbix_ns, HostList, Host, SendValue, SendBatch
from app.core.zabbix import ZabbixClient

class TestZabbixAPI(unittest.TestCase):
    """Test cases for the Zabbix API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a Flask app
        self.app = Flask(__name__)
        api.init_app(self.app)
        
        # Create a test client
        self.client = self.app.test_client()
        
        # Sample host data for testing
        self.test_hosts = [
            {
                'hostid': '10084',
                'host': 'rabbitmq-test',
                'name': 'RabbitMQ Test',
                'status': 0
            },
            {
                'hostid': '10085',
                'host': 'rabbitmq-prod',
                'name': 'RabbitMQ Production',
                'status': 0
            }
        ]
        
        # Sample host info for testing
        self.test_host_info = {
            'hostid': '10084',
            'host': 'rabbitmq-test',
            'name': 'RabbitMQ Test',
            'status': 0
        }
        
        # Sample send value result for testing
        self.test_send_result = {
            'success': True,
            'message': 'Processed: 1; Failed: 0; Total: 1; seconds spent: 0.000055',
            'command': 'zabbix_sender -z zabbix-server.example.com -p 10051 -s rabbitmq-test -k rabbitmq.test.queue.size[/,test-queue] -o 42',
            'returncode': 0
        }
        
        # Sample send batch result for testing
        self.test_send_batch_result = {
            'success': True,
            'message': 'Processed: 2; Failed: 0; Total: 2; seconds spent: 0.000128',
            'command': 'zabbix_sender -z zabbix-server.example.com -p 10051 -i /tmp/tmpfile123456',
            'returncode': 0
        }
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_list_hosts(self, mock_client):
        """Test listing all Zabbix hosts"""
        # Mock the api_call method
        mock_client.api_call.return_value = {'result': self.test_hosts}
        
        # Make a request to the API
        response = self.client.get('/api/zabbix/hosts')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['hostid'], '10084')
        self.assertEqual(data[0]['host'], 'rabbitmq-test')
        self.assertEqual(data[1]['hostid'], '10085')
        self.assertEqual(data[1]['host'], 'rabbitmq-prod')
        
        # Verify the client was called correctly
        mock_client.api_call.assert_called_once()
        args, kwargs = mock_client.api_call.call_args
        self.assertEqual(args[0], 'host.get')
        self.assertEqual(kwargs['params']['output'], ['hostid', 'host', 'name', 'status'])
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_list_hosts_error(self, mock_client):
        """Test listing hosts with an error"""
        # Mock the api_call method to return an error
        mock_client.api_call.return_value = {'error': 'API call failed'}
        
        # Make a request to the API
        response = self.client.get('/api/zabbix/hosts')
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was called correctly
        mock_client.api_call.assert_called_once()
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_get_host(self, mock_client):
        """Test getting a specific Zabbix host"""
        # Mock the get_host method
        mock_client.get_host.return_value = {'result': [self.test_host_info]}
        
        # Make a request to the API
        response = self.client.get('/api/zabbix/hosts/rabbitmq-test')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['hostid'], '10084')
        self.assertEqual(data['host'], 'rabbitmq-test')
        self.assertEqual(data['name'], 'RabbitMQ Test')
        
        # Verify the client was called correctly
        mock_client.get_host.assert_called_once_with('rabbitmq-test')
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_get_host_error(self, mock_client):
        """Test getting a host with an error"""
        # Mock the get_host method to return an error
        mock_client.get_host.return_value = {'error': 'API call failed'}
        
        # Make a request to the API
        response = self.client.get('/api/zabbix/hosts/rabbitmq-test')
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was called correctly
        mock_client.get_host.assert_called_once_with('rabbitmq-test')
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_get_host_not_found(self, mock_client):
        """Test getting a non-existent host"""
        # Mock the get_host method to return an empty result
        mock_client.get_host.return_value = {'result': []}
        
        # Make a request to the API
        response = self.client.get('/api/zabbix/hosts/non-existent')
        
        # Verify the response
        self.assertEqual(response.status_code, 404)
        
        # Verify the client was called correctly
        mock_client.get_host.assert_called_once_with('non-existent')
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_value_post(self, mock_client):
        """Test sending a value to Zabbix via POST"""
        # Mock the send_value method
        mock_client.send_value.return_value = self.test_send_result
        
        # Make a request to the API
        response = self.client.post('/api/zabbix/send', json={
            'host': 'rabbitmq-test',
            'key': 'rabbitmq.test.queue.size[/,test-queue]',
            'value': 42
        })
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Processed: 1; Failed: 0; Total: 1; seconds spent: 0.000055')
        
        # Verify the client was called correctly
        mock_client.send_value.assert_called_once_with('rabbitmq-test', 'rabbitmq.test.queue.size[/,test-queue]', 42)
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_value_get(self, mock_client):
        """Test sending a value to Zabbix via GET"""
        # Mock the send_value method
        mock_client.send_value.return_value = self.test_send_result
        
        # Make a request to the API
        response = self.client.get('/api/zabbix/send?host=rabbitmq-test&key=rabbitmq.test.queue.size[/,test-queue]&value=42')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Processed: 1; Failed: 0; Total: 1; seconds spent: 0.000055')
        
        # Verify the client was called correctly
        mock_client.send_value.assert_called_once_with('rabbitmq-test', 'rabbitmq.test.queue.size[/,test-queue]', '42')
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_value_missing_params(self, mock_client):
        """Test sending a value with missing parameters"""
        # Make a request to the API with missing parameters
        response = self.client.post('/api/zabbix/send', json={
            'host': 'rabbitmq-test',
            'key': 'rabbitmq.test.queue.size[/,test-queue]'
            # Missing 'value' parameter
        })
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was not called
        mock_client.send_value.assert_not_called()
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_value_error(self, mock_client):
        """Test sending a value with an error"""
        # Mock the send_value method to return an error
        mock_client.send_value.return_value = {
            'success': False,
            'error': 'Failed to send value'
        }
        
        # Make a request to the API
        response = self.client.post('/api/zabbix/send', json={
            'host': 'rabbitmq-test',
            'key': 'rabbitmq.test.queue.size[/,test-queue]',
            'value': 42
        })
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was called correctly
        mock_client.send_value.assert_called_once_with('rabbitmq-test', 'rabbitmq.test.queue.size[/,test-queue]', 42)
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_batch(self, mock_client):
        """Test sending multiple values to Zabbix"""
        # Mock the send_values_to_zabbix method
        mock_client.send_values_to_zabbix.return_value = self.test_send_batch_result
        
        # Make a request to the API
        response = self.client.post('/api/zabbix/send-batch', json=[
            {
                'host': 'rabbitmq-test',
                'key': 'rabbitmq.test.queue.size[/,queue1]',
                'value': 10
            },
            {
                'host': 'rabbitmq-test',
                'key': 'rabbitmq.test.queue.size[/,queue2]',
                'value': 20
            }
        ])
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Processed: 2; Failed: 0; Total: 2; seconds spent: 0.000128')
        
        # Verify the client was called correctly
        mock_client.send_values_to_zabbix.assert_called_once()
        args, kwargs = mock_client.send_values_to_zabbix.call_args
        data_points = args[0]
        self.assertEqual(len(data_points), 2)
        self.assertEqual(data_points[0]['host'], 'rabbitmq-test')
        self.assertEqual(data_points[0]['key'], 'rabbitmq.test.queue.size[/,queue1]')
        self.assertEqual(data_points[0]['value'], 10)
        self.assertEqual(data_points[1]['host'], 'rabbitmq-test')
        self.assertEqual(data_points[1]['key'], 'rabbitmq.test.queue.size[/,queue2]')
        self.assertEqual(data_points[1]['value'], 20)
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_batch_invalid_data(self, mock_client):
        """Test sending a batch with invalid data"""
        # Make a request to the API with invalid data
        response = self.client.post('/api/zabbix/send-batch', json={
            'host': 'rabbitmq-test',
            'key': 'rabbitmq.test.queue.size[/,test-queue]',
            'value': 42
        })  # Should be a list, not an object
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was not called
        mock_client.send_values_to_zabbix.assert_not_called()
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_batch_missing_params(self, mock_client):
        """Test sending a batch with missing parameters"""
        # Make a request to the API with missing parameters
        response = self.client.post('/api/zabbix/send-batch', json=[
            {
                'host': 'rabbitmq-test',
                'key': 'rabbitmq.test.queue.size[/,queue1]'
                # Missing 'value' parameter
            }
        ])
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was not called
        mock_client.send_values_to_zabbix.assert_not_called()
    
    @patch('app.api.endpoints.zabbix.zabbix_client')
    def test_send_batch_error(self, mock_client):
        """Test sending a batch with an error"""
        # Mock the send_values_to_zabbix method to return an error
        mock_client.send_values_to_zabbix.return_value = {
            'success': False,
            'error': 'Failed to send values'
        }
        
        # Make a request to the API
        response = self.client.post('/api/zabbix/send-batch', json=[
            {
                'host': 'rabbitmq-test',
                'key': 'rabbitmq.test.queue.size[/,queue1]',
                'value': 10
            }
        ])
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the client was called correctly
        mock_client.send_values_to_zabbix.assert_called_once()

if __name__ == "__main__":
    unittest.main()
