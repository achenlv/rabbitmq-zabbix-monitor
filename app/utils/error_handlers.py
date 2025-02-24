from flask import jsonify
from werkzeug.exceptions import HTTPException
import logging

logger = logging.getLogger(__name__)

def register_error_handlers(app):
  @app.errorhandler(Exception)
  def handle_exception(e):
    if isinstance(e, HTTPException):
      response = {
        'error': e.description,
        'status_code': e.code
      }
      return jsonify(response), e.code

    logger.exception("Unhandled exception occurred")
    response = {
      'error': 'Internal server error',
      'status_code': 500
    }
    return jsonify(response), 500