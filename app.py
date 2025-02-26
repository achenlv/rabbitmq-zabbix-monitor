from app import create_app
from app.core.config import Config

# Create Flask app
app = create_app()

if __name__ == '__main__':
  # Load configuration
  config = Config()
  app_config = config.get('app', {})
  
  # Get host and port from config
  host = app_config.get('host', '127.0.0.1')
  port = app_config.get('port', 5000)
  
  # Run the app
  app.run(host=host, port=port, debug=True)