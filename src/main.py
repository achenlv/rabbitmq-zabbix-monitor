import os
import time
import requests
import json
from rabbitmq_client import RabbitMQClient
from zabbix_client import ZabbixClient
from email_client import EmailClient
from utils import load_env_variables as load_env

def update_zabbix_with_queue_sizes(env_vars):
  rabbitmq_client = RabbitMQClient(
    host=env_vars['RABBIT_HOST'],
    username=env_vars['RABBIT_USER'],
    password=env_vars['RABBIT_PASS'],
    vhost=env_vars['RABBIT_VHOST'],
    queue=env_vars['RABBIT_QUEUE']
  )
  
  zabbix_client = ZabbixClient(
    server=env_vars['ZABBIX_SERVER'],
    username=env_vars['ZABBIX_USER'],
    password=env_vars['ZABBIX_PASS']
  )
  
  # Get list of queues from RabbitMQ
  url = f"http://{env_vars['RABBIT_HOST']}:15672/api/queues"
  response = requests.get(url, auth=(env_vars['RABBIT_USER'], env_vars['RABBIT_PASS']))
  if response.status_code != 200:
    print("Failed to get response from RabbitMQ API")
    return
  
  queues = response.json()
  for queue in queues:
    zabbix_key = f"rabbitmq.test.queue.size[{queue['vhost']},{queue['name']}]"
    # Update Zabbix item with queue message size
    zabbix_client.send_data(env_vars['ZABBIX_HOST'], zabbix_key, queue['messages_ready'])

def check_queue_item_count(vhost, queue, limit=15):
  env_vars = load_env(os.path.join(os.path.dirname(__file__), '../config/config.env'))
  
  email_client = EmailClient(
    mail_server=env_vars['MAIL_SERVER'],
    mail_from=env_vars['MAIL_FROM'],
    mail_to=env_vars['MAIL_TO']
  )
  
  rabbitmq_client = RabbitMQClient(
    host=env_vars['RABBIT_HOST'],
    username=env_vars['RABBIT_USER'],
    password=env_vars['RABBIT_PASS'],
    vhost=vhost,
    queue=queue
  )
  
  zabbix_client = ZabbixClient(
    server=env_vars['ZABBIX_SERVER'],
    username=env_vars['ZABBIX_USER'],
    password=env_vars['ZABBIX_PASS']
  )
  
  last_count = zabbix_client.get_last_item_value(env_vars['ZABBIX_ITEM_ID'], 2)
  
  print(f"Last recorded item count: {last_count}")
  
  if (last_count[0] > last_count[-1]) or (last_count[0] == last_count[-1]):
    trigger_details = zabbix_client.get_trigger_details(env_vars['ZABBIX_TRIGGER_ID'])
    event_details = zabbix_client.get_event_details(env_vars['ZABBIX_HOST_ID'], env_vars['ZABBIX_TRIGGER_ID'])
    problem_start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(event_details['clock'])))
    context = {
      'problem_start_time':  problem_start_time if event_details else 'N/A',
      'problem_name': trigger_details['description'] if trigger_details else 'N/A',
      'host': trigger_details['hosts'][0]['host'] if trigger_details else 'N/A',
      'severity': trigger_details['priority'] if trigger_details else 'N/A',
      'operational_data': f'{last_count[0]} -> {last_count[0]}',
      'original_problem_id': event_details['eventid'] if event_details else 'N/A',
      'event_tags_details': event_details['tags'] if event_details else 'N/A'         
    }
    email_body = email_client.read_template(os.path.join(os.path.dirname(__file__), '../config/email_template.txt'), context)
    email_client.send_email(
      subject="[RabbitMQ Error] Queue Size drift [FIHELSPAS54151, CaseReg, CaseReg_error_queue]",
      body=email_body
    )
    print("Email sent: The item count in the queue has increased.")
  else:
    print("No increase in queue item count.")
  
  if last_count[0] > limit:
    # Additional method call if message count in queue is higher than limit
    print(f"Queue item count {last_count[0]} exceeds limit {limit}")

if __name__ == "__main__":
  env_vars = load_env(os.path.join(os.path.dirname(__file__), '../config/config.env'))
  update_zabbix_with_queue_sizes(env_vars)
  check_queue_item_count(env_vars['RABBIT_VHOST'], env_vars['RABBIT_QUEUE'])