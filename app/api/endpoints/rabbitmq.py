from flask import Blueprint, jsonify, request
from app.core.config import Config
from app.core.rabbitmq import RabbitMQClient
from flask_restx import Resource
from app.api import rabbitmq_ns, queue_model, cluster_model

bp = Blueprint('rabbitmq', __name__, url_prefix='/api/rabbitmq')

# Initialize configuration
config = Config()
rabbitmq_client = RabbitMQClient(config.get_config())

@bp.route('/clusters', methods=['GET'])
def get_clusters():
  """Get all RabbitMQ clusters"""
  clusters = config.get('rabbitmq', {}).get('clusters', [])
  # Remove sensitive information
  for cluster in clusters:
    if 'auth' in cluster:
      del cluster['auth']
  
  return jsonify(clusters)

@bp.route('/clusters/<cluster_id>', methods=['GET'])
def get_cluster(cluster_id):
  """Get a specific RabbitMQ cluster"""
  cluster = rabbitmq_client.get_cluster_by_id(cluster_id)
  
  if not cluster:
    return jsonify({"error": "Cluster not found"}), 404
  
  # Remove sensitive information
  if 'auth' in cluster:
    del cluster['auth']
  
  return jsonify(cluster)

@bp.route('/clusters/<cluster_id>/queues', methods=['GET'])
def get_queues(cluster_id):
  """Get all queues for a specific cluster"""
  queues = rabbitmq_client.get_all_queues(cluster_id)
  
  if isinstance(queues, dict) and "error" in queues:
    return jsonify(queues), 400
  
  return jsonify(queues)

@bp.route('/clusters/<cluster_id>/queues/<vhost>/<queue_name>', methods=['GET'])
def get_queue(cluster_id, vhost, queue_name):
  """Get information about a specific queue"""
  queue_info = rabbitmq_client.get_queue_info(cluster_id, vhost, queue_name)
  
  if isinstance(queue_info, dict) and "error" in queue_info:
    return jsonify(queue_info), 400
  
  return jsonify(queue_info)