import logging
import json
from typing import Dict, Optional, Union, List
from pyzabbix import ZabbixAPI, ZabbixAPIException
import socket

logger = logging.getLogger(__name__)

class ZabbixClient:
    def __init__(self, config):
        self.config = config.get_zabbix_config()
        self.zapi = self._initialize_connection()
        
    def _initialize_connection(self) -> ZabbixAPI:
        """Initialize connection to Zabbix API"""
        try:
            zapi = ZabbixAPI(self.config['url'])
            zapi.login(self.config['user'], self.config['password'])
            return zapi
        except Exception as e:
            logger.error(f"Failed to initialize Zabbix connection: {str(e)}")
            raise

    def _send_to_zabbix_sender(self, host: str, key: str, value: Union[int, float, str]) -> bool:
        """Send metrics using zabbix_sender protocol"""
        try:
            # Prepare the data packet according to Zabbix sender protocol
            # https://www.zabbix.com/documentation/current/manual/appendix/protocols/header/sender
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
            
            # Convert to JSON and add header
            json_data = json.dumps(data)
            packet = f"ZBXD\1{len(json_data)}\0\0\0\0{json_data}"
            
            # Send to Zabbix server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((self.config['server'], int(self.config['port'])))
                sock.send(packet.encode())
                
                # Read response
                response = sock.recv(1024)
                if b'"response":"success"' in response:
                    return True
                else:
                    logger.error(f"Failed to send data to Zabbix: {response}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error sending data to Zabbix: {str(e)}")
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
                'history': '90d',
                'trends': '365d',
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