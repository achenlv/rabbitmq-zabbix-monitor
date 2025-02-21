#!/usr/bin/env bash

# Function to display usage instructions
usage() {
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --zabbixserver  Zabbix server (default: $DEFAULT_ZABBIX_SERVER)"
  echo "  --zabbixhost    Zabbix hostname (default: $DEFAULT_ZABBIX_HOST)"
  echo "  --hostname      RabbitMQ host (default: $DEFAULT_RABBIT_HOST)"
  echo "  --username      RabbitMQ user (default: $DEFAULT_RABBIT_USER)"
  echo "  --userpass      RabbitMQ password (default: $DEFAULT_RABBIT_PASS)"
  echo "  --rabbitvhost   RabbitMQ vhost (default: $DEFAULT_RABBIT_VHOST)"
  echo "  --rabbitqueue   RabbitMQ queue (default: $DEFAULT_RABBIT_QUEUE)"
  echo "  --dry-run       Simulate the script without making changes"
  echo "  --debug         Enable debug mode"
  echo "  -h, --help      Display this help message"
  echo "Script depends on curl and jq. Make sure they are installed."
  echo "Zabbix items will be created if do not exist."
  exit 1
}

# Check if curl is installed
if ! command -v curl &> /dev/null; then
  echo "curl is not installed. Exiting..."
  exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
  echo "jq is not installed. Exiting..."
  exit 1
fi

# Check if the required parameters are provided
# Default values
DRYRUN=false
DEBUG=false

DEFAULT_RABBIT_HOST=FIHEL2SPAS040
DEFAULT_RABBIT_USER=zbx_monitor
DEFAULT_RABBIT_PASS='0X*cdhDmLPKx'
DEFAULT_RABBIT_VHOST=/
DEFAULT_RABBIT_QUEUE=Test_RabbitMQ_Error_Queues
DEFAULT_ZABBIX_SERVER=fihel2stas253
DEFAULT_ZABBIX_HOST=FIHEL2SPAS040

TLS_OPTIONS='--tls-connect psk --tls-psk-identity agent-psk  --tls-psk-file /etc/zabbix/psk.key'

AUTH_TOKEN='74f285da330a7961ef9013d2eb0da971978e2207a6ba0d2879fa03f207722139'
# Logs and log cleanup
  # Create a tar.gz archive of yesterday's log file
  # Delete the original log file
  # Delete archived log files older than a week
LOG_NAME_PREFIX=rabbitmq_queue_sent_
LOG_DIR=/var/log/zabbix
LOG_FILE="${LOG_NAME_PREFIX}$(date +'%d%m%Y').log"
YESTERDAY_LOG_FILE="${LOG_NAME_PREFIX}$(date -d 'yesterday' +'%d%m%Y').log"
if [ -f "${LOG_DIR}${YESTERDAY_LOG_FILE}" ]; then
  tar -czf "${LOG_DIR}${YESTERDAY_LOG_FILE}.tgz" "${LOG_DIR}${YESTERDAY_LOG_FILE}"
  rm "${LOG_DIR}${YESTERDAY_LOG_FILE}"
  find ${LOG_DIR} -name "${LOG_NAME_PREFIX}*.tgz" -type f -mtime +7 -exec rm -f {} \;
fi

# Parse named parameters
while [[ "$#" -gt 0 ]]; do
  case $1 in
    --hostname) RABBIT_HOST="$2"; shift ;;
    --username) RABBIT_USER="$2"; shift ;;
    --userpass) RABBIT_PASS="$2"; shift ;;
    --zabbixserver) ZABBIX_SERVER="$2"; shift;;
    --rabbitvhost) RABBIT_VHOST="$2"; shift;;
    --rabbitqueue) RABBIT_QUEUE="$2"; shift;;
    --dry-run) DRYRUN=true ;;
    --debug) DEBUG=true ;;
    -h|--help) usage ;;
    *) echo "Unknown parameter passed: $1"; exit 1 ;;
  esac
  shift
done

# Use default values if parameters are not provided
RABBIT_HOST=${RABBIT_HOST:-$DEFAULT_RABBIT_HOST}
RABBIT_USER=${RABBIT_USER:-$DEFAULT_RABBIT_USER}
RABBIT_PASS=${RABBIT_PASS:-$DEFAULT_RABBIT_PASS}
ZABBIX_SERVER=${ZABBIX_SERVER:-$DEFAULT_ZABBIX_SERVER}
RABBIT_QUEUE=${RABBIT_QUEUE:-$DEFAULT_RABBIT_QUEUE}

# Function to get Zabbix API authorization token
get_zabbix_auth_token() {
  local zabbix_url="http://${ZABBIX_SERVER}/api_jsonrpc.php"
  local user="your_zabbix_user"
  local password="your_zabbix_password"

  local auth_response=$(curl -s -X POST -H 'Content-Type: application/json' -d '{
    "jsonrpc": "2.0",
    "method": "user.login",
    "params": {
      "user": "'"${user}"'",
      "password": "'"${password}"'"
    },
    "id": 1,
    "auth": null
  }' ${zabbix_url})

  echo $(echo $auth_response | jq -r '.result')
}

# Function to get host ID
get_zabbix_host_id() {
    local auth_token=$1
    local zabbix_url="http://${ZABBIX_SERVER}/api_jsonrpc.php"
    local host=$2

    HOST_ID=$(curl -s -X POST -H "Content-Type: application/json" -d '{
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "output": ["hostid", "host"],
            "filter": {
                "host": ["'"$host"'"]
            }
        },
        "auth": "'"$auth_token"'",
        "id": 2
    }' ${zabbix_url} | jq -r '.result[0].hostid')

    echo "$HOST_ID"
}

# Function to create an item in Zabbix
create_zabbix_item() {
  local auth_token=$1
  local zabbix_url="http://${ZABBIX_SERVER}/api_jsonrpc.php"
  local host_id=$2
  local key=$3
  local name=$4

  local create_item_response=$(curl -s -X POST -H 'Content-Type: application/json' -d '{
    "jsonrpc": "2.0",
    "method": "item.create",
    "params": {
      "name": "'"${name}"'",
      "key_": "'"${key}"'",
      "hostid": "'"${host_id}"'",
      "type": 2,
      "value_type": 3
    },
    "auth": "'"${auth_token}"'",
    "id": 1
  }' ${zabbix_url})
  sleep 1

  echo $create_item_response | jq .
}

# Define the URL
URL="http://${RABBIT_HOST}:15672/api/queues"

# Make the HTTP request and store the response
RESPONSE=$(curl -s -u $RABBIT_USER:$RABBIT_PASS $URL)

# Check if the response is empty
if [ -z "$RESPONSE" ]; then
    echo "Failed to get response from RabbitMQ API"
    exit 1
fi

# Parse the JSON response and transform it to the desired format
RESULT=$(echo $RESPONSE| jq '[.[] | {vhost: .vhost, queue: .name, messages_ready: .messages_ready}]')

# Output the transformed result
$DEBUG && echo $RESULT | jq .

RABBIT_HOST_ID=$(get_zabbix_host_id $AUTH_TOKEN $RABBIT_HOST)
echo $RESULT | jq -c '.[] | {vhost: .vhost, queue: .queue, messages_ready: .messages_ready}' |
  while read -r entry; do
    # TODO: If RABBIT_VHOST and RABBIT_QUEUE is not provided, send all queues to Zabbix. If provided, send only that queue.
    VHOST=$(echo $entry | jq -r '.vhost')
    QUEUE=$(echo $entry | jq -r '.queue')
    MESSAGE_COUNT=$(echo $entry | jq -r '.messages_ready')
    ZABBIX_KEY="rabbitmq.test.queue.size[$VHOST,$QUEUE]"
    # TODO: Create Zabbix item if it does not exist
    $DRYRUN || create_zabbix_item $AUTH_TOKEN $RABBIT_HOST_ID $ZABBIX_KEY "RabbitMQ Queue Size [$RABBIT_HOST, $VHOST, $QUEUE]"
    COMMAND="zabbix_sender $TLS_OPTIONS -z $ZABBIX_SERVER -s $RABBIT_HOST -k $ZABBIX_KEY -o $MESSAGE_COUNT"
    # Debug output
    $DEBUG && echo "Sending data to Zabbix: Key=$ZABBIX_KEY, Value=$MESSAGE_COUNT"
    # Execute the command
    $DRYRUN && echo $COMMAND || eval $COMMAND
  done

#TODO: cron job with >/dev/null 2>&1