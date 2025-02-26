from flask import Blueprint, jsonify, request
from app.core.config import Config
from app.core.monitoring import MonitoringService

bp = Blueprint('monitoring', __name__, url_prefix='/api/monitoring')

# Initialize configuration
config = Config()
monitoring_service = MonitoringService(config.get_config())

@bp.route('/run', methods=['POST'])
def run_monitoring():
  """Run the monitoring cycle"""
  result = monitoring_service.run_monitoring_cycle()
  
  if not result.get('success', False):
    return jsonify(result), 400
  
  return jsonify(result)

@bp.route('/queues', methods=['GET'])
def get_monitored_queues():
  """Get all monitored queues"""
  queues = config.get('monitoring', {}).get('queues', [])
  return jsonify(queues)

@bp.route('/metrics', methods=['GET'])
def get_metrics():
  """Collect metrics without sending to Zabbix"""
  metrics = monitoring_service.collect_queue_metrics()
  return jsonify(metrics)

@bp.route('/run-all', methods=['POST'])
def run_all_monitoring():
  """Run the monitoring cycle for ALL queues on ALL vhosts"""
  result = monitoring_service.send_all_metrics_to_zabbix()
  
  if not result.get('success', False):
    return jsonify(result), 400
  
  return jsonify(result)

@bp.route('/metrics-all', methods=['GET'])
def get_all_metrics():
  """Collect metrics for ALL queues without sending to Zabbix"""
  metrics = monitoring_service.collect_all_queue_metrics()
  return jsonify(metrics)