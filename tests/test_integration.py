# tests/test_integration.py
import unittest
from unittest.mock import patch, MagicMock
import os
import json
from app.core.config import Config
from app.core.rabbitmq import RabbitMQClient
from app.core.zabbix import ZabbixClient
from app.core.notification import NotificationClient
from app.core.monitoring import MonitoringService

class TestIntegration(unittest.TestCase):
    """Integration tests for the RabbitMQ-Zabbix Monitor"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a sample configuration for testing
        self.test_config = {
            'monitoring': {
                'threshold': 1000,
                'queues': [
                    {
                        'cluster_node': 'rabbitmq-test-01.example.com',
                        'vhost': '/',
                        'queue': 'test-queue',
                        'zabbix_host': 'rabbitmq-test'
                    }
                ]
            },
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
                            }
                        ],
                        'auth': {
                            'user': 'test-user',
                            'password': 'test-password'
                        },
                        'monitoring': {
                            'enabled': True,
                            'default_zabbix_host': 'rabbitmq-test'
                        }
                    }
                ]
            },
            'zabbix': {
                'url': 'https://zabbix.example.com',
                'server': 'zabbix-server.example.com',
                'port': 10051,
                'user': 'api-user',
                'password': 'api-password'
            },
            'email': {
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_user': 'alerts@example.com',
                'smtp_password': 'test-password',
                'from_address': 'rabbitmq-monitor@example.com',
                'templates': {
                    'drift': 'templates/drift_alert.html',
                    'threshold': 'templates/threshold_alert.html'
                },
                'alerts': {
                    'drift': {
                        'subject': 'RabbitMQ Queue Drift Alert - {vhost}/{queue}',
                        'template': 'drift',
                        'to': ['team@example.com']
                    },
                    'threshold': {
                        'subject': 'RabbitMQ Queue Threshold Alert - {vhost}/{queue}',
                        'template': 'threshold',
                        'to': ['team@example.com']
                    }
                }
            }
        }
        
        # Create the clients
        self.rabbitmq_client = RabbitMQClient(self.test_config)
        self.zabbix_client = ZabbixClient(self.test_config)
        self.notification_client = NotificationClient(self.test_config)
        self.monitoring_service = MonitoringService(self.test_config)
    
    @patch('app.core.rabbitmq.requests.get')
    def test_rabbitmq_to_zabbix_integration(self, mock_get):
        """Test the integration between RabbitMQ and Zabbix"""
        # Mock the RabbitMQ API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'name': 'test-queue',
            'vhost': '/',
            'messages': 42,
            'consumers': 2,
            'state': 'running'
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Mock the Zabbix client's send_values_to_zabbix method
        with patch.object(self.zabbix_client, 'send_values_to_zabbix') as mock_send:
            # Set up the mock to return success
            mock_send.return_value = {
                'success': True,
                'message': 'Processed: 3; Failed: 0; Total: 3'
            }
            
            # Replace the monitoring service's clients with our mocked ones
            self.monitoring_service.rabbitmq_client = self.rabbitmq_client
            self.monitoring_service.zabbix_client = self.zabbix_client
            
            # Run the monitoring cycle
            result = self.monitoring_service.run_monitoring_cycle()
            
            # Verify the results
            self.assertTrue(result['success'])
            self.assertEqual(result['metrics_collected'], 1)
            
            # Verify the RabbitMQ client was called correctly
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            self.assertTrue('rabbitmq-test-01.example.com:15672/api/queues/' in args[0])
            self.assertEqual(kwargs['auth'], ('test-user', 'test-password'))
            
            # Verify the Zabbix client was called correctly
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            zabbix_data_points = args[0]
            self.assertEqual(len(zabbix_data_points), 3)  # 3 metrics for the queue
            
            # Check that the data points have the correct format
            for data_point in zabbix_data_points:
                self.assertEqual(data_point['host'], 'rabbitmq-test')
                self.assertTrue(data_point['key'].startswith('rabbitmq./'))
                self.assertTrue(data_point['key'].endswith('queue.messages') or 
                               data_point['key'].endswith('queue.consumers') or 
                               data_point['key'].endswith('queue.state'))
    
    @patch('app.core.rabbitmq.requests.get')
    @patch('app.core.zabbix.requests.post')
    def test_drift_detection_and_notification(self, mock_post, mock_get):
        """Test drift detection and notification"""
        # Mock the RabbitMQ API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'name': 'test-queue',
            'vhost': '/',
            'messages': 1500,  # Above threshold
            'consumers': 2,
            'state': 'running'
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Mock the Zabbix API responses
        mock_host_response = MagicMock()
        mock_host_response.json.return_value = {"result": [{"hostid": "10084", "host": "rabbitmq-test"}]}
        
        mock_item_response = MagicMock()
        mock_item_response.json.return_value = {"result": [{"itemid": "28979", "key_": "rabbitmq.test.queue.size[/,test-queue]", "value_type": 0}]}
        
        mock_history_response = MagicMock()
        mock_history_response.json.return_value = {
            "result": [
                {"value": "1500", "clock": "1614556800"},  # Latest value
                {"value": "900", "clock": "1614553200"}    # Previous value
            ]
        }
        
        # Set up the mock to return different responses for different API calls
        mock_post.side_effect = [mock_host_response, mock_item_response, mock_history_response]
        
        # Mock the notification client's send_alert method
        with patch.object(self.notification_client, 'send_alert') as mock_send_alert:
            # Set up the mock to return success
            mock_send_alert.return_value = {
                'success': True,
                'message': 'Alert sent to team@example.com'
            }
            
            # Replace the monitoring service's clients with our mocked ones
            self.monitoring_service.rabbitmq_client = self.rabbitmq_client
            self.monitoring_service.zabbix_client = self.zabbix_client
            self.monitoring_service.notification_client = self.notification_client
            
            # Set auth token for Zabbix client
            self.zabbix_client._auth = "auth-token-123"
            
            # Check for drift and send notifications
            result = self.monitoring_service.process_queue_alerts()
            
            # Verify the results
            self.assertEqual(result['alerts_detected'], 2)  # Both drift and threshold alerts
            self.assertEqual(result['notifications_sent'], 2)
            
            # Verify the Zabbix client was called correctly
            self.assertEqual(mock_post.call_count, 3)
            
            # Verify the notification client was called correctly
            self.assertEqual(mock_send_alert.call_count, 2)
            mock_send_alert.assert_any_call('drift', unittest.mock.ANY)
            mock_send_alert.assert_any_call('threshold', unittest.mock.ANY)
    
    @patch('app.core.rabbitmq.requests.get')
    @patch('app.core.zabbix.subprocess.Popen')
    @patch('app.core.notification.smtplib.SMTP')
    @patch('app.core.notification.open', new_callable=unittest.mock.mock_open, read_data='<html>Alert: {vhost}/{queue}</html>')
    def test_full_monitoring_cycle(self, mock_open, mock_smtp, mock_popen, mock_get):
        """Test a full monitoring cycle from RabbitMQ to Zabbix to notification"""
        # Mock the RabbitMQ API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'name': 'test-queue',
            'vhost': '/',
            'messages': 1500,  # Above threshold
            'consumers': 2,
            'state': 'running'
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Mock the Zabbix sender process
        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"Processed: 3; Failed: 0; Total: 3", b"")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        # Mock the SMTP server
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance
        
        # Mock finding zabbix_sender
        with patch.object(self.zabbix_client, '_find_zabbix_sender', return_value='/usr/bin/zabbix_sender'):
            # Mock the get_item_history method of the Zabbix client
            with patch.object(self.zabbix_client, 'get_item_history') as mock_get_history:
                # Set up the mock to return history data
                mock_get_history.return_value = [
                    {'value': '1500', 'clock': '1614556800'},  # Latest value
                    {'value': '900', 'clock': '1614553200'}    # Previous value
                ]
                
                # Replace the monitoring service's clients with our mocked ones
                self.monitoring_service.rabbitmq_client = self.rabbitmq_client
                self.monitoring_service.zabbix_client = self.zabbix_client
                self.monitoring_service.notification_client = self.notification_client
                
                # Run the monitoring cycle and check for drift
                metrics_result = self.monitoring_service.run_monitoring_cycle()
                drift_result = self.monitoring_service.process_queue_alerts()
                
                # Verify the metrics result
                self.assertTrue(metrics_result['success'])
                self.assertEqual(metrics_result['metrics_collected'], 1)
                
                # Verify the drift result
                self.assertEqual(drift_result['alerts_detected'], 2)  # Both drift and threshold alerts
                self.assertEqual(drift_result['notifications_sent'], 2)
                
                # Verify the RabbitMQ client was called correctly
                mock_get.assert_called_once()
                
                # Verify the Zabbix sender was called correctly
                mock_popen.assert_called_once()
                
                # Verify the SMTP server was used correctly
                self.assertEqual(mock_smtp_instance.sendmail.call_count, 2)  # Two emails sent
    
    @patch('app.core.config.Config._load_config')
    def test_config_integration(self, mock_load_config):
        """Test the integration with the configuration system"""
        # Mock the config loading
        mock_load_config.return_value = self.test_config
        
        # Create a config instance
        config = Config()
        
        # Get the configuration sections
        rabbitmq_config = config.get('rabbitmq')
        zabbix_config = config.get('zabbix')
        monitoring_config = config.get('monitoring')
        email_config = config.get('email')
        
        # Verify the configuration sections
        self.assertEqual(len(rabbitmq_config['clusters']), 1)
        self.assertEqual(rabbitmq_config['clusters'][0]['id'], 'test-cluster')
        self.assertEqual(zabbix_config['server'], 'zabbix-server.example.com')
        self.assertEqual(monitoring_config['threshold'], 1000)
        self.assertEqual(email_config['smtp_server'], 'smtp.example.com')
        
        # Create clients with the configuration
        rabbitmq_client = RabbitMQClient(config.get_config())
        zabbix_client = ZabbixClient(config.get_config())
        notification_client = NotificationClient(config.get_config())
        monitoring_service = MonitoringService(config.get_config())
        
        # Verify the clients were initialized correctly
        self.assertEqual(len(rabbitmq_client.clusters), 1)
        self.assertEqual(rabbitmq_client.clusters[0]['id'], 'test-cluster')
        self.assertEqual(zabbix_client.server, 'zabbix-server.example.com')
        self.assertEqual(monitoring_service.threshold, 1000)
        self.assertEqual(notification_client.smtp_server, 'smtp.example.com')

if __name__ == "__main__":
    unittest.main()
