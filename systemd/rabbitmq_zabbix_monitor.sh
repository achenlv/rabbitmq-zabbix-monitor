#!/bin/bash
cd /var/www/rabbitmq-zabbix-monitor
source /var/www/rabbitmq-zabbix-monitor/.venv/bin/activate
/var/www/rabbitmq-zabbix-monitor/.venv/bin/python \
    /var/www/rabbitmq-zabbix-monitor/app.py 