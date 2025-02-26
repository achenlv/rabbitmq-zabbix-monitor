#!/usr/bin/env python3
import requests
import subprocess
import logging
import sys
import os

# Set up logging
logging.basicConfig(
  filename='/path/to/rabbitmq-zabbix-monitor/log/service_monitor.log',
  level=logging.INFO,
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def check_service():
  try:
    # Try to connect to the service's health endpoint
    response = requests.get('http://127.0.0.1:5000/health', timeout=5)
    if response.status_code == 200:
      logging.info("Service is running correctly")
      return True
    else:
      logging.error(f"Service returned status code {response.status_code}")
      return False
  except Exception as e:
    logging.error(f"Failed to connect to service: {str(e)}")
    return False

def restart_service():
  try:
    logging.info("Attempting to restart service...")
    subprocess.run(['sudo', 'systemctl', 'restart', 'rabbitmq-zabbix-monitor.service'])
    logging.info("Service restart command sent")
  except Exception as e:
    logging.error(f"Failed to restart service: {str(e)}")

if __name__ == "__main__":
  if not check_service():
    restart_service()