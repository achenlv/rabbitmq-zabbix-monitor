import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Setup logging configuration"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    fh = RotatingFileHandler(
        os.path.join(os.path.dirname(__file__), '../log/monitor.log'),
        maxBytes=10485760,  # 10MB
        backupCount=7
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def get_alert_key(node: str, vhost: str, queue: str) -> str:
    """Generate unique key for alert tracking"""
    return f"{node}:{vhost}:{queue}"