from flask import Flask
from app.core.config import Config
import logging
from logging.handlers import RotatingFileHandler
import os

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