import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    fh = RotatingFileHandler('log/monitor.log', maxBytes=10485760, backupCount=7)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

def get_alert_key(node: str, vhost: str, queue: str) -> str:
    return f"{node}:{vhost}:{queue}"
