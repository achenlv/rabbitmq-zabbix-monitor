from flask import Flask, jsonify
from app.utils.config import config
from app.utils.logging import setup_logging
import os
import logging
import datetime
from flasgger import Swagger

def create_app():
  """Initialize the core application."""
  app = Flask(__name__)
  
  # Load configuration
  app_config = config.config['app']
  app.config.update(
    HOST=app_config['host'],
    PORT=app_config['port'],
    DEBUG=os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
  )

  # Swagger configuration
  swagger_config = {
    "headers": [],
    "specs": [
      {
        "endpoint": "apispec",
        "route": "/apispec.json",
        "rule_filter": lambda rule: True,
        "model_filter": lambda tag: True,
      }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs/"
  }
  
  swagger_template = {
    "swagger": "2.0",
    "info": {
      "title": "RabbitMQ-Zabbix Monitor API",
      "description": "API for monitoring RabbitMQ queues and sending alerts to Zabbix",
      "version": "0.0.1",
      "contact": {
        "name": "API Support",
        "email": "support@example.com"
      }
    },
    "schemes": ["http", "https"],
  }
  
  # Setup Swagger
  Swagger(app, config=swagger_config, template=swagger_template)


  # Setup logging
  setup_logging()
  logger = logging.getLogger(__name__)

  # @app.route('/')
  @app.route('/health')
  def health():
    """
    Health check endpoint
    Returns the status of the API service
    ---
    responses:
      200:
        description: Service is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
            timestamp:
              type: string
              example: 2025-02-24T12:34:56.789012
            service:
              type: string
              example: rabbitmq-zabbix-monitor
            version:
              type: string
              example: 1.0.0
    """
    return jsonify({
      'status': 'ok',
      'timestamp': datetime.datetime.now().isoformat(),
      'service': 'rabbitmq-zabbix-monitor',
      'version': '0.0.1'
    })

  with app.app_context():
    # Register blueprints
    from app.api.endpoints import rabbitmq, zabbix, email
    app.register_blueprint(rabbitmq.bp)
    app.register_blueprint(zabbix.bp)
    app.register_blueprint(email.bp)
    logger.info(f"Application initialized")

  return app

if __name__ == '__main__':
  app = create_app()
  logger = logging.getLogger(__name__)
  logger.info(f"Starting Flask server on http://{app.config['HOST']}:{app.config['PORT']} (Debug: {app.config['DEBUG']})")
  logger.info(f"API documentation available at http://{app.config['HOST']}:{app.config['PORT']}/docs/")

  app.run(
    host=app.config['HOST'],
    port=app.config['PORT'],
    debug=app.config['DEBUG']
  )