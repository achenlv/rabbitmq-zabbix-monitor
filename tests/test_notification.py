# tests/test_notification.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
from app.core.notification import NotificationClient

class TestNotificationClient(unittest.TestCase):
    """Test cases for the NotificationClient class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a sample configuration for testing
        self.test_config = {
            'email': {
                'smtp_server': 'smtp.example.com',
                'smtp_port': 587,
                'smtp_user': 'alerts@example.com',
                'smtp_password': 'test-password',
                'from_address': 'rabbitmq-monitor@example.com',
                'templates': {
                    'drift': 'templates/drift_alert.html',
                    'threshold': 'templates/threshold_alert.html',
                    'error': 'templates/error_alert.html'
                },
                'alerts': {
                    'drift': {
                        'subject': 'RabbitMQ Queue Drift Alert - {vhost}/{queue}',
                        'template': 'drift',
                        'to': ['team@example.com'],
                        'cc': ['manager@example.com']
                    },
                    'threshold': {
                        'subject': 'RabbitMQ Queue Threshold Alert - {vhost}/{queue}',
                        'template': 'threshold',
                        'to': ['team@example.com']
                    }
                }
            }
        }
        
        # Create the client with the test configuration
        self.client = NotificationClient(self.test_config)
    
    def test_init(self):
        """Test initialization of the NotificationClient"""
        self.assertEqual(self.client.smtp_server, 'smtp.example.com')
        self.assertEqual(self.client.smtp_port, 587)
        self.assertEqual(self.client.smtp_user, 'alerts@example.com')
        self.assertEqual(self.client.smtp_password, 'test-password')
        self.assertEqual(self.client.from_address, 'rabbitmq-monitor@example.com')
        self.assertEqual(self.client.templates['drift'], 'templates/drift_alert.html')
        self.assertEqual(self.client.templates['threshold'], 'templates/threshold_alert.html')
        self.assertEqual(self.client.templates['error'], 'templates/error_alert.html')
        self.assertEqual(self.client.alerts['drift']['subject'], 'RabbitMQ Queue Drift Alert - {vhost}/{queue}')
        self.assertEqual(self.client.alerts['drift']['to'], ['team@example.com'])
        self.assertEqual(self.client.alerts['drift']['cc'], ['manager@example.com'])
        self.assertEqual(self.client.alerts['threshold']['subject'], 'RabbitMQ Queue Threshold Alert - {vhost}/{queue}')
        self.assertEqual(self.client.alerts['threshold']['to'], ['team@example.com'])
    
    @patch('app.core.notification.open', new_callable=mock_open, read_data='<html>Hello {name}!</html>')
    def test_load_template(self, mock_file):
        """Test loading an email template from file"""
        # Test with valid template name
        template = self.client._load_template('drift')
        self.assertIsNotNone(template)
        self.assertEqual(template.template, '<html>Hello {name}!</html>')
        
        # Verify the file was opened correctly
        mock_file.assert_called_once_with('templates/drift_alert.html', 'r')
        
        # Test with invalid template name
        template = self.client._load_template('non-existent')
        self.assertIsNone(template)
        
        # Test with file open error
        mock_file.side_effect = IOError('File not found')
        template = self.client._load_template('drift')
        self.assertIsNone(template)
    
    @patch('app.core.notification.smtplib.SMTP')
    def test_send_alert_drift(self, mock_smtp):
        """Test sending a drift alert email"""
        # Mock the _load_template method
        with patch.object(self.client, '_load_template') as mock_load_template:
            # Set up the mock to return a template
            from string import Template
            mock_template = Template('<html>Drift alert for {vhost}/{queue}: {current_count} (was {previous_count})</html>')
            mock_load_template.return_value = mock_template
            
            # Test context
            context = {
                'vhost': '/',
                'queue': 'test-queue',
                'current_count': 50,
                'previous_count': 30,
                'timestamp': '2023-01-01 12:00:00',
                'threshold': 1000,
                'zabbix_host': 'rabbitmq-test'
            }
            
            # Test sending a drift alert
            result = self.client.send_alert('drift', context)
            
            # Verify the results
            self.assertTrue(result['success'])
            self.assertEqual(result['message'], 'Alert sent to team@example.com')
            
            # Verify the template was loaded
            mock_load_template.assert_called_once_with('drift')
            
            # Verify the SMTP server was used correctly
            mock_smtp.assert_called_once_with('smtp.example.com', 587)
            mock_smtp_instance = mock_smtp.return_value
            mock_smtp_instance.login.assert_called_once_with('alerts@example.com', 'test-password')
            mock_smtp_instance.sendmail.assert_called_once()
            
            # Verify the email content
            args, kwargs = mock_smtp_instance.sendmail.call_args
            self.assertEqual(args[0], 'rabbitmq-monitor@example.com')
            self.assertEqual(args[1], ['team@example.com', 'manager@example.com'])
            email_content = args[2]
            self.assertIn('Subject: RabbitMQ Queue Drift Alert - /test-queue', email_content)
            self.assertIn('From: rabbitmq-monitor@example.com', email_content)
            self.assertIn('To: team@example.com', email_content)
            self.assertIn('Cc: manager@example.com', email_content)
            self.assertIn('<html>Drift alert for /test-queue: 50 (was 30)</html>', email_content)
    
    @patch('app.core.notification.smtplib.SMTP')
    def test_send_alert_threshold(self, mock_smtp):
        """Test sending a threshold alert email"""
        # Mock the _load_template method
        with patch.object(self.client, '_load_template') as mock_load_template:
            # Set up the mock to return a template
            from string import Template
            mock_template = Template('<html>Threshold alert for {vhost}/{queue}: {current_count} (threshold: {threshold})</html>')
            mock_load_template.return_value = mock_template
            
            # Test context
            context = {
                'vhost': '/',
                'queue': 'test-queue',
                'current_count': 1500,
                'previous_count': 900,
                'timestamp': '2023-01-01 12:00:00',
                'threshold': 1000,
                'zabbix_host': 'rabbitmq-test'
            }
            
            # Test sending a threshold alert
            result = self.client.send_alert('threshold', context)
            
            # Verify the results
            self.assertTrue(result['success'])
            self.assertEqual(result['message'], 'Alert sent to team@example.com')
            
            # Verify the template was loaded
            mock_load_template.assert_called_once_with('threshold')
            
            # Verify the SMTP server was used correctly
            mock_smtp.assert_called_once_with('smtp.example.com', 587)
            mock_smtp_instance = mock_smtp.return_value
            mock_smtp_instance.login.assert_called_once_with('alerts@example.com', 'test-password')
            mock_smtp_instance.sendmail.assert_called_once()
            
            # Verify the email content
            args, kwargs = mock_smtp_instance.sendmail.call_args
            self.assertEqual(args[0], 'rabbitmq-monitor@example.com')
            self.assertEqual(args[1], ['team@example.com'])  # No CC for threshold alerts
            email_content = args[2]
            self.assertIn('Subject: RabbitMQ Queue Threshold Alert - /test-queue', email_content)
            self.assertIn('From: rabbitmq-monitor@example.com', email_content)
            self.assertIn('To: team@example.com', email_content)
            self.assertIn('<html>Threshold alert for /test-queue: 1500 (threshold: 1000)</html>', email_content)
    
    def test_send_alert_unknown_type(self):
        """Test sending an alert with an unknown type"""
        # Test context
        context = {
            'vhost': '/',
            'queue': 'test-queue',
            'current_count': 50,
            'previous_count': 30
        }
        
        # Test sending an alert with an unknown type
        result = self.client.send_alert('unknown', context)
        
        # Verify the results
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'Unknown alert type: unknown')
    
    @patch('app.core.notification.smtplib.SMTP')
    def test_send_alert_no_recipients(self, mock_smtp):
        """Test sending an alert with no recipients"""
        # Create a client with no recipients
        config = self.test_config.copy()
        config['email']['alerts']['drift']['to'] = []
        client = NotificationClient(config)
        
        # Test context
        context = {
            'vhost': '/',
            'queue': 'test-queue',
            'current_count': 50,
            'previous_count': 30
        }
        
        # Test sending an alert with no recipients
        result = client.send_alert('drift', context)
        
        # Verify the results
        self.assertFalse(result['success'])
        self.assertEqual(result['error'], 'No recipients specified')
        
        # Verify the SMTP server was not used
        mock_smtp.assert_not_called()
    
    @patch('app.core.notification.smtplib.SMTP')
    def test_send_alert_template_error(self, mock_smtp):
        """Test sending an alert with a template error"""
        # Mock the _load_template method
        with patch.object(self.client, '_load_template') as mock_load_template:
            # Set up the mock to return None (template not found)
            mock_load_template.return_value = None
            
            # Test context
            context = {
                'vhost': '/',
                'queue': 'test-queue',
                'current_count': 50,
                'previous_count': 30
            }
            
            # Test sending an alert with a template error
            result = self.client.send_alert('drift', context)
            
            # Verify the results
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Failed to load template: drift')
            
            # Verify the SMTP server was not used
            mock_smtp.assert_not_called()
    
    @patch('app.core.notification.smtplib.SMTP')
    def test_send_alert_missing_context_key(self, mock_smtp):
        """Test sending an alert with a missing context key"""
        # Mock the _load_template method
        with patch.object(self.client, '_load_template') as mock_load_template:
            # Set up the mock to return a template that requires a key not in the context
            from string import Template
            mock_template = Template('<html>Drift alert for {vhost}/{queue}: {missing_key}</html>')
            mock_load_template.return_value = mock_template
            
            # Test context (missing 'missing_key')
            context = {
                'vhost': '/',
                'queue': 'test-queue',
                'current_count': 50,
                'previous_count': 30
            }
            
            # Test sending an alert with a missing context key
            result = self.client.send_alert('drift', context)
            
            # Verify the results
            self.assertFalse(result['success'])
            self.assertTrue(result['error'].startswith('Error formatting template: Missing key'))
            
            # Verify the SMTP server was not used
            mock_smtp.assert_not_called()
    
    @patch('app.core.notification.smtplib.SMTP')
    def test_send_alert_smtp_error(self, mock_smtp):
        """Test sending an alert with an SMTP error"""
        # Mock the _load_template method
        with patch.object(self.client, '_load_template') as mock_load_template:
            # Set up the mock to return a template
            from string import Template
            mock_template = Template('<html>Drift alert for {vhost}/{queue}: {current_count} (was {previous_count})</html>')
            mock_load_template.return_value = mock_template
            
            # Set up the SMTP mock to raise an exception
            mock_smtp.side_effect = Exception('SMTP connection failed')
            
            # Test context
            context = {
                'vhost': '/',
                'queue': 'test-queue',
                'current_count': 50,
                'previous_count': 30
            }
            
            # Test sending an alert with an SMTP error
            result = self.client.send_alert('drift', context)
            
            # Verify the results
            self.assertFalse(result['success'])
            self.assertEqual(result['error'], 'Failed to send email: SMTP connection failed')

if __name__ == "__main__":
    unittest.main()
