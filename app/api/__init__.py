from flask_restx import Api, fields

# Initialize the API
api = Api(
  version='1.0',
  title='RabbitMQ-Zabbix Monitor API',
  description='API for monitoring RabbitMQ clusters and sending metrics to Zabbix',
  doc='/api/docs',
  prefix='/api'
)

# Create namespaces for each endpoint group
rabbitmq_ns = api.namespace('rabbitmq', description='RabbitMQ operations')
zabbix_ns = api.namespace('zabbix', description='Zabbix operations')
monitoring_ns = api.namespace('monitoring', description='Monitoring operations')

# Define common models
queue_model = api.model('Queue', {
  'vhost': fields.String(description='RabbitMQ virtual host'),
  'name': fields.String(description='Queue name'),
  'messages': fields.Integer(description='Number of messages in queue'),
  'consumers': fields.Integer(description='Number of consumers'),
  'state': fields.String(description='Queue state')
})

cluster_model = api.model('Cluster', {
  'id': fields.String(description='Cluster ID'),
  'description': fields.String(description='Cluster description'),
  'nodes': fields.List(fields.Raw, description='List of cluster nodes')
})

zabbix_data_point = api.model('ZabbixDataPoint', {
  'host': fields.String(required=True, description='Zabbix host name'),
  'key': fields.String(required=True, description='Item key'),
  'value': fields.String(required=True, description='Item value')
})

# Import endpoints to register them with the API
# This is critical for the operations to be visible in the Swagger UI
from app.api.endpoints import rabbitmq, zabbix, monitoring