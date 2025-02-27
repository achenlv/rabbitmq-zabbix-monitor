from flask import request
from app.core.config import Config
from app.core.monitoring import MonitoringService
from flask_restx import Resource, fields
from app.api import monitoring_ns, api

# Initialize configuration
config = Config()
monitoring_service = MonitoringService(config.get_config())

# Define monitoring-specific models
monitoring_result_model = monitoring_ns.model('MonitoringResult', {
  'metrics_collected': fields.Integer(description='Number of metrics collected'),
  'data_points_sent': fields.Integer(description='Number of data points sent to Zabbix'),
  'success': fields.Boolean(description='Operation success status'),
  'zabbix_result': fields.Raw(description='Zabbix sender result')
})

queue_config_model = monitoring_ns.model('QueueConfig', {
  'cluster_node': fields.String(description='RabbitMQ node hostname'),
  'vhost': fields.String(description='Virtual host'),
  'queue': fields.String(description='Queue name'),
  'zabbix_host': fields.String(description='Zabbix host name')
})

metrics_model = monitoring_ns.model('Metrics', {
  'host': fields.String(description='Zabbix host'),
  'metrics': fields.Raw(description='Collected metrics'),
  'queue_info': fields.Raw(description='Queue information')
})

drift_result_model = monitoring_ns.model('DriftResult', {
  'alerts_detected': fields.Integer(description='Number of alerts detected'),
  'notifications_sent': fields.Integer(description='Number of notifications sent'),
  'results': fields.List(fields.Raw, description='Notification results')
})

@monitoring_ns.route('/run')
class RunMonitoring(Resource):
  @monitoring_ns.doc('run_monitoring')
  @monitoring_ns.marshal_with(monitoring_result_model)
  def post(self):
    """Run the monitoring cycle"""
    result = monitoring_service.run_monitoring_cycle()
    
    if not result.get('success', False):
      monitoring_ns.abort(400, "Monitoring cycle failed")
    
    return result

@monitoring_ns.route('/run-all')
class RunAllMonitoring(Resource):
  @monitoring_ns.doc('run_all_monitoring')
  @monitoring_ns.marshal_with(monitoring_result_model)
  def post(self):
    """Run the monitoring cycle for ALL queues on ALL vhosts"""
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
    
    return {
      'metrics_collected': len(metrics),
      'data_points_sent': len(zabbix_data_points),
      'zabbix_result': result,
      'success': result.get('success', True)  # Default to true if no error
    }
  
  @monitoring_ns.doc('run_all_monitoring_get')
  @monitoring_ns.marshal_with(monitoring_result_model)
  def get(self):
    """Run the monitoring cycle (GET method for compatibility)"""
    return self.post()

@monitoring_ns.route('/queues')
class MonitoredQueues(Resource):
  @monitoring_ns.doc('get_monitored_queues')
  @monitoring_ns.marshal_list_with(queue_config_model)
  def get(self):
    """Get all monitored queues"""
    queues = config.get('monitoring', {}).get('queues', [])
    return queues

@monitoring_ns.route('/metrics')
class Metrics(Resource):
  @monitoring_ns.doc('get_metrics')
  @monitoring_ns.marshal_list_with(metrics_model)
  def get(self):
    """Collect metrics without sending to Zabbix"""
    metrics = monitoring_service.collect_queue_metrics()
    return metrics

@monitoring_ns.route('/metrics-all')
class AllMetrics(Resource):
  @monitoring_ns.doc('get_all_metrics')
  @monitoring_ns.marshal_list_with(metrics_model)
  def get(self):
    """Collect metrics for ALL queues without sending to Zabbix"""
    metrics = monitoring_service.collect_all_queue_metrics()
    return metrics

@monitoring_ns.route('/check-drift')
class CheckDrift(Resource):
  @monitoring_ns.doc('check_drift')
  @monitoring_ns.marshal_with(drift_result_model)
  def post(self):
    """Check all monitored queues for drift and send notifications"""
    result = monitoring_service.process_queue_alerts()
    return result
  
  @monitoring_ns.doc('check_drift_get')
  @monitoring_ns.marshal_with(drift_result_model)
  def get(self):
    """Check drift (GET method for compatibility)"""
    return self.post()
  

@monitoring_ns.route('/monitor-all-drift')
class CompleteMonitoring(Resource):
  @monitoring_ns.doc('complete_monitoring')
  def post(self):
    """
    Comprehensive monitoring: collect metrics for ALL queues and check for drift
    
    This endpoint combines the functionality of both /metrics-all and /check-drift:
    1. Collects metrics for all queues across all vhosts
    2. Sends these metrics to Zabbix
    3. Checks for queue size drift and threshold violations
    4. Sends notification alerts if needed
    """
    # Part 1: Collect and send metrics (from /metrics-all and /run-all)
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
    zabbix_result = monitoring_service.zabbix_client.send_values_to_zabbix(zabbix_data_points)
    
    # Part 2: Check for drift and send alerts (from /check-drift)
    drift_result = monitoring_service.process_queue_alerts()
    
    # Combine results
    return {
      'metrics_result': {
        'metrics_collected': len(metrics),
        'data_points_sent': len(zabbix_data_points),
        'zabbix_result': zabbix_result,
        'success': zabbix_result.get('success', True)
      },
      'drift_result': drift_result,
      'success': zabbix_result.get('success', True)
    }
  
  @monitoring_ns.doc('complete_monitoring_get')
  def get(self):
    """
    Comprehensive monitoring via GET (for compatibility)
    """
    return self.post()