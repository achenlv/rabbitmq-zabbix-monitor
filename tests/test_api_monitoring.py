# tests/test_api_monitoring.py
import unittest
from unittest.mock import patch, MagicMock
import json
from flask import Flask
from app.api import api
from app.api.endpoints.monitoring import monitoring_ns, RunMonitoring, RunAllMonitoring, MonitoredQueues, Metrics, AllMetrics, CheckDrift, CompleteMonitoring
from app.core.monitoring import MonitoringService

class TestMonitoringAPI(unittest.TestCase):
    """Test cases for the Monitoring API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a Flask app
        self.app = Flask(__name__)
        api.init_app(self.app)
        
        # Create a test client
        self.client = self.app.test_client()
        
        # Sample monitoring configuration for testing
        self.test_monitoring_config = {
            'threshold': 1000,
            'queues': [
                {
                    'cluster_node': 'rabbitmq-test-01.example.com',
                    'vhost': '/',
                    'queue': 'test-queue',
                    'zabbix_host': 'rabbitmq-test'
                },
                {
                    'cluster_node': 'rabbitmq-test-01.example.com',
                    'vhost': 'test',
                    'queue': 'another-queue',
                    'zabbix_host': 'rabbitmq-test'
                }
            ]
        }
        
        # Sample metrics for testing
        self.test_metrics = [
            {
                'host': 'rabbitmq-test',
                'metrics': {
                    'queue.messages': 42,
                    'queue.consumers': 2,
                    'queue.state': 1
                },
                'queue_info': {
                    'vhost': '/',
                    'queue': 'test-queue',
                    'messages': 42,
                    'consumers': 2,
                    'state': 'running'
                }
            }
        ]
        
        # Sample monitoring result for testing
        self.test_monitoring_result = {
            'metrics_collected': 1,
            'data_points_sent': 3,
            'zabbix_result': {
                'success': True,
                'message': 'Processed: 3; Failed: 0; Total: 3'
            },
            'success': True
        }
        
        # Sample drift result for testing
        self.test_drift_result = {
            'alerts_detected': 1,
            'notifications_sent': 1,
            'results': [
                {
                    'type': 'drift',
                    'queue': '/test-queue',
                    'result': {
                        'success': True,
                        'message': 'Alert sent to team@example.com'
                    }
                }
            ]
        }
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_run_monitoring(self, mock_service):
        """Test running the monitoring cycle"""
        # Mock the run_monitoring_cycle method
        mock_service.run_monitoring_cycle.return_value = self.test_monitoring_result
        
        # Make a request to the API
        response = self.client.post('/api/monitoring/run')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['metrics_collected'], 1)
        self.assertEqual(data['data_points_sent'], 3)
        
        # Verify the service was called correctly
        mock_service.run_monitoring_cycle.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_run_monitoring_failure(self, mock_service):
        """Test running the monitoring cycle with a failure"""
        # Mock the run_monitoring_cycle method to return a failure
        mock_service.run_monitoring_cycle.return_value = {
            'metrics_collected': 0,
            'zabbix_result': {
                'success': False,
                'error': 'Failed to send metrics'
            },
            'success': False
        }
        
        # Make a request to the API
        response = self.client.post('/api/monitoring/run')
        
        # Verify the response
        self.assertEqual(response.status_code, 400)
        
        # Verify the service was called correctly
        mock_service.run_monitoring_cycle.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_run_all_monitoring(self, mock_service):
        """Test running the monitoring cycle for all queues"""
        # Mock the collect_all_queue_metrics method
        mock_service.collect_all_queue_metrics.return_value = self.test_metrics
        
        # Mock the send_values_to_zabbix method
        mock_service.zabbix_client.send_values_to_zabbix.return_value = {
            'success': True,
            'message': 'Processed: 3; Failed: 0; Total: 3'
        }
        
        # Make a request to the API
        response = self.client.post('/api/monitoring/run-all')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['metrics_collected'], 1)
        self.assertEqual(data['data_points_sent'], 3)
        
        # Verify the service was called correctly
        mock_service.collect_all_queue_metrics.assert_called_once()
        mock_service.zabbix_client.send_values_to_zabbix.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_run_all_monitoring_get(self, mock_service):
        """Test running the monitoring cycle for all queues via GET"""
        # Mock the collect_all_queue_metrics method
        mock_service.collect_all_queue_metrics.return_value = self.test_metrics
        
        # Mock the send_values_to_zabbix method
        mock_service.zabbix_client.send_values_to_zabbix.return_value = {
            'success': True,
            'message': 'Processed: 3; Failed: 0; Total: 3'
        }
        
        # Make a request to the API
        response = self.client.get('/api/monitoring/run-all')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['metrics_collected'], 1)
        self.assertEqual(data['data_points_sent'], 3)
        
        # Verify the service was called correctly
        mock_service.collect_all_queue_metrics.assert_called_once()
        mock_service.zabbix_client.send_values_to_zabbix.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.config')
    def test_get_monitored_queues(self, mock_config):
        """Test getting all monitored queues"""
        # Mock the get method
        mock_config.get.return_value = self.test_monitoring_config
        
        # Make a request to the API
        response = self.client.get('/api/monitoring/queues')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['cluster_node'], 'rabbitmq-test-01.example.com')
        self.assertEqual(data[0]['vhost'], '/')
        self.assertEqual(data[0]['queue'], 'test-queue')
        self.assertEqual(data[0]['zabbix_host'], 'rabbitmq-test')
        self.assertEqual(data[1]['cluster_node'], 'rabbitmq-test-01.example.com')
        self.assertEqual(data[1]['vhost'], 'test')
        self.assertEqual(data[1]['queue'], 'another-queue')
        self.assertEqual(data[1]['zabbix_host'], 'rabbitmq-test')
        
        # Verify the config was called correctly
        mock_config.get.assert_called_once_with('monitoring', {})
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_get_metrics(self, mock_service):
        """Test collecting metrics without sending to Zabbix"""
        # Mock the collect_queue_metrics method
        mock_service.collect_queue_metrics.return_value = self.test_metrics
        
        # Make a request to the API
        response = self.client.get('/api/monitoring/metrics')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['host'], 'rabbitmq-test')
        self.assertEqual(data[0]['metrics']['queue.messages'], 42)
        self.assertEqual(data[0]['metrics']['queue.consumers'], 2)
        self.assertEqual(data[0]['metrics']['queue.state'], 1)
        self.assertEqual(data[0]['queue_info']['vhost'], '/')
        self.assertEqual(data[0]['queue_info']['queue'], 'test-queue')
        
        # Verify the service was called correctly
        mock_service.collect_queue_metrics.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_get_all_metrics(self, mock_service):
        """Test collecting metrics for all queues without sending to Zabbix"""
        # Mock the collect_all_queue_metrics method
        mock_service.collect_all_queue_metrics.return_value = self.test_metrics
        
        # Make a request to the API
        response = self.client.get('/api/monitoring/metrics-all')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['host'], 'rabbitmq-test')
        self.assertEqual(data[0]['metrics']['queue.messages'], 42)
        self.assertEqual(data[0]['metrics']['queue.consumers'], 2)
        self.assertEqual(data[0]['metrics']['queue.state'], 1)
        self.assertEqual(data[0]['queue_info']['vhost'], '/')
        self.assertEqual(data[0]['queue_info']['queue'], 'test-queue')
        
        # Verify the service was called correctly
        mock_service.collect_all_queue_metrics.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_check_drift(self, mock_service):
        """Test checking for queue drift and sending notifications"""
        # Mock the process_queue_alerts method
        mock_service.process_queue_alerts.return_value = self.test_drift_result
        
        # Make a request to the API
        response = self.client.post('/api/monitoring/check-drift')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['alerts_detected'], 1)
        self.assertEqual(data['notifications_sent'], 1)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['type'], 'drift')
        self.assertEqual(data['results'][0]['queue'], '/test-queue')
        
        # Verify the service was called correctly
        mock_service.process_queue_alerts.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_check_drift_get(self, mock_service):
        """Test checking for queue drift via GET"""
        # Mock the process_queue_alerts method
        mock_service.process_queue_alerts.return_value = self.test_drift_result
        
        # Make a request to the API
        response = self.client.get('/api/monitoring/check-drift')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['alerts_detected'], 1)
        self.assertEqual(data['notifications_sent'], 1)
        
        # Verify the service was called correctly
        mock_service.process_queue_alerts.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_complete_monitoring(self, mock_service):
        """Test comprehensive monitoring"""
        # Mock the collect_all_queue_metrics method
        mock_service.collect_all_queue_metrics.return_value = self.test_metrics
        
        # Mock the send_values_to_zabbix method
        mock_service.zabbix_client.send_values_to_zabbix.return_value = {
            'success': True,
            'message': 'Processed: 3; Failed: 0; Total: 3'
        }
        
        # Mock the process_queue_alerts method
        mock_service.process_queue_alerts.return_value = self.test_drift_result
        
        # Make a request to the API
        response = self.client.post('/api/monitoring/monitor-all-drift')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['metrics_result']['metrics_collected'], 1)
        self.assertEqual(data['metrics_result']['data_points_sent'], 3)
        self.assertEqual(data['drift_result']['alerts_detected'], 1)
        self.assertEqual(data['drift_result']['notifications_sent'], 1)
        
        # Verify the service was called correctly
        mock_service.collect_all_queue_metrics.assert_called_once()
        mock_service.zabbix_client.send_values_to_zabbix.assert_called_once()
        mock_service.process_queue_alerts.assert_called_once()
    
    @patch('app.api.endpoints.monitoring.monitoring_service')
    def test_complete_monitoring_get(self, mock_service):
        """Test comprehensive monitoring via GET"""
        # Mock the collect_all_queue_metrics method
        mock_service.collect_all_queue_metrics.return_value = self.test_metrics
        
        # Mock the send_values_to_zabbix method
        mock_service.zabbix_client.send_values_to_zabbix.return_value = {
            'success': True,
            'message': 'Processed: 3; Failed: 0; Total: 3'
        }
        
        # Mock the process_queue_alerts method
        mock_service.process_queue_alerts.return_value = self.test_drift_result
        
        # Make a request to the API
        response = self.client.get('/api/monitoring/monitor-all-drift')
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['metrics_result']['metrics_collected'], 1)
        self.assertEqual(data['metrics_result']['data_points_sent'], 3)
        self.assertEqual(data['drift_result']['alerts_detected'], 1)
        self.assertEqual(data['drift_result']['notifications_sent'], 1)
        
        # Verify the service was called correctly
        mock_service.collect_all_queue_metrics.assert_called_once()
        mock_service.zabbix_client.send_values_to_zabbix.assert_called_once()
        mock_service.process_queue_alerts.assert_called_once()

if __name__ == "__main__":
    unittest.main()
