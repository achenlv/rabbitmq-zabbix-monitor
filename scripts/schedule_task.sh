#!/bin/bash

# This script sets up a cron job to run the main.py script every working day at specified times.

# Define the schedule (e.g., every weekday at 9 AM and 5 PM)
SCHEDULE="15 9,17 * * 1-5"

# Define the command to run the Python script
# COMMAND="python3 /path/to/rabbitmq-zabbix-monitor/src/main.py"
COMMAND="cron_job.sh"

# Add the cron job
(crontab -l 2>/dev/null; echo "$SCHEDULE $COMMAND") | crontab -