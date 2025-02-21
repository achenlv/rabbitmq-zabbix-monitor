import json
import os
import logging
import smtplib
from email.mime.text import MIMEText
from configparser import ConfigParser
from datetime import datetime
from zabbix_api import ZabbixAPI
import pika

# Load configuration
def load_config():
    config_path = os.getenv('CONFIG_PATH', '/c:/work/rabbitmq-zabbix-monitor/config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

# Initialize logging
def init_logging():
    logging.basicConfig(filename='/var/log/rabbitmq_monitor.log', level=logging.INFO, format='%(asctime)s %(message)s')
    logging.info('Script started')

# Connect to RabbitMQ
def connect_rabbitmq(node):
    credentials = pika.PlainCredentials('guest', 'guest')
    parameters = pika.ConnectionParameters(node, 5672, '/', credentials)
    return pika.BlockingConnection(parameters)

# Connect to Zabbix
def connect_zabbix():
    zabbix_server = os.getenv('ZABBIX_SERVER', 'http://zabbix.example.com')
    zabbix_user = os.getenv('ZABBIX_USER', 'Admin')
    zabbix_password = os.getenv('ZABBIX_PASSWORD', 'zabbix')
    zapi = ZabbixAPI(server=zabbix_server)
    zapi.login(zabbix_user, zabbix_password)
    return zapi

# Get queue message count
def get_queue_message_count(connection, vhost, queue):
    channel = connection.channel()
    channel.queue_declare(queue=queue, passive=True)
    queue_state = channel.queue_declare(queue=queue, passive=True)
    return queue_state.method.message_count

# Update Zabbix item
def update_zabbix_item(zapi, host, key, value):
    item = zapi.item.get(filter={'host': host, 'key_': key})
    if not item:
        zapi.item.create({
            'name': key,
            'key_': key,
            'hostid': zapi.host.get(filter={'host': host})[0]['hostid'],
            'type': 2,
            'value_type': 3,
            'delay': '5m'
        })
    zapi.history.create({
        'itemid': item[0]['itemid'],
        'clock': int(datetime.now().timestamp()),
        'value': value
    })

# Send email
def send_email(subject, body, to, cc=None):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = os.getenv('EMAIL_FROM', 'monitor@example.com')
    msg['To'] = to
    if cc:
        msg['Cc'] = cc

    with smtplib.SMTP('localhost') as server:
        server.sendmail(msg['From'], [to] + ([cc] if cc else []), msg.as_string())

# Main function
def main():
    config = load_config()
    zapi = connect_zabbix()
    init_logging()

    for queue in config['monitoring']['queues']:
        node = queue['node']
        vhost = queue['vhost']
        queue_name = queue['queue']
        connection = connect_rabbitmq(node)
        message_count = get_queue_message_count(connection, vhost, queue_name)
        update_zabbix_item(zapi, node, f'rabbitmq.test.queue.size[{vhost},{queue_name}]', message_count)
        logging.info(f'Node: {node}, VHost: {vhost}, Queue: {queue_name}, Message Count: {message_count}')

        # Check for drift and send email if necessary
        if vhost == 'VHOST1' and queue_name == 'QUEUE1':
            # ... code to check previous values and send email if drift detected ...
            pass

        # Check if message count exceeds threshold and send email if necessary
        if message_count > config['threshold']:
            with open(config['email_templates']['threshold'], 'r') as f:
                email_body = f.read()
            send_email('Queue Message Count Exceeded', email_body, config['emails']['threshold']['to'], config['emails']['threshold'].get('cc'))

if __name__ == '__main__':
    main()
