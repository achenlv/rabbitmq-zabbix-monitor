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

@bp.route('/run-all-old', methods=['POST'])
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


@bp.route('/run-all', methods=['POST'])
def run_all_monitoring():
  """Run the monitoring cycle for ALL queues on ALL vhosts"""
  # First, try to verify that zabbix_sender works with a single test value
  test_result = monitoring_service.zabbix_client.send_value(
    "FIHELSPAS54151", 
    "rabbitmq.test.queue.size[test_vhost,test_queue]", 
    "2"
  )
  
  if not test_result.get('success', False):
    # Return detailed error to help troubleshoot
    return jsonify({
      'success': False,
      'error': "Failed to connect to Zabbix server",
      'details': test_result
    }), 400
  
  # Collect metrics
  metrics = monitoring_service.collect_all_queue_metrics()
  
  # Prepare data for Zabbix
  zabbix_data_points = []
  for metric in metrics:
    host = metric.get('host')
    for key, value in metric.get('metrics', {}).items():
      zabbix_data_points.append({
        'host': host,
        'key': key,
        'value': value
      })
  
  # Send data to Zabbix
  result = monitoring_service.zabbix_client.send_values_to_zabbix(zabbix_data_points)
  
  return jsonify({
    'metrics_collected': len(metrics),
    'data_points_sent': len(zabbix_data_points),
    'zabbix_result': result,
    'success': result.get('success', False)
  })