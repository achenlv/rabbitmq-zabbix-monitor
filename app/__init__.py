from flask import Flask
from app.core.config import Config

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
  
  return app