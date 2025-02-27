from flask import Flask
from app.core.config import Config
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_restx import Api

def create_app():
  # Create Flask app
  app = Flask(__name__)
  
  # Load configuration
  config = Config()
  app_config = config.get('app', {})
  
  # Register blueprints
  from app.api.endpoints.rabbitmq import bp as rabbitmq_bp
  from app.api.endpoints.zabbix import bp as zabbix_bp
  from app.api.endpoints.monitoring import bp as monitoring_bp
  
  app.register_blueprint(rabbitmq_bp)
  app.register_blueprint(zabbix_bp)
  app.register_blueprint(monitoring_bp)
  
  # Basic route for health check
  @app.route('/health', methods=['GET'])
  def health_check():
    return {'status': 'ok'}

  if not app.debug:
    if not os.path.exists('log'):
      os.mkdir('log')
    file_handler = RotatingFileHandler(
        'log/rabbitmq-zabbix-monitor.log', 
        maxBytes=10240,
        backupCount=7
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('RabbitMQ Zabbix Monitor startup')    


  return app



#### Setting for openapi
# # Initialize the API
# api = Api(
#   version='1.0',
#   title='RabbitMQ-Zabbix Monitor API',
#   description='API for monitoring RabbitMQ clusters and sending metrics to Zabbix',
#   doc='/api/docs',
#   prefix='/api'
# )

# # Create namespaces for each endpoint group
# rabbitmq_ns = api.namespace('rabbitmq', description='RabbitMQ operations')
# zabbix_ns = api.namespace('zabbix', description='Zabbix operations')
# monitoring_ns = api.namespace('monitoring', description='Monitoring operations')

# # Define common models
# queue_model = api.model('Queue', {
#   'vhost': api.fields.String(description='RabbitMQ virtual host'),
#   'name': api.fields.String(description='Queue name'),
#   'messages': api.fields.Integer(description='Number of messages in queue'),
#   'consumers': api.fields.Integer(description='Number of consumers'),
#   'state': api.fields.String(description='Queue state')
# })

# cluster_model = api.model('Cluster', {
#   'id': api.fields.String(description='Cluster ID'),
#   'description': api.fields.String(description='Cluster description'),
#   'nodes': api.fields.List(api.fields.Raw, description='List of cluster nodes')
# })

# zabbix_data_point = api.model('ZabbixDataPoint', {
#   'host': api.fields.String(required=True, description='Zabbix host name'),
#   'key': api.fields.String(required=True, description='Item key'),
#   'value': api.fields.String(required=True, description='Item value')
# })



#### Setting for service
# # In app/__init__.py
# def create_app():
#     app = Flask(__name__)
    
#     # If proxied under a path prefix, ensure URLs work correctly
#     class PrefixMiddleware:
#         def __init__(self, app, prefix='/rabbitmq-zabbix-monitor'):
#             self.app = app
#             self.prefix = prefix

#         def __call__(self, environ, start_response):
#             if environ['PATH_INFO'].startswith(self.prefix):
#                 environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
#                 environ['SCRIPT_NAME'] = self.prefix
#                 return self.app(environ, start_response)
#             else:
#                 start_response('404', [('Content-Type', 'text/plain')])
#                 return [b'Not Found']
    
#     # Only apply middleware when running behind proxy with path prefix
#     if os.environ.get('BEHIND_PROXY') == 'true':
#         app.wsgi_app = PrefixMiddleware(app.wsgi_app)
    
#     # Rest of your app setup
#     # ...
    
#     return app