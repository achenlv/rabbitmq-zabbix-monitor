import os
import time
import schedule
from rabbitmq_client import RabbitMQClient
from zabbix_client import ZabbixClient
from email_client import EmailClient
from utils import load_env_variables as load_env



def check_queue_item_count():
  env_vars = load_env('../config/config.env')
  
  rabbitmq_client = RabbitMQClient(
    host=env_vars['RABBIT_HOST'],
    user=env_vars['RABBIT_USER'],
    password=env_vars['RABBIT_PASS'],
    vhost=env_vars['RABBIT_VHOST'],
    queue=env_vars['RABBIT_QUEUE']
  )
  
  zabbix_client = ZabbixClient(
    server=env_vars['ZABBIX_SERVER'],
    user=env_vars['ZABBIX_USER'],
    password=env_vars['ZABBIX_PASS']
  )
  
  email_client = EmailClient(
    mail_server=env_vars['MAIL_SERVER'],
    mail_from=env_vars['MAIL_FROM'],
    mail_to=env_vars['MAIL_TO']
  )
  
  current_count = rabbitmq_client.get_queue_item_count()
  last_count = zabbix_client.get_last_item_value(env_vars['ZABBIX_ITEM_ID'])
    
  if current_count > last_count:
    zabbix_client.set_trapper_item(current_count)
    email_client.send_email(
      subject="RabbitMQ Queue Item Count Increased",
      body=f"The item count in the queue has increased from {last_count} to {current_count}."
    )

def main():
  load_env('../config/config.env')  # Load environment variables
  schedule.every().monday.at("09:00").do(check_queue_item_count)
  schedule.every().tuesday.at("09:00").do(check_queue_item_count)
  schedule.every().wednesday.at("09:00").do(check_queue_item_count)
  schedule.every().thursday.at("09:00").do(check_queue_item_count)
  schedule.every().friday.at("09:00").do(check_queue_item_count)

  while True:
    schedule.run_pending()
    time.sleep(1)

if __name__ == "__main__":
  main()