import os
import time
from rabbitmq_client import RabbitMQClient
from zabbix_client import ZabbixClient
from email_client import EmailClient
from utils import load_env_variables as load_env

def check_queue_item_count():
    # env_vars = load_env('../config/config.env')
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
      vhost=env_vars['RABBIT_VHOST'],
      queue=env_vars['RABBIT_QUEUE']
    )
    
    zabbix_client = ZabbixClient(
      server=env_vars['ZABBIX_SERVER'],
      username=env_vars['ZABBIX_USER'],
      password=env_vars['ZABBIX_PASS']
    )
    
    current_count = rabbitmq_client.get_queue_item_count()
    last_count = zabbix_client.get_last_item_value(env_vars['ZABBIX_ITEM_ID'])
    
    print(f"Current queue item count: {current_count}")
    print(f"Last recorded item count: {last_count}")
    
    if (current_count > last_count) or (current_count == last_count):
      # trigger_details = zabbix_client.get_trigger_details(env_vars['ZABBIX_TRIGGER_ID'])
      # event_details = zabbix_client.get_event_details(env_vars['ZABBIX_TRIGGER_ID'])
      trigger_details = zabbix_client.get_trigger_details(40130)
      event_details = zabbix_client.get_event_details(10660, 40130)
      problem_start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(event_details['clock'])))
      context = {
        'problem_start_time':  problem_start_time if event_details else 'N/A',
        'problem_name': trigger_details['description'] if trigger_details else 'N/A',
        # 'problem_name': event_details['name'] if event_details else trigger_details['description'] if trigger_details else 'N/A',
        'host': trigger_details['hosts'][0]['host'] if trigger_details else 'N/A',
        'severity': trigger_details['priority'] if trigger_details else 'N/A',
        'operational_data': current_count,
        'original_problem_id': event_details['eventid'] if event_details else 'N/A',
        'event_tags_details': event_details['tags'] if event_details else 'N/A'         
        # 'problem_start_time': time.strftime('%H:%M:%S on %Y.%m.%d'),
        # 'problem_name': f"RabbitMQ Queue Size drift [{env_vars['ZABBIX_HOST_NAME']}, {env_vars['RABBIT_VHOST']}, {env_vars['RABBIT_QUEUE']}]",
        # 'host': env_vars['ZABBIX_HOST_NAME'],
        # 'severity': 'Average',
        # 'operational_data': current_count,
        # 'original_problem_id': event_details['eventid'] if event_details else 'N/A',
        # 'event_tags_details': event_details['tags'] if event_details else 'N/A'
      }
      email_body = email_client.read_template(os.path.join(os.path.dirname(__file__), '../config/email_template.txt'), context)
      email_client.send_email(
        subject="RabbitMQ Queue Item Count Increased",
        body=email_body
      )
      print("Email sent: The item count in the queue has increased.")
    else:
      print("No increase in queue item count.")

if __name__ == "__main__":
  check_queue_item_count()