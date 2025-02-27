from flask import request
from app.core.config import Config
from app.core.rabbitmq import RabbitMQClient
from flask_restx import Resource
from app.api import rabbitmq_ns, queue_model, cluster_model
import urllib.parse

# Initialize configuration
config = Config()
rabbitmq_client = RabbitMQClient(config.get_config())

@rabbitmq_ns.route('/clusters')
class ClusterList(Resource):
  @rabbitmq_ns.doc('list_clusters')
  @rabbitmq_ns.marshal_list_with(cluster_model)
  def get(self):
    """Get all RabbitMQ clusters"""
    clusters = config.get('rabbitmq', {}).get('clusters', [])
    # Remove sensitive information
    for cluster in clusters:
      if 'auth' in cluster:
        del cluster['auth']
    
    return clusters

@rabbitmq_ns.route('/clusters/<cluster_id>')
@rabbitmq_ns.param('cluster_id', 'The cluster identifier')
class Cluster(Resource):
  @rabbitmq_ns.doc('get_cluster')
  @rabbitmq_ns.marshal_with(cluster_model)
  def get(self, cluster_id):
    """Get a specific RabbitMQ cluster"""
    cluster = rabbitmq_client.get_cluster_by_id(cluster_id)
    
    if not cluster:
      rabbitmq_ns.abort(404, "Cluster not found")
    
    # Remove sensitive information
    if 'auth' in cluster:
      del cluster['auth']
    
    return cluster

@rabbitmq_ns.route('/clusters/<cluster_id>/queues')
@rabbitmq_ns.param('cluster_id', 'The cluster identifier')
class QueueList(Resource):
  @rabbitmq_ns.doc('list_queues')
  @rabbitmq_ns.marshal_list_with(queue_model)
  def get(self, cluster_id):
    """Get all queues for a specific cluster"""
    queues = rabbitmq_client.get_all_queues(cluster_id)
    
    if isinstance(queues, dict) and "error" in queues:
      rabbitmq_ns.abort(400, queues["error"])
    
    return queues

@rabbitmq_ns.route('/clusters/<cluster_id>/queues/<path:vhost>/<queue_name>')
@rabbitmq_ns.param('cluster_id', 'The cluster identifier')
@rabbitmq_ns.param('vhost', 'The virtual host (URL-encoded)')
@rabbitmq_ns.param('queue_name', 'The queue name')
class Queue(Resource):
  @rabbitmq_ns.doc('get_queue')
  @rabbitmq_ns.marshal_with(queue_model)
  def get(self, cluster_id, vhost, queue_name):
    """Get information about a specific queue"""
    # URL decode the vhost parameter
    decoded_vhost = urllib.parse.unquote(vhost)
    queue_info = rabbitmq_client.get_queue_info(cluster_id, decoded_vhost, queue_name)
    
    if isinstance(queue_info, dict) and "error" in queue_info:
      rabbitmq_ns.abort(400, queue_info["error"])
    
    return queue_info