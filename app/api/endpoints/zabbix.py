import logging
from typing import Dict, List, Optional, Tuple
from app.utils.config import config
from app.core.rabbitmq import RabbitMQClient
from flask import Blueprint, jsonify, request
from app.core.email import EmailSender
import requests
import os

# Import the ZabbixClient
from app.core.zabbix import ZabbixClient

bp = Blueprint('zabbix', __name__, url_prefix='/api/zabbix')
logger = logging.getLogger(__name__)

# Global EmailSender instance
# Global ZabbixClient instance
_zabbix_client = None

def get_zabbix_client():
    """Get or initialize the ZabbixClient instance"""
    global _zabbix_client
    if _zabbix_client is None:
        _zabbix_client = ZabbixClient(config)
    return _zabbix_client

_email_sender = None

def get_email_sender():
    """Get or initialize the EmailSender instance"""
    global _email_sender
    if _email_sender is None:
        _email_sender = EmailSender()
    return _email_sender


@bp.route('/health', methods=['GET'])
def health_check():
    """
    Zabbix Health Check
    Checks the connection to Zabbix API
    ---
    tags:
      - Zabbix
    responses:
      200:
        description: Zabbix connection status
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            api_version:
              type: string
              example: 6.0.0
      500:
        description: Error connecting to Zabbix
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        client = get_zabbix_client()
        api_version = client.zapi.api_version()
        
        return jsonify({
            "status": "ok",
            "api_version": api_version
        })
    except Exception as e:
        logger.error(f"Zabbix health check failed: {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@bp.route('/update-queue-metrics', methods=['POST'])
def update_queue_metrics():
    """
    Update Queue Metrics in Zabbix
    Updates Zabbix with the latest message_ready counts for monitored queues
    ---
    tags:
      - Zabbix
    parameters:
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            cluster_id:
              type: string
              description: RabbitMQ cluster ID (optional)
            check_threshold:
              type: boolean
              description: Whether to check for threshold warnings
              default: true
    responses:
      200:
        description: Update results
        schema:
          type: object
          properties:
            success:
              type: boolean
            updated_items:
              type: array
              items:
                type: object
                properties:
                  host:
                    type: string
                  key:
                    type: string
                  value:
                    type: integer
                  previous_value:
                    type: integer
                  status:
                    type: string
            warnings:
              type: array
              items:
                type: object
                properties:
                  host:
                    type: string
                  key:
                    type: string
                  current_value:
                    type: integer
                  previous_value:
                    type: integer
                  increase_percentage:
                    type: number
      500:
        description: Error updating metrics
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        # Add a parameter to accept the send_emails option
        send_emails = data.get('send_emails', True)

        data = request.json or {}
        cluster_id = data.get('cluster_id')
        check_threshold = data.get('check_threshold', True)
        
        # Initialize clients
        zabbix_client = get_zabbix_client()

        # Initialize the email sender if needed
        if send_emails:
            email_sender = get_email_sender()

        # Get monitoring configuration
        monitoring_config = config.get_monitoring_config()
        monitored_queues = monitoring_config.get('queues', [])
        threshold_percentage = monitoring_config.get('threshold', 10)
        
        # Filter by cluster_id if specified
        if cluster_id:
            monitored_queues = [q for q in monitored_queues if q.get('cluster_id') == cluster_id]
        
        # Create a map of cluster IDs to clients
        rabbitmq_config = config.get_rabbitmq_config()
        cluster_clients = {}
        
        for cluster in rabbitmq_config.get('clusters', []):
            cluster_id = cluster.get('id')
            if cluster_id:
                cluster_clients[cluster_id] = RabbitMQClient(cluster)
        
        # Results storage
        updated_items = []
        warnings = []
        
        # Process each monitored queue
        for queue_config in monitored_queues:
            try:
                cluster_id = queue_config.get('cluster_id')
                vhost = queue_config.get('vhost')
                queue = queue_config.get('queue')
                zabbix_host = queue_config.get('zabbix_host')
                
                if not all([cluster_id, vhost, queue, zabbix_host]):
                    logger.warning(f"Incomplete queue configuration: {queue_config}")
                    continue
                
                if cluster_id not in cluster_clients:
                    logger.warning(f"No client found for cluster ID: {cluster_id}")
                    continue
                
                # Get RabbitMQ client for this cluster
                rabbitmq_client = cluster_clients[cluster_id]
                
                # Get current message_ready count
                messages_ready = get_queue_messages_ready(rabbitmq_client, vhost, queue)
                
                if messages_ready is None:
                    logger.warning(f"Could not get messages_ready for {vhost}/{queue}")
                    continue
                
                # Construct Zabbix item key
                item_key = f"rabbitmq.queue.messages_ready[{vhost}.{queue}]"
                
                # Check if item exists in Zabbix
                if not zabbix_client.item_exists(zabbix_host, item_key):
                    logger.info(f"Creating Zabbix item: {item_key} for host {zabbix_host}")
                    zabbix_client.create_item(zabbix_host, item_key)
                
                # Get previous value before updating
                previous_value = zabbix_client.get_last_value(zabbix_host, item_key)
                
                # Send value to Zabbix
                send_result = zabbix_client.send_value(zabbix_host, item_key, messages_ready)
                
                update_status = {
                    "host": zabbix_host,
                    "key": item_key,
                    "value": messages_ready,
                    "previous_value": previous_value,
                    "status": "success" if send_result else "failed"
                }
                
                updated_items.append(update_status)
                
                # Check for threshold warnings
                if check_threshold and previous_value is not None and messages_ready > previous_value:
                    increase = messages_ready - previous_value
                    increase_percentage = (increase / previous_value * 100) if previous_value > 0 else 100
                    
                    if increase_percentage > threshold_percentage:
                        warning = {
                            "host": zabbix_host,
                            "key": item_key,
                            "current_value": messages_ready,
                            "previous_value": previous_value,
                            "increase": increase,
                            "increase_percentage": round(increase_percentage, 2)
                        }
                        warnings.append(warning)
                        logger.warning(f"Threshold warning: {warning}")

                # Send email notification
                if send_emails:
                    try:
                        email_result = email_sender.send_drift_alert(
                            queue_info=warning["queue_info"],
                            current_value=messages_ready,
                            previous_value=previous_value,
                            increase_percentage=increase_percentage
                        )
                        
                        email_status = {
                            "queue": f"{vhost}/{queue}",
                            "subject": f"Queue Size Drift Alert: {vhost}/{queue}",
                            "status": "sent" if email_result else "failed"
                        }
                        emails_sent.append(email_status)
                        
                    except Exception as e:
                        logger.error(f"Error sending email alert: {str(e)}")
                        emails_sent.append({
                            "queue": f"{vhost}/{queue}",
                            "status": "failed",
                            "error": str(e)
                        })

            except Exception as e:
                logger.error(f"Error processing queue {queue_config}: {str(e)}")
        
        return jsonify({
            "success": True,
            "updated_items": updated_items,
            "warnings": warnings
        })
        
    except Exception as e:
        logger.error(f"Error updating queue metrics: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/queue-metrics', methods=['GET'])
def get_queue_metrics():
    """
    Get Queue Metrics from Zabbix
    Retrieves the latest message_ready values from Zabbix for monitored queues
    ---
    tags:
      - Zabbix
    parameters:
      - name: cluster_id
        in: query
        type: string
        required: false
        description: Filter by cluster ID
      - name: with_warnings
        in: query
        type: boolean
        required: false
        description: Only show queues with threshold warnings
    responses:
      200:
        description: Queue metrics
        schema:
          type: object
          properties:
            metrics:
              type: array
              items:
                type: object
                properties:
                  cluster_id:
                    type: string
                  vhost:
                    type: string
                  queue:
                    type: string
                  zabbix_host:
                    type: string
                  current_value:
                    type: integer
                  previous_value:
                    type: integer
                  status:
                    type: string
                  warning:
                    type: boolean
            warnings_count:
              type: integer
      500:
        description: Error retrieving metrics
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        cluster_id = request.args.get('cluster_id')
        with_warnings = request.args.get('with_warnings', 'false').lower() == 'true'
        
        # Initialize clients
        zabbix_client = get_zabbix_client()
        
        # Get monitoring configuration
        monitoring_config = config.get_monitoring_config()
        monitored_queues = monitoring_config.get('queues', [])
        threshold_percentage = monitoring_config.get('threshold', 10)
        
        # Filter by cluster_id if specified
        if cluster_id:
            monitored_queues = [q for q in monitored_queues if q.get('cluster_id') == cluster_id]
        
        metrics = []
        warnings_count = 0
        
        # Process each monitored queue
        for queue_config in monitored_queues:
            try:
                queue_cluster_id = queue_config.get('cluster_id')
                vhost = queue_config.get('vhost')
                queue = queue_config.get('queue')
                zabbix_host = queue_config.get('zabbix_host')
                
                if not all([queue_cluster_id, vhost, queue, zabbix_host]):
                    continue
                
                # Construct Zabbix item key
                item_key = f"rabbitmq.queue.messages_ready[{vhost}.{queue}]"
                
                # Check if item exists in Zabbix
                if not zabbix_client.item_exists(zabbix_host, item_key):
                    continue
                
                # Get current and history values from Zabbix
                current_value, previous_value = get_last_two_values(zabbix_client, zabbix_host, item_key)
                
                warning = False
                
                # Check if this queue has a warning
                if previous_value is not None and current_value > previous_value:
                    increase = current_value - previous_value
                    increase_percentage = (increase / previous_value * 100) if previous_value > 0 else 100
                    
                    if increase_percentage > threshold_percentage:
                        warning = True
                        warnings_count += 1
                
                # Skip non-warning queues if with_warnings is True
                if with_warnings and not warning:
                    continue
                
                metric = {
                    "cluster_id": queue_cluster_id,
                    "vhost": vhost,
                    "queue": queue,
                    "zabbix_host": zabbix_host,
                    "current_value": current_value,
                    "previous_value": previous_value,
                    "status": "warning" if warning else "normal",
                    "warning": warning
                }
                
                if warning and previous_value is not None:
                    increase = current_value - previous_value
                    increase_percentage = (increase / previous_value * 100) if previous_value > 0 else 100
                    metric["increase"] = increase
                    metric["increase_percentage"] = round(increase_percentage, 2)
                
                metrics.append(metric)
                
            except Exception as e:
                logger.error(f"Error processing queue {queue_config}: {str(e)}")
        
        return jsonify({
            "metrics": metrics,
            "warnings_count": warnings_count
        })
        
    except Exception as e:
        logger.error(f"Error retrieving queue metrics: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Helper functions

def get_queue_messages_ready(rabbitmq_client, vhost: str, queue: str) -> Optional[int]:
    """Get messages_ready for a specific queue"""
    try:
        # Use primary node to get queue data
        primary_node = rabbitmq_client.primary_node['hostname']
        
        # Get queue data
        messages_ready_counts = rabbitmq_client.get_messages_ready_count(vhost, queue)
        
        # The key should be in the format vhost/queue
        key = f"{vhost}/{queue}"
        
        if key in messages_ready_counts:
            return messages_ready_counts[key]
        
        return None
    except Exception as e:
        logger.error(f"Error getting messages_ready for {vhost}/{queue}: {str(e)}")
        return None

def get_last_two_values(zabbix_client, host: str, key: str) -> Tuple[Optional[int], Optional[int]]:
    """Get last two values for a Zabbix item"""
    try:
        # Get history for the item
        items = zabbix_client.zapi.item.get(
            host=host,
            search={'key_': key},
            output=['itemid']
        )
        
        if not items:
            return None, None
            
        itemid = items[0]['itemid']
        
        # Get last 2 history values
        history = zabbix_client.zapi.history.get(
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
    
@bp.route('/send-drift-alert', methods=['POST'])
def send_drift_alert():
    """
    Send Drift Alert Email
    Manually sends a drift alert email for a specific queue
    ---
    tags:
      - Zabbix
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            cluster_id:
              type: string
              required: true
              description: RabbitMQ cluster ID
            vhost:
              type: string
              required: true
              description: Virtual host
            queue:
              type: string
              required: true
              description: Queue name
            current_value:
              type: integer
              required: true
              description: Current message_ready count
            previous_value:
              type: integer
              required: true
              description: Previous message_ready count
    responses:
      200:
        description: Email sending result
        schema:
          type: object
          properties:
            success:
              type: boolean
            message:
              type: string
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Error sending email
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Validate required fields
        required_fields = ['cluster_id', 'vhost', 'queue', 'current_value', 'previous_value']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Get queue information
        cluster_id = data['cluster_id']
        vhost = data['vhost']
        queue = data['queue']
        current_value = int(data['current_value'])
        previous_value = int(data['previous_value'])
        
        # Get monitoring configuration for zabbix_host
        monitoring_config = config.get_monitoring_config()
        queues = monitoring_config.get('queues', [])
        
        # Find matching queue config
        queue_config = None
        for q in queues:
            if (q.get('cluster_id') == cluster_id and 
                q.get('vhost') == vhost and 
                q.get('queue') == queue):
                queue_config = q
                break
                
        if not queue_config:
            return jsonify({"error": f"Queue not found in monitoring configuration"}), 404
            
        # Calculate increase percentage
        if previous_value > 0:
            increase_percentage = ((current_value - previous_value) / previous_value) * 100
        else:
            increase_percentage = 100  # If previous value was 0
            
        # Send email
        email_sender = get_email_sender()
        result = email_sender.send_drift_alert(
            queue_info=queue_config,
            current_value=current_value,
            previous_value=previous_value,
            increase_percentage=increase_percentage
        )
        
        if result:
            return jsonify({
                "success": True,
                "message": f"Drift alert email sent for {vhost}/{queue}"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to send drift alert email"
            }), 500
            
    except Exception as e:
        logger.error(f"Error sending drift alert email: {str(e)}")
        return jsonify({"error": str(e)}), 500    
    
@bp.route('/update-queue-sizes', methods=['GET'])
def update_queue_sizes():
    """
    Update Queue Sizes in Zabbix
    Fetches all queue messages_ready counts from RabbitMQ API and updates Zabbix items
    ---
    tags:
      - Zabbix
    responses:
      200:
        description: Update results
        schema:
          type: object
          properties:
            success:
              type: boolean
            updated_count:
              type: integer
            results:
              type: array
              items:
                type: object
                properties:
                  queue:
                    type: string
                  host:
                    type: string
                  key:
                    type: string
                  value:
                    type: integer
                  status:
                    type: string
      500:
        description: Error updating queue sizes
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        # Get RabbitMQ queue data
        response = requests.get('http://127.0.0.1:5000/api/rabbitmq/messages-ready')
        response.raise_for_status()
        
        queue_data = response.json().get('messages_ready', {})
        if not queue_data:
            return jsonify({"error": "No queue data returned from RabbitMQ API"}), 500
        
        # Initialize Zabbix client
        zabbix_client = get_zabbix_client()
        
        # Validate Zabbix configuration
        if not zabbix_client.config.get('server') or not zabbix_client.config.get('port'):
            return jsonify({"error": "Zabbix server configuration incomplete"}), 500
            
        if zabbix_client.tls_config.get('connect') == 'psk':
            if not zabbix_client.tls_config.get('psk_identity'):
                return jsonify({"error": "Zabbix PSK identity not configured"}), 500
                
            # Check for either psk_file or psk_key
            has_psk_file = zabbix_client.tls_config.get('psk_file') and os.path.exists(zabbix_client.tls_config.get('psk_file'))
            has_psk_key = zabbix_client.tls_config.get('psk_key')
            
            if not (has_psk_file or has_psk_key):
                return jsonify({"error": "Neither PSK file nor PSK key value is available"}), 500
        
        # Get RabbitMQ configuration to map cluster IDs to hosts
        rabbitmq_config = config.get_rabbitmq_config()
        clusters = rabbitmq_config.get('clusters', [])
        
        # Create a mapping of cluster IDs to zabbix_hosts
        cluster_hosts = {}
        for cluster in clusters:
            cluster_id = cluster.get('id')
            if not cluster_id:
                continue
                
            for node in cluster.get('nodes', []):
                if node.get('primary', False) and 'zabbix_host' in node:
                    cluster_hosts[cluster_id] = node['zabbix_host']
                    break
            
            # If no primary node found, use the first node with zabbix_host
            if cluster_id not in cluster_hosts:
                for node in cluster.get('nodes', []):
                    if 'zabbix_host' in node:
                        cluster_hosts[cluster_id] = node['zabbix_host']
                        break
        
        # Process each queue
        results = []
        updated_count = 0
        
        for queue_key, message_count in queue_data.items():
            try:
                # Parse queue key format "cluster_id:vhost/queue"
                parts = queue_key.split(':', 1)
                if len(parts) != 2:
                    logger.warning(f"Invalid queue key format: {queue_key}")
                    continue
                
                cluster_id = parts[0]
                vhost_queue = parts[1]
                
                # Parse vhost and queue
                vhost_queue_parts = vhost_queue.split('/', 1)
                if len(vhost_queue_parts) != 2:
                    logger.warning(f"Invalid vhost/queue format: {vhost_queue}")
                    continue
                
                vhost = vhost_queue_parts[0]
                queue = vhost_queue_parts[1]
                
                # Get Zabbix host for this cluster
                zabbix_host = cluster_hosts.get(cluster_id)
                if not zabbix_host:
                    logger.warning(f"No Zabbix host found for cluster: {cluster_id}")
                    continue
                
                # Construct Zabbix item key
                item_key = f"rabbitmq.test.queue.size[{vhost},{queue}]"
                
                # Check if item exists, create if not
                if not zabbix_client.item_exists(zabbix_host, item_key):
                    logger.info(f"Creating new Zabbix item: {item_key} for host {zabbix_host}")
                    zabbix_client.create_item(zabbix_host, item_key)
                
                # Update the item value
                logger.debug(f"Sending value to Zabbix: host={zabbix_host}, key={item_key}, value={message_count}")
                success = zabbix_client.send_value(zabbix_host, item_key, message_count)
                
                status = "success" if success else "failed"
                if success:
                    updated_count += 1
                
                results.append({
                    "queue": queue_key,
                    "host": zabbix_host,
                    "key": item_key,
                    "value": message_count,
                    "status": status
                })
                
                logger.info(f"Updated Zabbix item {item_key} with value {message_count} ({status})")
                
            except Exception as e:
                logger.error(f"Error processing queue {queue_key}: {str(e)}")
                results.append({
                    "queue": queue_key,
                    "status": "error",
                    "error": str(e)
                })
        
        return jsonify({
            "success": True,
            "updated_count": updated_count,
            "results": results
        })
        
    except requests.RequestException as e:
        logger.error(f"Error fetching queue data from RabbitMQ API: {str(e)}")
        return jsonify({"error": f"Error fetching queue data: {str(e)}"}), 500
        
    except Exception as e:
        logger.error(f"Error updating queue sizes: {str(e)}")
        return jsonify({"error": str(e)}), 500