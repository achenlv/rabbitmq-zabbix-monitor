import logging
import json
import subprocess
from typing import Dict, Optional, Union, List
from pyzabbix import ZabbixAPI, ZabbixAPIException
import socket
import ssl

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

    def _create_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Create SSL context based on TLS configuration"""
        if not self.tls_config['enabled']:
            return None

        try:
            context = ssl.create_default_context()
            
            if self.tls_config['connect'] == 'psk':
                # PSK-based encryption
                psk_key = self._read_psk_key(self.tls_config['psk_file'])
                if not psk_key:
                    return None
                    
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.maximum_version = ssl.TLSVersion.TLSv1_3
                context.set_ciphers('PSK')
                context.psk_identity = self.tls_config['psk_identity'].encode()
                context.psk = psk_key
                
            elif self.tls_config['connect'] == 'cert':
                # Certificate-based encryption
                if self.tls_config['ca_file']:
                    context.load_verify_locations(self.tls_config['ca_file'])
                if self.tls_config['cert_file'] and self.tls_config['key_file']:
                    context.load_cert_chain(
                        self.tls_config['cert_file'],
                        self.tls_config['key_file']
                    )
                    
            return context
            
        except Exception as e:
            logger.error(f"Failed to create SSL context: {str(e)}")
            return None

    def _send_to_zabbix_sender(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics using zabbix_sender protocol"""
        # If TLS is enabled, use zabbix_sender command-line tool
        if self.tls_config['enabled']:
            return self._send_with_zabbix_sender_cli(host, key, value)
        
        # Otherwise, use direct socket connection
        return self._send_with_socket(host, key, value)

    def _send_with_socket(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics using direct socket connection"""
        try:
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
            
            json_data = json.dumps(data)
            packet = f"ZBXD\1{len(json_data)}\0\0\0\0{json_data}"
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                # Apply TLS if enabled
                ssl_context = self._create_ssl_context()
                if ssl_context:
                    sock = ssl_context.wrap_socket(sock, server_hostname=self.config['server'])
                
                sock.connect((self.config['server'], int(self.config['port'])))
                sock.send(packet.encode())
                
                response = sock.recv(1024)
                if b'"response":"success"' in response:
                    return True
                else:
                    logger.error(f"Failed to send data to Zabbix: {response}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending data to Zabbix: {str(e)}")
            return False

    def _send_with_zabbix_sender_cli(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics using zabbix_sender command-line tool"""
        try:
            # Prepare command with TLS options
            cmd = [
                'zabbix_sender',
                '-z', self.config['server'],
                '-p', str(self.config['port']),
                '-s', host,
                '-k', key,
                '-o', str(value)
            ]
            
            # Add TLS options
            if self.tls_config['connect'] == 'psk':
                cmd.extend([
                    '--tls-connect', 'psk',
                    '--tls-psk-identity', self.tls_config['psk_identity'],
                    '--tls-psk-file', self.tls_config['psk_file']
                ])
            elif self.tls_config['connect'] == 'cert':
                cmd.extend([
                    '--tls-connect', 'cert',
                    '--tls-ca-file', self.tls_config['ca_file']
                ])
                if self.tls_config['cert_file'] and self.tls_config['key_file']:
                    cmd.extend([
                        '--tls-cert-file', self.tls_config['cert_file'],
                        '--tls-key-file', self.tls_config['key_file']
                    ])
            
            # Execute command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            if "processed: 1; failed: 0" in result.stdout:
                return True
            else:
                logger.error(f"Failed to send data via zabbix_sender: {result.stderr}")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"zabbix_sender command failed: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Error using zabbix_sender: {str(e)}")
            return False

    # def _send_to_zabbix_sender(self, host: str, key: str, value: Union[int, float, str]) -> bool:
    #     """Send metrics using zabbix_sender protocol"""
    #     try:
    #         # Prepare the data packet according to Zabbix sender protocol
    #         # https://www.zabbix.com/documentation/current/manual/appendix/protocols/header/sender
    #         data = {
    #             "request": "sender data",
    #             "data": [
    #                 {
    #                     "host": host,
    #                     "key": key,
    #                     "value": str(value)
    #                 }
    #             ]
    #         }
            
    #         # Convert to JSON and add header
    #         json_data = json.dumps(data)
    #         packet = f"ZBXD\1{len(json_data)}\0\0\0\0{json_data}"
            
    #         # Send to Zabbix server
    #         with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    #             sock.connect((self.config['server'], int(self.config['port'])))
    #             sock.send(packet.encode())
                
    #             # Read response
    #             response = sock.recv(1024)
    #             if b'"response":"success"' in response:
    #                 return True
    #             else:
    #                 logger.error(f"Failed to send data to Zabbix: {response}")
    #                 return False
                    
    #     except Exception as e:
    #         logger.error(f"Error sending data to Zabbix: {str(e)}")
    #         return False

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

    def create_item(self, host: str, key: str) -> bool:
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
            
            # Create item
            self.zapi.item.create({
                'hostid': hostid,
                'name': f'RabbitMQ Queue Size: {key}',
                'key_': key,
                'type': 2,  # Trapper
                'value_type': 3,  # Numeric unsigned
                'delay': 0,
                'history': '7d',
                'trends': '90d',
                'description': 'RabbitMQ queue message count monitored by rabbitmq-monitor'
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

    def send_value(self, host: str, key: str, value: int) -> bool:
        """Send value to Zabbix trapper item"""
        try:
            return self._send_to_zabbix_sender(host, key, value)
        except Exception as e:
            logger.error(f"Failed to send value to Zabbix: {str(e)}")
            return False