Design python project which is supposed to check message count in all rabbitmq vhost queues and update it to specific zabbix trapper item rabbitmq.test.queue.size[${VHOST},${QUEUE}] for ${ZABBIX_HOST}, where ZABBIX_HOST equals RABBITMQ cluster node. If zabbix item cannot be found, it should be created.
* On zabbix item value update, if {ZABBIX_HOST}, {VHOST} and {QUEUE} fits spefically given, i.e., VHOST1 and QUEUE1, then last 2 item values should be checked and compared, and in case of latest value is bigger, email is sent to specified To and Cc addresses, and email body should be read from given template. 
* All data like hosts, addresses and such should be read from environment file which can be either json or ini style.
* Code should be started as systemd service, and should run every 5 minutes. 
* Logging should be implemented for every time code was run showing rabbitmq node, vhost, queue and queue message count. If latest message count higher than previous for specified queue (drift), then it should be loggged as warning, and email sent out to specified integration team email. If this message count is higher than 15, then email should be sent to watchman as well.
* Logrotate should be implemented by each day.

Additional comments:
* config.json monitoring.queues should have rabbitmq cluster node included as well. This should be equal to zabbix host where trapper item would be added. According changes should be done in code elsewhere.
* config.json emails should be set in 2 options where 1) is with To, and optional Cc emails for all drifts, and 2) is with To and optional Cc emails if queue message count exceeds set threshold (by default 15).
* email should be sent only once when drift was noticed.
* There can be more than one email template used.
* There can be more than one rabbitmq server (cluster node) specified.

Anything else need to be specified?