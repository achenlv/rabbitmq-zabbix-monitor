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
      # zabbix_client.set_trapper_item(current_count)
      email_client.send_email(
          subject="RabbitMQ Queue Item Count Increased",
          body=f"The item count in the queue has increased from {last_count} to {current_count}."
      )
      print("Email sent: The item count in the queue has increased.")
    else:
      print("No increase in queue item count.")

if __name__ == "__main__":
  check_queue_item_count()