# app/api/endpoints/zabbix.py
from flask import Blueprint, jsonify, request
import logging

bp = Blueprint('zabbix', __name__, url_prefix='/api/zabbix')
logger = logging.getLogger(__name__)

@bp.route('/health', methods=['GET'])
def health_check():
  """Simple health check endpoint"""
  return jsonify({'status': 'ok'})

@bp.route('/hosts', methods=['GET'])
def get_hosts():
  """
  Get Zabbix Hosts
  Returns a list of hosts monitored by Zabbix
  ---
  tags:
    - Zabbix
  responses:
    200:
      description: List of hosts
      schema:
        type: object
        properties:
          hosts:
            type: array
            items:
              type: object
              properties:
                hostid:
                  type: string
                name:
                  type: string
    500:
      description: Error retrieving hosts
      schema:
        type: object
        properties:
          error:
            type: string
  """
  return jsonify({
    'hosts': [
      {
        'hostid': '10084',
        'name': 'FIHELSPAS54151'
      }
    ]
  })