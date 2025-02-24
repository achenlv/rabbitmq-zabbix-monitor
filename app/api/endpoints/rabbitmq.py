from flask import Blueprint, jsonify, request
from app.core.rabbitmq import RabbitMQClient
from app.utils.config import config
import logging

bp = Blueprint('rabbitmq', __name__, url_prefix='/api/rabbitmq')
logger = logging.getLogger(__name__)

@bp.route('/queues', methods=['GET'])
def get_queues():
  """
  Get RabbitMQ Queues
  Returns a list of all queues from RabbitMQ
  ---
  tags:
    - RabbitMQ
  parameters:
    - name: cluster
      in: query
      type: string
      required: false
      description: Filter by cluster name
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
    500:
      description: Error retrieving queues
      schema:
        type: object
        properties:
          error:
            type: string
  """
  # This will be implemented with actual RabbitMQ API calls later
  return jsonify({
    'queues': [
      {
        'name': 'test_queue',
        'vhost': 'test_vhost',
        'messages': 0,
        'consumers': 1
      }
    ]
  })


@bp.route('/queues/<cluster>/<vhost>/<queue>', methods=['GET'])
def get_queue_info(cluster: str, vhost: str, queue: str):
  """Get queue information from RabbitMQ"""
  try:
    rabbitmq_client = RabbitMQClient(cluster)
    queue_info = rabbitmq_client.get_queue_info(vhost, queue)
    return jsonify(queue_info)
  except Exception as e:
    logger.error(f"Error getting queue info: {str(e)}")
    return jsonify({'error': str(e)}), 500