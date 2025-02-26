import logging
import json
import subprocess
from typing import Dict, Optional, Union, List, Tuple
from pyzabbix import ZabbixAPI, ZabbixAPIException
import socket
import ssl
import time
import tempfile

logger = logging.getLogger(__name__)

class ZabbixClient:
    def __init__(self, config):
        self.config = config.get_zabbix_config()
        self.zapi = self._initialize_connection()
        self.tls_config = self._get_tls_config()
        
    def _initialize_connection(self) -> ZabbixAPI:
        """Initialize connection to Zabbix API"""
        try:
            zapi = ZabbixAPI(self.config['url'])
            # zapi.login(self.config['user'], self.config['password'])
            zapi.login(api_token=self.config['token'])
            return zapi
        except Exception as e:
            logger.error(f"Failed to initialize Zabbix connection: {str(e)}")
            raise

    def _get_tls_config(self) -> Dict:
        """Get TLS configuration from config"""
        tls_config = {
            'enabled': False,
            'connect': self.config.get('tls_connect', 'unencrypted'),
            'psk_identity': self.config.get('tls_psk_identity', ''),
            'psk_file': self.config.get('tls_psk_file', ''),
            'psk_key': self.config.get('psk_key', ''),  
            'ca_file': self.config.get('tls_ca_file', ''),
            'cert_file': self.config.get('tls_cert_file', ''),
            'key_file': self.config.get('tls_key_file', '')
        }
        
        # Enable TLS if PSK or cert configuration is present
        if tls_config['connect'] != 'unencrypted':
            tls_config['enabled'] = True
            
        return tls_config

    def _read_psk_key(self, psk_file: str) -> Optional[bytes]:
        """Read PSK key from file"""
        try:
            with open(psk_file, 'r') as f:
                psk_hex = f.read().strip()
                return bytes.fromhex(psk_hex)
        except Exception as e:
            logger.error(f"Failed to read PSK key file: {str(e)}")
            return None

    def _send_to_zabbix_sender(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics using zabbix_sender protocol"""
        # If TLS is enabled, use zabbix_sender command-line tool
        if self.tls_config['enabled']:
            return self._send_with_zabbix_sender_cli(host, key, value)
        
        # Otherwise, use direct socket connection
        return self._send_with_socket(host, key, value)

    def send_value_via_api(self, host: str, key: str, value: int) -> bool:
        """Send value to Zabbix item using the API"""
        try:
            # Find the host ID
            hosts = self.zapi.host.get(
                filter={'host': host},
                output=['hostid']
            )
            
            if not hosts:
                logger.error(f"Host {host} not found in Zabbix")
                return False
                
            hostid = hosts[0]['hostid']
            
            # Find the item ID
            items = self.zapi.item.get(
                hostids=hostid,
                filter={'key_': key},
                output=['itemid']
            )
            
            if not items:
                logger.error(f"Item {key} not found for host {host}")
                return False
                
            itemid = items[0]['itemid']
            
            # Update the value
            current_time = int(time.time())
            self.zapi.history.add({
                "itemid": itemid,
                "clock": current_time,
                "value": str(value),
                "ns": 0
            })
            
            logger.info(f"Successfully sent value to Zabbix via API: {host}:{key}={value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send value via API: {str(e)}")
            return False

    def _send_with_zabbix_sender_cli(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics using zabbix_sender command-line tool with PSK support"""
        try:
            temp_files = []  # Keep track of temporary files to clean up

            # Create a temporary file with the data
            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as tmp:
                tmp.write(f"{host} {key} {value}\n")
                data_file = tmp.name
                temp_files.append(data_file)
            
            # Build the command
            cmd = [
                "zabbix_sender",
                "-z", self.config['server'],
                "-p", str(self.config['port']),
                "-i", data_file,
                "-v"
            ]
            
            # Add PSK parameters
            if self.tls_config['connect'] == 'psk':
                cmd.extend([
                    "--tls-connect", "psk",
                    "--tls-psk-identity", self.tls_config['psk_identity']
                ])
                
                # If we have a PSK key value but no file, create a temporary file
                if self.tls_config.get('psk_key') and not (self.tls_config.get('psk_file') and os.path.exists(self.tls_config['psk_file'])):
                    with tempfile.NamedTemporaryFile(mode='w+', delete=False) as psk_tmp:
                        psk_tmp.write(self.tls_config['psk_key'])
                        psk_file = psk_tmp.name
                        temp_files.append(psk_file)
                    cmd.extend(["--tls-psk-file", psk_file])
                else:
                    # Use the existing PSK file
                    cmd.extend(["--tls-psk-file", self.tls_config['psk_file']])
            
            # Execute the command
            logger.debug(f"Executing command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Clean up all temporary files
            for file in temp_files:
                try:
                    os.unlink(file)
                except Exception as e:
                    logger.warning(f"Error cleaning up temporary file {file}: {str(e)}")
            
            # Log the output for troubleshooting
            if result.stdout:
                logger.debug(f"zabbix_sender stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"zabbix_sender stderr: {result.stderr}")
            
            # Check the result
            if result.returncode == 0 and ("processed: 1" in result.stdout or "sent: 1" in result.stdout):
                logger.info(f"Successfully sent value to Zabbix: {host}:{key}={value}")
                return True
            else:
                logger.error(f"Zabbix sender failed: {result.stdout} {result.stderr}")
                return False
        
        except Exception as e:
            logger.error(f"Error using zabbix_sender: {str(e)}")
            return False
        
    def _send_with_socket(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics directly using Zabbix trapper protocol via socket"""
        try:
            # Prepare data in the format expected by Zabbix
            data = {
                "request": "sender data",
                "data": [
                    {
                        "host": host,
                        "key": key,
                        "value": str(value)
                    }
                ]
            }
            
            # Log the data being sent
            logger.debug(f"Sending to Zabbix server: {json.dumps(data)}")
            
            # Convert to JSON and prepare packet
            json_data = json.dumps(data).encode('utf-8')
            header = b'ZBXD\1' + len(json_data).to_bytes(4, byteorder='little') + b'\0\0\0\0'
            packet = header + json_data
            
            # Create socket and connect
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            
            try:
                logger.debug(f"Connecting to Zabbix server: {self.config['server']}:{self.config['port']}")
                sock.connect((self.config['server'], int(self.config['port'])))
                
                # Send the packet
                sock.sendall(packet)
                
                # Receive response
                response_header = sock.recv(13)
                if len(response_header) < 13:
                    logger.error("Invalid response header from Zabbix server")
                    return False
                    
                response_length = int.from_bytes(response_header[5:9], byteorder='little')
                response_data = sock.recv(response_length)
                
                # Parse response
                response = json.loads(response_data.decode('utf-8'))
                logger.debug(f"Zabbix server response: {response}")
                
                if response.get('response') == 'success':
                    processed = response.get('info', '').split(';')[0].strip()
                    if 'processed: 1' in processed or 'processed 1' in processed:
                        logger.info(f"Successfully sent value to Zabbix: {host}:{key}={value}")
                        return True
                    else:
                        logger.warning(f"Value sent but not processed: {response}")
                        return False
                else:
                    logger.error(f"Zabbix server error: {response}")
                    return False
                    
            finally:
                sock.close()
                
        except Exception as e:
            logger.error(f"Error sending data via socket: {str(e)}")
            return False
    
    def item_exists(self, host: str, key: str) -> bool:
        """Check if item exists in Zabbix"""
        try:
            items = self.zapi.item.get(
                host=host,
                search={'key_': key},
                output=['itemid']
            )
            return len(items) > 0
        except ZabbixAPIException as e:
            logger.error(f"Failed to check item existence: {str(e)}")
            return False

    # def create_item(self, host: str, key: str) -> bool:
    #     """Create new trapper item in Zabbix"""
    #     try:
    #         # Get host ID first
    #         hosts = self.zapi.host.get(
    #             filter={'host': host},
    #             output=['hostid']
    #         )
            
    #         if not hosts:
    #             logger.error(f"Host {host} not found in Zabbix")
    #             return False
                
    #         hostid = hosts[0]['hostid']
            
    #         # Create item
    #         self.zapi.item.create({
    #             'hostid': hostid,
    #             'name': f'RabbitMQ Queue Size: {key}',
    #             'key_': key,
    #             'type': 2,  # Trapper
    #             'value_type': 3,  # Numeric unsigned
    #             'delay': 0,
    #             'history': '7d',
    #             'trends': '90d',
    #             'description': 'RabbitMQ queue message count monitored by rabbitmq-monitor'
    #         })
            
    #         logger.info(f"Created new Zabbix item: {key} for host {host}")
    #         return True
            
    #     except ZabbixAPIException as e:
    #         logger.error(f"Failed to create Zabbix item: {str(e)}")
    #         return False

    def create_item(self, host: str, key: str, name=None) -> bool:
        """Create new trapper item in Zabbix"""
        try:
            # Get host ID first
            hosts = self.zapi.host.get(
                filter={'host': host},
                output=['hostid']
            )
            
            if not hosts:
                logger.error(f"Host {host} not found in Zabbix")
                return False
                
            hostid = hosts[0]['hostid']
            
            # Extract vhost and queue from key for better naming
            parts = key.split('[', 1)
            if len(parts) == 2 and parts[1].endswith(']'):
                params = parts[1][:-1].split(',')
                if len(params) >= 2:
                    vhost = params[0]
                    queue = params[1]
                    if not name:
                        name = f"RabbitMQ Queue Size: {vhost}/{queue}"
            
            if not name:
                name = f"RabbitMQ Queue Size: {key}"
            
            # Create item
            self.zapi.item.create({
                'hostid': hostid,
                'name': name,
                'key_': key,
                'type': 2,  # Trapper
                'value_type': 3,  # Numeric unsigned
                'delay': 0,
                'history': '7d',
                'trends': '90d',
                'description': 'RabbitMQ queue message count monitored by rabbitmq-monitor',
                'units': 'messages'
            })
            
            logger.info(f"Created new Zabbix item: {key} for host {host}")
            return True
            
        except ZabbixAPIException as e:
            logger.error(f"Failed to create Zabbix item: {str(e)}")
            return False

    def get_last_value(self, host: str, key: str) -> Optional[int]:
        """Get last value for given item"""
        try:
            items = self.zapi.item.get(
                host=host,
                search={'key_': key},
                output=['lastvalue']
            )
            
            if items and items[0]['lastvalue']:
                return int(items[0]['lastvalue'])
            return None
            
        except ZabbixAPIException as e:
            logger.error(f"Failed to get last value: {str(e)}")
            return None

    def get_last_two_values(self, host: str, key: str) -> Tuple[Optional[int], Optional[int]]:
        """Get last two values for a Zabbix item"""
        try:
            # Get item ID first
            items = self.zapi.item.get(
                host=host,
                search={'key_': key},
                output=['itemid']
            )
            
            if not items:
                return None, None
                
            itemid = items[0]['itemid']
            
            # Get last 2 history values
            history = self.zapi.history.get(
                itemids=[itemid],
                history=3,  # Numeric unsigned
                sortfield="clock",
                sortorder="DESC",
                limit=2
            )
            
            current_value = int(history[0]['value']) if len(history) > 0 else None
            previous_value = int(history[1]['value']) if len(history) > 1 else None
            
            return current_value, previous_value
            
        except Exception as e:
            logger.error(f"Failed to get history values: {str(e)}")
            return None, None

    def send_value(self, host: str, key: str, value: int) -> bool:
        """Send value to Zabbix trapper item"""
        try:
            logger.debug(f"Attempting to send value to Zabbix: host={host}, key={key}, value={value}")
            
            # Try zabbix_sender CLI method first if PSK is enabled
            if self.tls_config['enabled'] and self.tls_config['connect'] == 'psk':
                logger.debug("Using zabbix_sender CLI method with PSK authentication")
                return self._send_with_zabbix_sender_cli(host, key, value)
            
            # Fall back to direct socket method if PSK is not used
            logger.debug("Using direct socket method")
            return self._send_with_socket(host, key, value)
            
        except Exception as e:
            logger.error(f"Failed to send value to Zabbix: {str(e)}")
            return False