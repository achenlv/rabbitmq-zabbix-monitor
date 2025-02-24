from flask import Flask
from flasgger import Swagger
import logging
from logging.handlers import RotatingFileHandler
import os

def create_app():
    app = Flask(__name__)
    swagger = Swagger(app)

    # Setup logging
    if not os.path.exists('log'):
        os.makedirs('log')
    handler = RotatingFileHandler('log/monitor.log', maxBytes=10485760, backupCount=7)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    app.logger.addHandler(handler)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000)
