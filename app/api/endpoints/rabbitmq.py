from flask import Blueprint, jsonify, request
import logging
from typing import Dict, List, Optional
from app.utils.config import config
from app.core.rabbitmq import RabbitMQClient

bp = Blueprint('rabbitmq', __name__, url_prefix='/api/rabbitmq')
logger = logging.getLogger(__name__)

# Dictionary to store RabbitMQ client instances by cluster ID
_clients = {}

def get_client_for_cluster(cluster_id: str) -> RabbitMQClient:
    """Get or create a RabbitMQ client for a specific cluster ID"""
    if cluster_id not in _clients:
        # Find the cluster config for this ID
        rabbitmq_config = config.get_rabbitmq_config()
        
        for cluster in rabbitmq_config['clusters']:
            if cluster.get('id') == cluster_id:
                _clients[cluster_id] = RabbitMQClient(cluster)
                break
        else:
            # If no matching cluster found
            raise ValueError(f"No configuration found for RabbitMQ cluster ID: {cluster_id}")
    
    return _clients[cluster_id]

def get_client_for_node(node_hostname: str) -> tuple:
    """Get or create a RabbitMQ client for a specific node, returns (client, cluster_id)"""
    # Find the cluster that contains this node
    rabbitmq_config = config.get_rabbitmq_config()
    
    for cluster in rabbitmq_config['clusters']:
        for node in cluster.get('nodes', []):
            if node.get('hostname') == node_hostname:
                cluster_id = cluster.get('id')
                if cluster_id not in _clients:
                    _clients[cluster_id] = RabbitMQClient(cluster)
                return _clients[cluster_id], cluster_id
    
    # If no matching node found
    raise ValueError(f"No cluster configuration found for node: {node_hostname}")

@bp.route('/clusters', methods=['GET'])
def get_clusters():
    """
    Get All RabbitMQ Clusters
    Returns a list of all configured RabbitMQ clusters
    ---
    tags:
      - RabbitMQ
    responses:
      200:
        description: List of clusters
        schema:
          type: object
          properties:
            clusters:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  description:
                    type: string
                  nodes:
                    type: array
                    items:
                      type: string
      500:
        description: Error retrieving clusters
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        rabbitmq_config = config.get_rabbitmq_config()
        clusters = []
        
        for cluster in rabbitmq_config.get('clusters', []):
            # Extract relevant information
            cluster_info = {
                'id': cluster.get('id', 'unknown'),
                'description': cluster.get('description', 'Unknown Cluster'),
                'nodes': [node.get('hostname') for node in cluster.get('nodes', [])]
            }
            clusters.append(cluster_info)
        
        return jsonify({"clusters": clusters})
    except Exception as e:
        logger.error(f"Error retrieving clusters: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/health', methods=['GET'])
def health():
    """
    Check RabbitMQ Cluster Health
    Checks the health of all configured RabbitMQ clusters
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: query
        type: string
        required: false
        description: Specific cluster ID to check (optional)
      - name: node
        in: query
        type: string
        required: false
        description: Specific node to check (optional)
    responses:
      200:
        description: Health status of RabbitMQ clusters
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            clusters:
              type: array
              items:
                type: object
                properties:
                  id:
                    type: string
                  description:
                    type: string
                  status:
                    type: string
                  nodes:
                    type: array
                    items:
                      type: object
                      properties:
                        hostname:
                          type: string
                        status:
                          type: string
      500:
        description: Error checking health
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        cluster_id = request.args.get('cluster_id')
        node = request.args.get('node')
        rabbitmq_config = config.get_rabbitmq_config()
        
        health_results = []
        overall_status = "ok"
        
        # Function to check a single cluster
        def check_cluster(cluster):
            cluster_health = {
                "id": cluster.get('id', 'unknown'),
                "description": cluster.get('description', 'Unknown Cluster'),
                "status": "ok",
                "nodes": []
            }
            
            try:
                # Create client for this cluster
                client = RabbitMQClient(cluster)
                
                # Check health for each node
                for node_config in cluster.get('nodes', []):
                    node_hostname = node_config.get('hostname')
                    
                    # Skip if specific node requested and this isn't it
                    if node and node != node_hostname:
                        continue
                        
                    try:
                        is_healthy = client.check_node_health(node_hostname)
                        node_status = {
                            "hostname": node_hostname,
                            "status": "ok" if is_healthy else "error"
                        }
                        
                        if not is_healthy:
                            cluster_health["status"] = "error"
                            
                        cluster_health["nodes"].append(node_status)
                    except Exception as e:
                        cluster_health["status"] = "error"
                        cluster_health["nodes"].append({
                            "hostname": node_hostname,
                            "status": "error",
                            "message": str(e)
                        })
                
                return cluster_health
            except Exception as e:
                logger.error(f"Error checking cluster {cluster.get('id')}: {str(e)}")
                return {
                    "id": cluster.get('id', 'unknown'),
                    "description": cluster.get('description', 'Unknown Cluster'),
                    "status": "error",
                    "message": str(e)
                }
        
        # Process clusters based on request params
        if cluster_id:
            # Check specific cluster
            for cluster in rabbitmq_config.get('clusters', []):
                if cluster.get('id') == cluster_id:
                    cluster_health = check_cluster(cluster)
                    health_results.append(cluster_health)
                    
                    if cluster_health["status"] == "error":
                        overall_status = "error"
                    break
            else:
                return jsonify({"error": f"Cluster ID {cluster_id} not found"}), 404
        else:
            # Check all clusters
            for cluster in rabbitmq_config.get('clusters', []):
                cluster_health = check_cluster(cluster)
                health_results.append(cluster_health)
                
                if cluster_health["status"] == "error":
                    overall_status = "error"
        
        return jsonify({
            "status": overall_status,
            "clusters": health_results
        })
    except Exception as e:
        logger.error(f"Error checking RabbitMQ health: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/queues', methods=['GET'])
def get_queues():
    """
    Get RabbitMQ Queues
    Returns a list of all queues from RabbitMQ
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: query
        type: string
        required: false
        description: Filter by cluster ID
      - name: node
        in: query
        type: string
        required: false
        description: Filter by node hostname
      - name: vhost
        in: query
        type: string
        required: false
        description: Filter by vhost
    responses:
      200:
        description: List of queues
        schema:
          type: object
          properties:
            queues:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  vhost:
                    type: string
                  messages:
                    type: integer
                  consumers:
                    type: integer
                  cluster_id:
                    type: string
                  node:
                    type: string
      500:
        description: Error retrieving queues
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        cluster_id = request.args.get('cluster_id')
        node = request.args.get('node')
        vhost = request.args.get('vhost')
        
        rabbitmq_config = config.get_rabbitmq_config()
        all_queues = []
        
        # Function to get queues from a cluster
        def get_cluster_queues(cluster):
            try:
                client = RabbitMQClient(cluster)
                cluster_id = cluster.get('id', 'unknown')
                
                queues = client.get_queues(vhost)
                
                # Add cluster info to each queue
                for queue in queues:
                    queue['cluster_id'] = cluster_id
                
                return queues
            except Exception as e:
                logger.error(f"Error getting queues from cluster {cluster.get('id')}: {str(e)}")
                return []
        
        # If specific cluster requested
        if cluster_id:
            for cluster in rabbitmq_config.get('clusters', []):
                if cluster.get('id') == cluster_id:
                    all_queues.extend(get_cluster_queues(cluster))
                    break
            else:
                return jsonify({"error": f"Cluster ID {cluster_id} not found"}), 404
        
        # If specific node requested
        elif node:
            found = False
            for cluster in rabbitmq_config.get('clusters', []):
                for node_config in cluster.get('nodes', []):
                    if node_config.get('hostname') == node:
                        all_queues.extend(get_cluster_queues(cluster))
                        found = True
                        break
                if found:
                    break
            
            if not found:
                return jsonify({"error": f"Node {node} not found in any cluster"}), 404
        
        # Otherwise get from all clusters
        else:
            for cluster in rabbitmq_config.get('clusters', []):
                all_queues.extend(get_cluster_queues(cluster))
        
        return jsonify({"queues": all_queues})
    except Exception as e:
        logger.error(f"Error retrieving queues: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/queues/<cluster_id>/<vhost>/<queue>', methods=['GET'])
def get_queue_details(cluster_id: str, vhost: str, queue: str):
    """
    Get Queue Details
    Returns detailed information about a specific queue
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: path
        type: string
        required: true
        description: RabbitMQ cluster ID
      - name: vhost
        in: path
        type: string
        required: true
        description: Virtual host
      - name: queue
        in: path
        type: string
        required: true
        description: Queue name
    responses:
      200:
        description: Queue details
        schema:
          type: object
          properties:
            name:
              type: string
            vhost:
              type: string
            messages:
              type: integer
            consumers:
              type: integer
            state:
              type: string
      404:
        description: Queue or cluster not found
      500:
        description: Error retrieving queue details
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        # Get client for this cluster
        try:
            client = get_client_for_cluster(cluster_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        
        # Use primary node to get queue details
        primary_node = client.primary_node['hostname']
        
        try:
            # Modified this to return full queue info, not just message count
            encoded_vhost = vhost.replace('/', '%2F')
            encoded_queue = queue.replace('/', '%2F')
            path = f"queues/{encoded_vhost}/{encoded_queue}"
            
            queue_data = client._make_request('GET', path, primary_node)
            
            if not queue_data:
                return jsonify({"error": f"Queue {vhost}/{queue} not found"}), 404
                
            # Add cluster info
            queue_data['cluster_id'] = cluster_id
            
            return jsonify(queue_data)
            
        except Exception as e:
            return jsonify({"error": f"Error retrieving queue details: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"Error retrieving queue details: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/monitor/queues', methods=['GET'])
def get_monitored_queues():
    """
    Get Monitored Queues
    Returns the list of queues being monitored as defined in config
    ---
    tags:
      - RabbitMQ
    responses:
      200:
        description: List of monitored queues
        schema:
          type: object
          properties:
            queues:
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
                  current_message_count:
                    type: integer
      500:
        description: Error retrieving monitored queues
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        monitoring_config = config.get_monitoring_config()
        queues = monitoring_config.get('queues', [])
        
        # Create a map of cluster IDs to clients
        rabbitmq_config = config.get_rabbitmq_config()
        cluster_clients = {}
        
        for cluster in rabbitmq_config.get('clusters', []):
            cluster_id = cluster.get('id')
            if cluster_id:
                cluster_clients[cluster_id] = RabbitMQClient(cluster)
        
        # Enhance with current message counts if possible
        for queue_config in queues:
            try:
                cluster_id = queue_config.get('cluster_id')
                vhost = queue_config.get('vhost')
                queue = queue_config.get('queue')
                
                if cluster_id and vhost and queue and cluster_id in cluster_clients:
                    client = cluster_clients[cluster_id]
                    
                    # Use primary node to get message count
                    primary_node = client.primary_node['hostname']
                    
                    message_count = client.get_queue_message_count(primary_node, vhost, queue)
                    
                    if message_count is not None:
                        queue_config['current_message_count'] = message_count
            except Exception as e:
                logger.warning(f"Could not get message count for {vhost}/{queue}: {str(e)}")
        
        return jsonify({"queues": queues})
        
    except Exception as e:
        logger.error(f"Error retrieving monitored queues: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/cluster/<cluster_id>/status', methods=['GET'])
def get_cluster_status(cluster_id: str):
    """
    Get Cluster Status
    Returns the status of a specific RabbitMQ cluster
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: path
        type: string
        required: true
        description: RabbitMQ cluster ID
    responses:
      200:
        description: Cluster status
        schema:
          type: object
          properties:
            id:
              type: string
            description:
              type: string
            name:
              type: string
            nodes:
              type: array
              items:
                type: object
                properties:
                  hostname:
                    type: string
                  status:
                    type: string
                  running:
                    type: boolean
                  memory_used:
                    type: integer
                  disk_free:
                    type: integer
      404:
        description: Cluster not found
      500:
        description: Error retrieving cluster status
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        # Get client for this cluster
        try:
            client = get_client_for_cluster(cluster_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        
        # Get cluster name
        cluster_name_data = client.get_cluster_status()
        cluster_name = cluster_name_data.get('name', 'unknown')
        
        # Get status for each node
        nodes_status = []
        
        for node_config in client.node_configs:
            hostname = node_config.get('hostname')
            
            try:
                # Get node details
                node_info = client.get_node_info(hostname)
                
                node_status = {
                    "hostname": hostname,
                    "status": "ok",
                    "running": node_info.get('running', False),
                    "type": node_info.get('type', 'unknown'),
                    "uptime": node_info.get('uptime', 0),
                    "memory_used": node_info.get('mem_used', 0),
                    "disk_free": node_info.get('disk_free', 0),
                    "zabbix_host": node_config.get('zabbix_host', '')
                }
                
                nodes_status.append(node_status)
            except Exception as e:
                nodes_status.append({
                    "hostname": hostname,
                    "status": "error",
                    "message": str(e),
                    "zabbix_host": node_config.get('zabbix_host', '')
                })
        
        result = {
            "id": cluster_id,
            "description": client.description,
            "name": cluster_name,
            "nodes": nodes_status
        }
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error retrieving cluster status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/vhosts', methods=['GET'])
def get_vhosts():
    """
    Get RabbitMQ Virtual Hosts
    Returns a list of all virtual hosts from a RabbitMQ cluster
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: query
        type: string
        required: false
        description: Specific cluster ID (optional)
    responses:
      200:
        description: List of virtual hosts
        schema:
          type: object
          properties:
            vhosts:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  description:
                    type: string
                  tags:
                    type: array
                    items:
                      type: string
      500:
        description: Error retrieving vhosts
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        cluster_id = request.args.get('cluster_id')
        rabbitmq_config = config.get_rabbitmq_config()
        
        all_vhosts = []
        
        # Function to get vhosts from a cluster
        def get_cluster_vhosts(cluster):
            try:
                client = RabbitMQClient(cluster)
                cluster_id = cluster.get('id', 'unknown')
                
                vhosts = client.get_vhosts()
                
                # Add cluster info to each vhost
                for vhost in vhosts:
                    vhost['cluster_id'] = cluster_id
                
                return vhosts
            except Exception as e:
                logger.error(f"Error getting vhosts from cluster {cluster.get('id')}: {str(e)}")
                return []
        
        # If specific cluster requested
        if cluster_id:
            for cluster in rabbitmq_config.get('clusters', []):
                if cluster.get('id') == cluster_id:
                    all_vhosts.extend(get_cluster_vhosts(cluster))
                    break
            else:
                return jsonify({"error": f"Cluster ID {cluster_id} not found"}), 404
        
        # Otherwise get from all clusters
        else:
            for cluster in rabbitmq_config.get('clusters', []):
                all_vhosts.extend(get_cluster_vhosts(cluster))
        
        return jsonify({"vhosts": all_vhosts})
    except Exception as e:
        logger.error(f"Error retrieving vhosts: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/vhosts/<cluster_id>/queues', methods=['GET'])
def get_vhost_queues(cluster_id: str):
    """
    Get Queues in Virtual Host
    Returns a list of all queues in a specific virtual host
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: path
        type: string
        required: true
        description: RabbitMQ cluster ID
      - name: vhost
        in: query
        type: string
        required: false
        description: Virtual host (optional, if not provided returns queues from all vhosts)
    responses:
      200:
        description: List of queues
        schema:
          type: object
          properties:
            queues:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  vhost:
                    type: string
                  messages:
                    type: integer
                  messages_ready:
                    type: integer
                  messages_unacknowledged:
                    type: integer
      404:
        description: Cluster or vhost not found
      500:
        description: Error retrieving queues
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        vhost = request.args.get('vhost')
        
        # Get client for this cluster
        try:
            client = get_client_for_cluster(cluster_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 404
        
        # Get queues for this vhost or all vhosts
        queues = client.get_queues_in_vhost(vhost)
        
        # Add cluster info to each queue
        for queue in queues:
            queue['cluster_id'] = cluster_id
        
        return jsonify({"queues": queues})
    except Exception as e:
        logger.error(f"Error retrieving queues: {str(e)}")
        return jsonify({"error": str(e)}), 500

@bp.route('/messages-ready', methods=['GET'])
def get_messages_ready():
    """
    Get Messages Ready Count
    Returns the number of messages ready for consumption in queues
    ---
    tags:
      - RabbitMQ
    parameters:
      - name: cluster_id
        in: query
        type: string
        required: false
        description: RabbitMQ cluster ID (optional)
      - name: vhost
        in: query
        type: string
        required: false
        description: Virtual host (optional)
      - name: queue
        in: query
        type: string
        required: false
        description: Queue name (optional, requires vhost to be specified)
    responses:
      200:
        description: Message count by queue
        schema:
          type: object
          properties:
            messages_ready:
              type: object
              additionalProperties:
                type: integer
      404:
        description: Cluster, vhost, or queue not found
      500:
        description: Error retrieving message counts
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        cluster_id = request.args.get('cluster_id')
        vhost = request.args.get('vhost')
        queue = request.args.get('queue')
        
        # If queue is specified but vhost is not, return error
        if queue and not vhost:
            return jsonify({"error": "Vhost parameter is required when queue is specified"}), 400
        
        rabbitmq_config = config.get_rabbitmq_config()
        all_messages_ready = {}
        
        # Function to get message counts from a cluster
        def get_cluster_message_counts(cluster, vhost=None, queue=None):
            try:
                client = RabbitMQClient(cluster)
                cluster_id = cluster.get('id', 'unknown')
                
                messages_ready = client.get_messages_ready_count(vhost, queue)
                
                # Add cluster ID to the keys
                prefixed_counts = {f"{cluster_id}:{k}": v for k, v in messages_ready.items()}
                
                return prefixed_counts
            except Exception as e:
                logger.error(f"Error getting message counts from cluster {cluster.get('id')}: {str(e)}")
                return {}
        
        # If specific cluster requested
        if cluster_id:
            for cluster in rabbitmq_config.get('clusters', []):
                if cluster.get('id') == cluster_id:
                    message_counts = get_cluster_message_counts(cluster, vhost, queue)
                    all_messages_ready.update(message_counts)
                    break
            else:
                return jsonify({"error": f"Cluster ID {cluster_id} not found"}), 404
        
        # Otherwise get from all clusters
        else:
            for cluster in rabbitmq_config.get('clusters', []):
                message_counts = get_cluster_message_counts(cluster, vhost, queue)
                all_messages_ready.update(message_counts)
        
        return jsonify({"messages_ready": all_messages_ready})
    except Exception as e:
        logger.error(f"Error retrieving message counts: {str(e)}")
        return jsonify({"error": str(e)}), 500    