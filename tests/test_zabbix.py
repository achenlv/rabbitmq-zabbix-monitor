# tests/test_zabbix.py
import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import platform
import tempfile
import json
from app.core.zabbix import ZabbixClient

class TestZabbixClient(unittest.TestCase):
    """Test cases for the ZabbixClient class"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Create a sample configuration for testing
        self.test_config = {
            'zabbix': {
                'url': 'https://zabbix.example.com',
                'server': 'zabbix-server.example.com',
                'port': 10051,
                'user': 'api-user',
                'password': 'api-password',
                'tls_connect': 'psk',
                'tls_psk_identity': 'PSK_IDENTITY',
                'tls_psk_file': 'C:\\zabbix\\psk.key',
                'tls_psk_file_linux': '/etc/zabbix/psk.key'
            }
        }
        
        # Create the client with the test configuration
        self.client = ZabbixClient(self.test_config)
    
    def test_init(self):
        """Test initialization of the ZabbixClient"""
        self.assertEqual(self.client.url, 'https://zabbix.example.com')
        self.assertEqual(self.client.api_url, 'https://zabbix.example.com/api_jsonrpc.php')
        self.assertEqual(self.client.user, 'api-user')
        self.assertEqual(self.client.password, 'api-password')
        self.assertEqual(self.client.server, 'zabbix-server.example.com')
        self.assertEqual(self.client.port, 10051)
        self.assertEqual(self.client.tls_connect, 'psk')
        self.assertEqual(self.client.tls_psk_identity, 'PSK_IDENTITY')
        
        # Check PSK file path based on platform
        if platform.system() == "Windows":
            self.assertEqual(self.client.tls_psk_file, 'C:\\zabbix\\psk.key')
        else:
            self.assertEqual(self.client.tls_psk_file, 'C:\\zabbix\\psk.key')
            self.assertEqual(self.client.tls_psk_file_linux, '/etc/zabbix/psk.key')
    
    @patch('app.core.zabbix.shutil.which')
    def test_find_zabbix_sender(self, mock_which):
        """Test finding the zabbix_sender executable"""
        # Test when zabbix_sender is in PATH
        mock_which.return_value = '/usr/bin/zabbix_sender'
        self.assertEqual(self.client._find_zabbix_sender(), '/usr/bin/zabbix_sender')
        
        # Test when zabbix_sender is not in PATH but exists in common locations
        mock_which.return_value = None
        
        # Mock platform.system to return "Windows"
        with patch('app.core.zabbix.platform.system', return_value="Windows"):
            # Mock os.path.exists to return True for a Windows path
            with patch('app.core.zabbix.os.path.exists', side_effect=lambda path: path == r"C:\Program Files\Zabbix Agent\zabbix_sender.exe"):
                self.assertEqual(self.client._find_zabbix_sender(), r"C:\Program Files\Zabbix Agent\zabbix_sender.exe")
        
        # Mock platform.system to return "Linux"
        with patch('app.core.zabbix.platform.system', return_value="Linux"):
            # Mock os.path.exists to return True for a Linux path
            with patch('app.core.zabbix.os.path.exists', side_effect=lambda path: path == "/usr/bin/zabbix_sender"):
                self.assertEqual(self.client._find_zabbix_sender(), "/usr/bin/zabbix_sender")
        
        # Test when zabbix_sender is not found anywhere
        with patch('app.core.zabbix.platform.system', return_value="Linux"):
            with patch('app.core.zabbix.os.path.exists', return_value=False):
                self.assertIsNone(self.client._find_zabbix_sender())
    
    def test_get_psk_file_path(self):
        """Test getting the PSK file path"""
        # Test on Windows
        with patch('app.core.zabbix.platform.system', return_value="Windows"):
            with patch('app.core.zabbix.os.path.exists', return_value=True):
                self.assertEqual(self.client._get_psk_file_path(), 'C:\\zabbix\\psk.key')
        
        # Test on Linux with Linux path existing
        with patch('app.core.zabbix.platform.system', return_value="Linux"):
            with patch('app.core.zabbix.os.path.exists', side_effect=lambda path: path == '/etc/zabbix/psk.key'):
                self.assertEqual(self.client._get_psk_file_path(), '/etc/zabbix/psk.key')
        
        # Test on Linux with no paths existing
        with patch('app.core.zabbix.platform.system', return_value="Linux"):
            with patch('app.core.zabbix.os.path.exists', return_value=False):
                self.assertEqual(self.client._get_psk_file_path(), '/etc/zabbix/psk.key')
    
    @patch('app.core.zabbix.requests.post')
    def test_authenticate(self, mock_post):
        """Test authentication with Zabbix API"""
        # Mock successful authentication
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "auth-token-123"}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        # Test with API URL and credentials
        auth_token = self.client.authenticate()
        self.assertEqual(auth_token, "auth-token-123")
        self.assertEqual(self.client._auth, "auth-token-123")
        
        # Verify the API call was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://zabbix.example.com/api_jsonrpc.php')
        self.assertEqual(kwargs['json']['method'], 'user.login')
        self.assertEqual(kwargs['json']['params']['user'], 'api-user')
        self.assertEqual(kwargs['json']['params']['password'], 'api-password')
        
        # Test with token already set
        self.client.token = "existing-token"
        auth_token = self.client.authenticate()
        self.assertEqual(auth_token, "existing-token")
        
        # Test with no API URL
        self.client.api_url = None
        self.client._auth = None
        auth_token = self.client.authenticate()
        self.assertIsNone(auth_token)
    
    @patch('app.core.zabbix.requests.post')
    def test_api_call(self, mock_post):
        """Test making API calls to Zabbix"""
        # Mock successful API call
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [{"hostid": "10084", "host": "test-host"}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        # Set auth token
        self.client._auth = "auth-token-123"
        
        # Test API call
        result = self.client.api_call("host.get", {"filter": {"host": ["test-host"]}})
        self.assertEqual(result, {"result": [{"hostid": "10084", "host": "test-host"}]})
        
        # Verify the API call was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://zabbix.example.com/api_jsonrpc.php')
        self.assertEqual(kwargs['json']['method'], 'host.get')
        self.assertEqual(kwargs['json']['params']['filter']['host'], ['test-host'])
        self.assertEqual(kwargs['json']['auth'], 'auth-token-123')
        
        # Test API call with no auth token
        self.client._auth = None
        
        # Mock authentication
        with patch.object(self.client, 'authenticate', return_value="new-auth-token"):
            result = self.client.api_call("host.get", {"filter": {"host": ["test-host"]}})
            self.assertEqual(result, {"result": [{"hostid": "10084", "host": "test-host"}]})
            self.assertEqual(self.client._auth, "new-auth-token")
        
        # Test API call with authentication failure
        self.client._auth = None
        with patch.object(self.client, 'authenticate', return_value=None):
            result = self.client.api_call("host.get", {"filter": {"host": ["test-host"]}})
            self.assertEqual(result, {"error": "Not authenticated"})
    
    @patch('app.core.zabbix.subprocess.Popen')
    def test_send_value(self, mock_popen):
        """Test sending a value to Zabbix"""
        # Mock successful command execution
        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"Processed: 1; Failed: 0; Total: 1", b"")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        # Mock finding zabbix_sender
        with patch.object(self.client, '_find_zabbix_sender', return_value='/usr/bin/zabbix_sender'):
            # Test sending a value
            result = self.client.send_value("test-host", "test.key", 42)
            self.assertTrue(result["success"])
            self.assertEqual(result["message"], "Processed: 1; Failed: 0; Total: 1")
            self.assertEqual(result["returncode"], 0)
            
            # Verify the command was executed correctly
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0][0], '/usr/bin/zabbix_sender')
            self.assertEqual(args[0][1], '-z')
            self.assertEqual(args[0][2], 'zabbix-server.example.com')
            self.assertEqual(args[0][5], 'test-host')
            self.assertEqual(args[0][7], 'test.key')
            self.assertEqual(args[0][9], '42')
            
            # Test with TLS/PSK options
            mock_popen.reset_mock()
            with patch.object(self.client, '_get_psk_file_path', return_value='/etc/zabbix/psk.key'):
                result = self.client.send_value("test-host", "test.key", 42)
                self.assertTrue(result["success"])
                
                # Verify TLS options were included
                args, kwargs = mock_popen.call_args
                self.assertIn('--tls-connect', args[0])
                self.assertIn('psk', args[0])
                self.assertIn('--tls-psk-identity', args[0])
                self.assertIn('PSK_IDENTITY', args[0])
                self.assertIn('--tls-psk-file', args[0])
                self.assertIn('/etc/zabbix/psk.key', args[0])
        
        # Test when zabbix_sender is not found
        with patch.object(self.client, '_find_zabbix_sender', return_value=None):
            result = self.client.send_value("test-host", "test.key", 42)
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "zabbix_sender not found in PATH or common locations")
        
        # Test when command execution fails
        with patch.object(self.client, '_find_zabbix_sender', return_value='/usr/bin/zabbix_sender'):
            process_mock.communicate.return_value = (b"", b"Error: connection failed")
            result = self.client.send_value("test-host", "test.key", 42)
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "Error: connection failed")
    
    @patch('app.core.zabbix.subprocess.Popen')
    @patch('app.core.zabbix.tempfile.NamedTemporaryFile')
    def test_send_values_to_zabbix(self, mock_tempfile, mock_popen):
        """Test sending multiple values to Zabbix"""
        # Mock temporary file
        mock_file = MagicMock()
        mock_file.name = '/tmp/zabbix_data_12345'
        mock_tempfile.return_value.__enter__.return_value = mock_file
        
        # Mock successful command execution
        process_mock = MagicMock()
        process_mock.communicate.return_value = (b"Processed: 2; Failed: 0; Total: 2", b"")
        process_mock.returncode = 0
        mock_popen.return_value = process_mock
        
        # Test data points
        data_points = [
            {"host": "test-host", "key": "test.key1", "value": 42},
            {"host": "test-host", "key": "test.key2", "value": 100}
        ]
        
        # Mock finding zabbix_sender
        with patch.object(self.client, '_find_zabbix_sender', return_value='/usr/bin/zabbix_sender'):
            # Test sending multiple values
            result = self.client.send_values_to_zabbix(data_points)
            self.assertTrue(result["success"])
            self.assertEqual(result["message"], "Processed: 2; Failed: 0; Total: 2")
            self.assertEqual(result["returncode"], 0)
            
            # Verify the temporary file was written correctly
            mock_file.write.assert_any_call("test-host test.key1 42\n")
            mock_file.write.assert_any_call("test-host test.key2 100\n")
            
            # Verify the command was executed correctly
            mock_popen.assert_called_once()
            args, kwargs = mock_popen.call_args
            self.assertEqual(args[0][0], '/usr/bin/zabbix_sender')
            self.assertEqual(args[0][1], '-z')
            self.assertEqual(args[0][2], 'zabbix-server.example.com')
            self.assertEqual(args[0][5], '-i')
            self.assertEqual(args[0][6], '/tmp/zabbix_data_12345')
            
            # Test with empty data points
            mock_popen.reset_mock()
            result = self.client.send_values_to_zabbix([])
            self.assertTrue(result["success"])
            self.assertEqual(result["message"], "No data points to send")
            mock_popen.assert_not_called()
        
        # Test when zabbix_sender is not found
        with patch.object(self.client, '_find_zabbix_sender', return_value=None):
            result = self.client.send_values_to_zabbix(data_points)
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "zabbix_sender not found in PATH or common locations")
    
    @patch('app.core.zabbix.requests.post')
    def test_get_host(self, mock_post):
        """Test getting host information from Zabbix"""
        # Mock successful API call
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": [{"hostid": "10084", "host": "test-host", "name": "Test Host"}]}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        # Set auth token
        self.client._auth = "auth-token-123"
        
        # Test getting host information
        result = self.client.get_host("test-host")
        self.assertEqual(result, {"result": [{"hostid": "10084", "host": "test-host", "name": "Test Host"}]})
        
        # Verify the API call was made correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['json']['method'], 'host.get')
        self.assertEqual(kwargs['json']['params']['filter']['host'], ['test-host'])
    
    @patch('app.core.zabbix.requests.post')
    def test_get_item_history(self, mock_post):
        """Test getting item history from Zabbix"""
        # Mock successful API calls
        mock_host_response = MagicMock()
        mock_host_response.json.return_value = {"result": [{"hostid": "10084", "host": "test-host"}]}
        
        mock_item_response = MagicMock()
        mock_item_response.json.return_value = {"result": [{"itemid": "28979", "key_": "test.key", "value_type": 0}]}
        
        mock_history_response = MagicMock()
        mock_history_response.json.return_value = {
            "result": [
                {"value": "42", "clock": "1614556800"},
                {"value": "36", "clock": "1614553200"}
            ]
        }
        
        # Set up the mock to return different responses for different API calls
        mock_post.side_effect = [mock_host_response, mock_item_response, mock_history_response]
        
        # Set auth token
        self.client._auth = "auth-token-123"
        
        # Test getting item history
        result = self.client.get_item_history("test-host", "test.key", 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["value"], "42")
        self.assertEqual(result[1]["value"], "36")
        
        # Verify the API calls were made correctly
        self.assertEqual(mock_post.call_count, 3)
        
        # First call: host.get
        args, kwargs = mock_post.call_args_list[0]
        self.assertEqual(kwargs['json']['method'], 'host.get')
        self.assertEqual(kwargs['json']['params']['filter']['host'], ['test-host'])
        
        # Second call: item.get
        args, kwargs = mock_post.call_args_list[1]
        self.assertEqual(kwargs['json']['method'], 'item.get')
        self.assertEqual(kwargs['json']['params']['hostids'], '10084')
        self.assertEqual(kwargs['json']['params']['filter']['key_'], 'test.key')
        
        # Third call: history.get
        args, kwargs = mock_post.call_args_list[2]
        self.assertEqual(kwargs['json']['method'], 'history.get')
        self.assertEqual(kwargs['json']['params']['history'], 0)
        self.assertEqual(kwargs['json']['params']['itemids'], '28979')
        self.assertEqual(kwargs['json']['params']['limit'], 2)
        
        # Test with no authentication
        self.client._auth = None
        with patch.object(self.client, 'authenticate', return_value=None):
            result = self.client.get_item_history("test-host", "test.key", 2)
            self.assertEqual(result, [])
        
        # Test with no host result
        self.client._auth = "auth-token-123"
        mock_post.reset_mock()
        mock_host_response.json.return_value = {"result": []}
        mock_post.side_effect = [mock_host_response]
        result = self.client.get_item_history("test-host", "test.key", 2)
        self.assertEqual(result, [])
        
        # Test with no item result
        mock_post.reset_mock()
        mock_host_response.json.return_value = {"result": [{"hostid": "10084", "host": "test-host"}]}
        mock_item_response.json.return_value = {"result": []}
        mock_post.side_effect = [mock_host_response, mock_item_response]
        result = self.client.get_item_history("test-host", "test.key", 2)
        self.assertEqual(result, [])
        
        # Test with no history result but lastvalue/prevvalue available
        mock_post.reset_mock()
        mock_host_response.json.return_value = {"result": [{"hostid": "10084", "host": "test-host"}]}
        mock_item_response.json.return_value = {"result": [{"itemid": "28979", "key_": "test.key", "lastvalue": "42", "prevvalue": "36"}]}
        mock_history_response.json.return_value = {"result": []}
        mock_post.side_effect = [mock_host_response, mock_item_response, mock_history_response]
        result = self.client.get_item_history("test-host", "test.key", 2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["value"], "42")
        self.assertEqual(result[1]["value"], "36")

if __name__ == "__main__":
    unittest.main()
