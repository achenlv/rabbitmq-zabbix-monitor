from flask import Flask
from app.core.config import Config
import os

def create_app():
  # Create Flask app
  app = Flask(__name__)
  
  # Load configuration
  # config = Config()
  # app_config = config.get('app', {})
  
  # Basic route for health check
  @app.route('/health', methods=['GET'])
  def health_check():
    return {'status': 'ok'}
  
  # Initialize API with Swagger support - Do this AFTER defining any routes
  from app.api import api
  api.init_app(app)
  
  # Set up proxy handling for path prefixes if enabled
  if os.environ.get('BEHIND_PROXY') == 'true':
    class PrefixMiddleware:
      def __init__(self, app, prefix='/rabbitmq-zabbix-monitor'):
        self.app = app
        self.prefix = prefix

      def __call__(self, environ, start_response):
        if environ['PATH_INFO'].startswith(self.prefix):
          environ['PATH_INFO'] = environ['PATH_INFO'][len(self.prefix):]
          environ['SCRIPT_NAME'] = self.prefix
          return self.app(environ, start_response)
        else:
          start_response('404', [('Content-Type', 'text/plain')])
          return [b'Not Found']
    
    app.wsgi_app = PrefixMiddleware(app.wsgi_app)
  
  return app