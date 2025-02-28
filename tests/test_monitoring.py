# tests/test_monitoring.py
import unittest
from unittest.mock import patch, MagicMock
from app.core.monitoring import MonitoringService

class TestMonitoringService(unittest.TestCase):
    """Test cases for the MonitoringService class"""
    
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
                    },
                    {
                        'cluster_node': 'rabbitmq-test-01.example.com',
                        'vhost': 'test',
                        'queue': 'another-queue',
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
                            },
                            {
                                'hostname': 'rabbitmq-test-02.example.com',
                                'api_port': 15672
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
            }
        }
        
        # Create mocks for the dependencies
        self.mock_rabbitmq_client = MagicMock()
        self.mock_zabbix_client = MagicMock()
        self.mock_notification_client = MagicMock()
        
        # Patch the client classes
        with patch('app.core.monitoring.RabbitMQClient', return_value=self.mock_rabbitmq_client), \
             patch('app.core.monitoring.ZabbixClient', return_value=self.mock_zabbix_client), \
             patch('app.core.monitoring.NotificationClient', return_value=self.mock_notification_client):
            # Create the service with the test configuration
            self.service = MonitoringService(self.test_config)
    
    def test_init(self):
        """Test initialization of the MonitoringService"""
        self.assertEqual(self.service.threshold, 1000)
        self.assertEqual(len(self.service.queues), 2)
        self.assertEqual(self.service.queues[0]['cluster_node'], 'rabbitmq-test-01.example.com')
        self.assertEqual(self.service.queues[0]['vhost'], '/')
        self.assertEqual(self.service.queues[0]['queue'], 'test-queue')
        self.assertEqual(self.service.queues[0]['zabbix_host'], 'rabbitmq-test')
    
    def test_get_node_from_queue_config(self):
        """Test getting node information from queue configuration"""
        # Test with valid queue config
        node_info = self.service.get_node_from_queue_config(self.service.queues[0])
        self.assertIsNotNone(node_info)
        self.assertEqual(node_info['cluster_id'], 'test-cluster')
        self.assertEqual(node_info['node']['hostname'], 'rabbitmq-test-01.example.com')
        
        # Test with invalid queue config
        node_info = self.service.get_node_from_queue_config({
            'cluster_node': 'non-existent-node',
            'vhost': '/',
            'queue': 'test-queue',
            'zabbix_host': 'rabbitmq-test'
        })
        self.assertIsNone(node_info)
    
    def test_collect_queue_metrics(self):
        """Test collecting metrics for configured queues"""
        # Mock the get_node_from_queue_config method
        with patch.object(self.service, 'get_node_from_queue_config') as mock_get_node:
            # Set up the mock to return node info for the first queue and None for the second
            mock_get_node.side_effect = [
                {
                    'cluster_id': 'test-cluster',
                    'node': {
                        'hostname': 'rabbitmq-test-01.example.com',
                        'api_port': 15672,
                        'primary': True
                    }
                },
                None  # Simulate a queue with invalid node
            ]
            
            # Mock the get_queue_info method of the RabbitMQ client
            self.mock_rabbitmq_client.get_queue_info.return_value = {
                'name': 'test-queue',
                'vhost': '/',
                'messages': 42,
                'consumers': 2,
                'state': 'running'
            }
            
            # Test collecting metrics
            metrics = self.service.collect_queue_metrics()
            
            # Verify the results
            self.assertEqual(len(metrics), 1)  # Only one valid queue
            self.assertEqual(metrics[0]['host'], 'rabbitmq-test')
            self.assertEqual(metrics[0]['metrics']['queue.messages'], 42)
            self.assertEqual(metrics[0]['metrics']['queue.consumers'], 2)
            self.assertEqual(metrics[0]['metrics']['queue.state'], 1)
            self.assertEqual(metrics[0]['queue_info']['vhost'], '/')
            self.assertEqual(metrics[0]['queue_info']['queue'], 'test-queue')
            
            # Verify the RabbitMQ client was called correctly
            self.mock_rabbitmq_client.get_queue_info.assert_called_once_with(
                'test-cluster', '/', 'test-queue'
            )
    
    def test_send_metrics_to_zabbix(self):
        """Test sending metrics to Zabbix"""
        # Test metrics
        metrics = [
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
        
        # Mock the send_values_to_zabbix method of the Zabbix client
        self.mock_zabbix_client.send_values_to_zabbix.return_value = {
            'success': True,
            'message': 'Processed: 3; Failed: 0; Total: 3'
        }
        
        # Test sending metrics to Zabbix
        result = self.service.send_metrics_to_zabbix(metrics)
        
        # Verify the results
        self.assertTrue(result['success'])
        self.assertEqual(result['message'], 'Processed: 3; Failed: 0; Total: 3')
        
        # Verify the Zabbix client was called correctly
        self.mock_zabbix_client.send_values_to_zabbix.assert_called_once()
        args, kwargs = self.mock_zabbix_client.send_values_to_zabbix.call_args
        zabbix_data_points = args[0]
        self.assertEqual(len(zabbix_data_points), 3)  # 3 metrics for the queue
        
        # Check that the data points have the correct format
        for data_point in zabbix_data_points:
            self.assertEqual(data_point['host'], 'rabbitmq-test')
            self.assertTrue(data_point['key'].startswith('rabbitmq./'))
            self.assertTrue(data_point['key'].endswith('queue.messages') or 
                           data_point['key'].endswith('queue.consumers') or 
                           data_point['key'].endswith('queue.state'))
        
        # Test with threshold exceeded
        metrics[0]['queue_info']['messages'] = 1500  # Above threshold
        
        # Reset the mock
        self.mock_zabbix_client.send_values_to_zabbix.reset_mock()
        self.mock_notification_client.send_alert.reset_mock()
        
        # Test sending metrics to Zabbix with threshold exceeded
        result = self.service.send_metrics_to_zabbix(metrics)
        
        # Verify the notification client was called
        self.mock_notification_client.send_alert.assert_called_once_with(
            'threshold', metrics[0]['queue_info']
        )
    
    def test_run_monitoring_cycle(self):
        """Test running a complete monitoring cycle"""
        # Mock the collect_queue_metrics method
        with patch.object(self.service, 'collect_queue_metrics') as mock_collect:
            # Set up the mock to return test metrics
            mock_collect.return_value = [
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
            
            # Mock the send_metrics_to_zabbix method
            with patch.object(self.service, 'send_metrics_to_zabbix') as mock_send:
                # Set up the mock to return success
                mock_send.return_value = {
                    'success': True,
                    'message': 'Processed: 3; Failed: 0; Total: 3'
                }
                
                # Test running the monitoring cycle
                result = self.service.run_monitoring_cycle()
                
                # Verify the results
                self.assertEqual(result['metrics_collected'], 1)
                self.assertTrue(result['success'])
                self.assertEqual(result['zabbix_result']['message'], 'Processed: 3; Failed: 0; Total: 3')
                
                # Verify the methods were called
                mock_collect.assert_called_once()
                mock_send.assert_called_once_with([
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
                ])
    
    def test_collect_all_queue_metrics(self):
        """Test collecting metrics for all queues"""
        # Mock the get_all_queues method of the RabbitMQ client
        self.mock_rabbitmq_client.get_all_queues.return_value = [
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
        
        # Test collecting all queue metrics
        metrics = self.service.collect_all_queue_metrics()
        
        # Verify the results
        self.assertEqual(len(metrics), 2)
        self.assertEqual(metrics[0]['host'], 'rabbitmq-test')
        self.assertEqual(metrics[0]['queue_info']['queue'], 'queue1')
        self.assertEqual(metrics[0]['queue_info']['vhost'], '/')
        self.assertEqual(metrics[0]['queue_info']['messages'], 10)
        self.assertEqual(metrics[1]['host'], 'rabbitmq-test')
        self.assertEqual(metrics[1]['queue_info']['queue'], 'queue2')
        self.assertEqual(metrics[1]['queue_info']['vhost'], 'test')
        self.assertEqual(metrics[1]['queue_info']['messages'], 20)
        
        # Verify the RabbitMQ client was called correctly
        self.mock_rabbitmq_client.get_all_queues.assert_called_once_with('test-cluster')
        
        # Test with error from RabbitMQ client
        self.mock_rabbitmq_client.get_all_queues.reset_mock()
        self.mock_rabbitmq_client.get_all_queues.return_value = {"error": "Connection failed"}
        
        # Test collecting all queue metrics with error
        metrics = self.service.collect_all_queue_metrics()
        
        # Verify the results
        self.assertEqual(len(metrics), 0)
    
    def test_send_all_metrics_to_zabbix(self):
        """Test sending all metrics to Zabbix"""
        # Mock the collect_all_queue_metrics method
        with patch.object(self.service, 'collect_all_queue_metrics') as mock_collect:
            # Set up the mock to return test metrics
            mock_collect.return_value = [
                {
                    'host': 'rabbitmq-test',
                    'metrics': {
                        'rabbitmq.test.queue.size[/,queue1]': 10,
                        'rabbitmq.test.queue.consumers[/,queue1]': 1,
                        'rabbitmq.test.queue.state[/,queue1]': 1
                    },
                    'queue_info': {
                        'vhost': '/',
                        'queue': 'queue1',
                        'messages': 10,
                        'consumers': 1,
                        'state': 'running'
                    }
                },
                {
                    'host': 'rabbitmq-test',
                    'metrics': {
                        'rabbitmq.test.queue.size[test,queue2]': 20,
                        'rabbitmq.test.queue.consumers[test,queue2]': 2,
                        'rabbitmq.test.queue.state[test,queue2]': 1
                    },
                    'queue_info': {
                        'vhost': 'test',
                        'queue': 'queue2',
                        'messages': 20,
                        'consumers': 2,
                        'state': 'running'
                    }
                }
            ]
            
            # Mock the send_values_to_zabbix method of the Zabbix client
            self.mock_zabbix_client.send_values_to_zabbix.return_value = {
                'success': True,
                'message': 'Processed: 6; Failed: 0; Total: 6'
            }
            
            # Test sending all metrics to Zabbix
            result = self.service.send_all_metrics_to_zabbix()
            
            # Verify the results
            self.assertEqual(result['metrics_collected'], 2)
            self.assertEqual(result['data_points_sent'], 6)
            self.assertTrue(result['success'])
            self.assertEqual(result['zabbix_result']['message'], 'Processed: 6; Failed: 0; Total: 6')
            
            # Verify the methods were called
            mock_collect.assert_called_once()
            self.mock_zabbix_client.send_values_to_zabbix.assert_called_once()
            
            # Verify the Zabbix client was called with the correct data points
            args, kwargs = self.mock_zabbix_client.send_values_to_zabbix.call_args
            zabbix_data_points = args[0]
            self.assertEqual(len(zabbix_data_points), 6)  # 3 metrics for each of the 2 queues
    
    def test_check_queue_drift(self):
        """Test checking queues for drift"""
        # Mock the get_item_history method of the Zabbix client
        self.mock_zabbix_client.get_item_history.side_effect = [
            # First queue: drift detected
            [
                {'value': '50', 'clock': '1614556800'},  # Latest value
                {'value': '30', 'clock': '1614553200'}   # Previous value
            ],
            # Second queue: no drift
            [
                {'value': '20', 'clock': '1614556800'},  # Latest value
                {'value': '25', 'clock': '1614553200'}   # Previous value (higher than latest)
            ]
        ]
        
        # Test checking for drift
        alerts = self.service.check_queue_drift()
        
        # Verify the results
        self.assertEqual(len(alerts), 1)  # Only one queue has drift
        self.assertEqual(alerts[0]['type'], 'drift')
        self.assertEqual(alerts[0]['queue_info']['vhost'], '/')
        self.assertEqual(alerts[0]['queue_info']['queue'], 'test-queue')
        self.assertEqual(alerts[0]['queue_info']['current_count'], 50)
        self.assertEqual(alerts[0]['queue_info']['previous_count'], 30)
        
        # Verify the Zabbix client was called correctly
        self.assertEqual(self.mock_zabbix_client.get_item_history.call_count, 2)
        
        # Test with threshold exceeded
        self.mock_zabbix_client.get_item_history.reset_mock()
        self.mock_zabbix_client.get_item_history.side_effect = [
            # First queue: drift and threshold exceeded
            [
                {'value': '1500', 'clock': '1614556800'},  # Latest value (above threshold)
                {'value': '900', 'clock': '1614553200'}    # Previous value
            ]
        ]
        
        # Test checking for drift with threshold exceeded
        alerts = self.service.check_queue_drift()
        
        # Verify the results
        self.assertEqual(len(alerts), 2)  # Both drift and threshold alerts
        self.assertEqual(alerts[0]['type'], 'drift')
        self.assertEqual(alerts[1]['type'], 'threshold')
    
    def test_process_queue_alerts(self):
        """Test processing queue alerts"""
        # Mock the check_queue_drift method
        with patch.object(self.service, 'check_queue_drift') as mock_check:
            # Set up the mock to return test alerts
            mock_check.return_value = [
                {
                    'type': 'drift',
                    'queue_info': {
                        'node': 'rabbitmq-test-01.example.com',
                        'vhost': '/',
                        'queue': 'test-queue',
                        'current_count': 50,
                        'previous_count': 30,
                        'timestamp': '2023-01-01 12:00:00',
                        'threshold': 1000,
                        'zabbix_host': 'rabbitmq-test'
                    }
                },
                {
                    'type': 'threshold',
                    'queue_info': {
                        'node': 'rabbitmq-test-01.example.com',
                        'vhost': '/',
                        'queue': 'test-queue',
                        'current_count': 1500,
                        'previous_count': 900,
                        'timestamp': '2023-01-01 12:00:00',
                        'threshold': 1000,
                        'zabbix_host': 'rabbitmq-test'
                    }
                }
            ]
            
            # Mock the send_alert method of the notification client
            self.mock_notification_client.send_alert.side_effect = [
                {'success': True, 'message': 'Drift alert sent'},
                {'success': True, 'message': 'Threshold alert sent'}
            ]
            
            # Test processing alerts
            result = self.service.process_queue_alerts()
            
            # Verify the results
            self.assertEqual(result['alerts_detected'], 2)
            self.assertEqual(result['notifications_sent'], 2)
            self.assertEqual(len(result['results']), 2)
            self.assertEqual(result['results'][0]['type'], 'drift')
            self.assertEqual(result['results'][0]['queue'], '/test-queue')
            self.assertEqual(result['results'][1]['type'], 'threshold')
            self.assertEqual(result['results'][1]['queue'], '/test-queue')
            
            # Verify the methods were called
            mock_check.assert_called_once()
            self.assertEqual(self.mock_notification_client.send_alert.call_count, 2)
            
            # Verify the notification client was called with the correct parameters
            self.mock_notification_client.send_alert.assert_any_call(
                'drift', mock_check.return_value[0]['queue_info']
            )
            self.mock_notification_client.send_alert.assert_any_call(
                'threshold', mock_check.return_value[1]['queue_info']
            )

if __name__ == "__main__":
    unittest.main()
