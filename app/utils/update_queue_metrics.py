#!/usr/bin/env python3
"""
Script to update RabbitMQ queue metrics in Zabbix.
This script is designed to be run as a cron job.

Usage:
  python update_queue_metrics.py [--no-warnings]

Options:
  --no-warnings    Don't check for threshold warnings
"""

import os
import sys
import logging
import requests
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/rabbitmq-zabbix-monitor/update_metrics.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('update_queue_metrics')

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Update RabbitMQ queue metrics in Zabbix')
    parser.add_argument('--no-warnings', action='store_true', help="Don't check for threshold warnings")
    parser.add_argument('--no-emails', action='store_true', help="Don't send email notifications")
    return parser.parse_args()
    return parser.parse_args()

def update_metrics(api_url, check_threshold=True):
    """Update RabbitMQ queue metrics in Zabbix"""
    try:
        # Send request to the API
        url = f"{api_url}/api/zabbix/update-queue-metrics"
        response = requests.post(
            url,
            json={"check_threshold": check_threshold},
            timeout=30
        )
        
        # Check response
        if response.status_code == 200:
            data = response.json()
            updated_count = len(data.get('updated_items', []))
            warnings_count = len(data.get('warnings', []))
            
            logger.info(f"Successfully updated {updated_count} queue metrics")
            
            if warnings_count > 0:
                logger.warning(f"Found {warnings_count} queue warnings")
                
                # Log each warning
                for warning in data.get('warnings', []):
                    logger.warning(
                        f"Warning for {warning.get('host')}:{warning.get('key')} - "
                        f"Value increased from {warning.get('previous_value')} to {warning.get('current_value')} "
                        f"({warning.get('increase_percentage')}%)"
                    )
            
            return True, data
        else:
            logger.error(f"API request failed: {response.status_code} - {response.text}")
            return False, response.text
            
    except Exception as e:
        logger.error(f"Error updating metrics: {str(e)}")
        return False, str(e)

def main():
    """Main function"""
    args = parse_args()
    
    # Get API URL from environment or use default
    api_url = os.environ.get('API_URL', 'http://localhost:5000')
    
    logger.info(f"Starting queue metrics update at {datetime.now().isoformat()}")
    
    # Update metrics
    success, data = update_metrics(api_url, not args.no_warnings)
    
    if success:
        logger.info("Metrics update completed successfully")
    else:
        logger.error(f"Metrics update failed: {data}")
        sys.exit(1)

if __name__ == '__main__':
    main()