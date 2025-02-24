from flask import Blueprint, jsonify, request, send_file, current_app
import logging


bp=Blueprint('test', __name__, url_prefix='/test')
logger = logging.getLogger(__name__)

@bp.route('/hello', methods=['GET'])
def hello():
  logger.info('Hello World!')
  return jsonify({'message': 'Hello World!'})