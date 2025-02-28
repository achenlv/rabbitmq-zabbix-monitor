# RabbitMQ-Zabbix Monitor

## Overview

The RabbitMQ-Zabbix Monitor is a comprehensive monitoring solution designed to track RabbitMQ clusters and send metrics to Zabbix. It provides real-time monitoring of queue sizes, detects abnormal growth patterns (drifts), and sends alerts via email when predefined thresholds are exceeded.

## Features

- **RabbitMQ Monitoring**: Connect to multiple RabbitMQ clusters and monitor queues across different virtual hosts
- **Zabbix Integration**: Send queue metrics to Zabbix for long-term storage and visualization
- **Drift Detection**: Identify abnormal queue growth patterns and send alerts
- **Threshold Monitoring**: Set thresholds for queue sizes and receive alerts when exceeded
- **Email Notifications**: Configurable email alerts with customizable templates
- **RESTful API**: Comprehensive API with Swagger UI documentation
- **Systemd Service**: Run as a system service with automatic monitoring and recovery

## Architecture

The application is built with a modular architecture:

- **API Layer**: Flask-based RESTful API with Swagger documentation
- **Core Services**: Modules for RabbitMQ, Zabbix, and notification handling
- **Monitoring Service**: Collects metrics and processes alerts
- **Configuration**: JSON-based configuration with environment variable support
- **Utilities**: Logging, error handling, and helper functions

## Installation

### Prerequisites

- Python 3.6+
- RabbitMQ server(s)
- Zabbix server
- SMTP server for email notifications

### Basic Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/rabbitmq-zabbix-monitor.git
   cd rabbitmq-zabbix-monitor
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create and configure the configuration file:
   ```bash
   mkdir -p config
   cp config/config.json.example config/config.json
   # Edit config/config.json with your settings
   ```

5. Run the application:
   ```bash
   python app.py
   ```

6. Access the Swagger UI at `http://127.0.0.1:5000/api/docs`

### Systemd Service Installation

For production deployments, you can install the application as a systemd service:

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/rabbitmq-zabbix-monitor.service
   ```

2. Add the following content (adjust paths and user/group settings):
   ```ini
   [Unit]
   Description=RabbitMQ Zabbix Monitor Service
   After=network.target

   [Service]
   User=your_service_user
   Group=your_service_group
   WorkingDirectory=/path/to/rabbitmq-zabbix-monitor
   Environment="PATH=/path/to/rabbitmq-zabbix-monitor/venv/bin"
   Environment="BEHIND_PROXY=true"
   ExecStart=/path/to/rabbitmq-zabbix-monitor/venv/bin/python app/main.py
   Restart=always
   RestartSec=10
   StandardOutput=journal
   StandardError=journal
   SyslogIdentifier=rabbitmq-zabbix-monitor

   [Install]
   WantedBy=multi-user.target
   ```

   Alternatively, you can use the setup script which will create this file:
   ```bash
   sudo ./systemd/setup.sh
   ```

3. Create a WSGI file for production deployment:
   ```bash
   nano wsgi.py
   ```

4. Add the following content:
   ```python
   from app import create_app

   app = create_app()

   if __name__ == "__main__":
       app.run()
   ```

5. For production deployment with Gunicorn (optional):
   ```bash
   pip install gunicorn
   ```
   
   Then update the ExecStart line in the service file:
   ```
   ExecStart=/path/to/rabbitmq-zabbix-monitor/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:app
   ```

6. Reload systemd, enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable rabbitmq-zabbix-monitor.service
   sudo systemctl start rabbitmq-zabbix-monitor.service
   ```

7. Check the service status:
   ```bash
   sudo systemctl status rabbitmq-zabbix-monitor.service
   ```

8. Service management commands:
   ```bash
   # Start the service
   sudo systemctl start rabbitmq-zabbix-monitor.service
   
   # Stop the service
   sudo systemctl stop rabbitmq-zabbix-monitor.service
   
   # Restart the service
   sudo systemctl restart rabbitmq-zabbix-monitor.service
   
   # View the logs
   sudo journalctl -u rabbitmq-zabbix-monitor.service
   
   # View live logs
   sudo journalctl -fu rabbitmq-zabbix-monitor.service
   ```

### SELinux Configuration

If you're running on a system with SELinux enabled (like RHEL, CentOS, or Fedora), you'll need to configure SELinux to allow the service to run:

1. Create a temporary policy file:
   ```bash
   sudo ausearch -c 'python' --raw | audit2allow -M rabbitmq-zabbix-monitor
   ```

2. Install the policy:
   ```bash
   sudo semodule -i rabbitmq-zabbix-monitor.pp
   ```

   Alternatively, you can set the appropriate contexts:
   ```bash
   sudo chcon -R -t bin_t /var/www/rabbitmq-zabbix-monitor/.venv/bin/
   sudo chcon -t bin_t /var/www/rabbitmq-zabbix-monitor/app.py
   sudo chcon -t bin_t /var/www/rabbitmq-zabbix-monitor/systemd/rabbitmq_zabbix_monitor.sh
   ```

3. For web server connections (if using Caddy or other web servers):
   ```bash
   sudo setsebool -P httpd_can_network_connect 1
   ```

### Caddy Server Installation

Caddy is a modern web server that can be used as a reverse proxy for the application. It provides automatic HTTPS with Let's Encrypt certificates.

1. Install Caddy (RHEL/CentOS/Fedora):
   ```bash
   sudo dnf install 'dnf-command(copr)'
   sudo dnf copr enable @caddy/caddy
   sudo dnf install caddy
   ```

2. Start and enable Caddy service:
   ```bash
   sudo systemctl enable caddy
   sudo systemctl start caddy
   ```

3. Configure Caddy by creating a Caddyfile:
   ```bash
   sudo nano /etc/caddy/Caddyfile
   ```

4. Add the following configuration (adjust as needed):
   ```
   # 1. Listen on port 8000 for Flask app at root path
   :8000 {
       # Reverse proxy to Flask/WSGI app
       reverse_proxy 127.0.0.1:5000 {
           header_up Host {host}
           header_up X-Real-IP {remote}
           header_up X-Forwarded-For {remote}
           header_up X-Forwarded-Proto {scheme}
       }
       
       # Enable logging
       log {
           output file /var/log/caddy/flask-8000.log
           format json
       }
   }

   # 2. Listen on port 80 for path-based routing
   :80 {
       # Route for RabbitMQ-Zabbix-Monitor app
       handle_path /rabbitmq-zabbix-monitor/* {
           reverse_proxy 127.0.0.1:5000 {
               header_up Host {host}
               header_up X-Real-IP {remote}
               header_up X-Forwarded-For {remote}
               header_up X-Forwarded-Proto {scheme}
           }
       }
       
       # Route for Zabbix service (if applicable)
       handle_path /zabbix/* {
           reverse_proxy 127.0.0.1:8080 {
               header_up Host {host}
               header_up X-Real-IP {remote}
               header_up X-Forwarded-For {remote}
               header_up X-Forwarded-Proto {scheme}
           }
       }
       
       # Enable logging
       log {
           output file /var/log/caddy/http.log
           format json
       }
   }

   # 3. HTTPS with automatic certificates (replace example.com with your domain)
   example.com {
       # Enable TLS with automatic HTTPS
       tls internal
       
       # Route for RabbitMQ-Zabbix-Monitor app
       handle_path /rabbitmq-zabbix-monitor/* {
           reverse_proxy 127.0.0.1:5000 {
               header_up Host {host}
               header_up X-Real-IP {remote}
               header_up X-Forwarded-For {remote}
               header_up X-Forwarded-Proto {scheme}
           }
       }
       
       # Route for Zabbix service (if applicable)
       handle_path /zabbix/* {
           reverse_proxy 127.0.0.1:8080 {
               header_up Host {host}
               header_up X-Real-IP {remote}
               header_up X-Forwarded-For {remote}
               header_up X-Forwarded-Proto {scheme}
           }
       }
       
       # Enable logging
       log {
           output file /var/log/caddy/https.log
           format json
       }
   }
   ```

5. Reload Caddy to apply the configuration:
   ```bash
   sudo systemctl reload caddy
   ```

### Zabbix Integration (if using Zabbix web interface)

If you're using Zabbix with path-based routing, you'll need to configure the Zabbix web interface:

1. Edit the Zabbix PHP configuration file:
   ```bash
   sudo nano /etc/zabbix/web/zabbix.conf.php
   ```

2. Add or modify the following lines:
   ```php
   // Set the server name
   $ZBX_SERVER_NAME = 'Zabbix';
   
   // Add this for path-based routing
   define('ZBX_ROOT_PATH', '/zabbix/');
   ```

## Configuration

The application is configured using a JSON file located at `config/config.json`. The configuration includes the following sections:

### App Configuration

```json
{
  "app": {
    "host": "0.0.0.0",
    "port": 5000,
    "log_dir": "log"
  }
}
```

### RabbitMQ Configuration

```json
{
  "rabbitmq": {
    "clusters": [
      {
        "id": "prod-cluster",
        "description": "Production RabbitMQ Cluster",
        "nodes": [
          {
            "hostname": "rabbitmq-prod-01.example.com",
            "api_port": 15672,
            "primary": true
          },
          {
            "hostname": "rabbitmq-prod-02.example.com",
            "api_port": 15672
          }
        ],
        "auth": {
          "user": "monitoring",
          "password": "your-password"
        },
        "monitoring": {
          "enabled": true,
          "default_zabbix_host": "rabbitmq-prod"
        }
      }
    ]
  }
}
```

### Zabbix Configuration

```json
{
  "zabbix": {
    "url": "https://zabbix.example.com",
    "server": "zabbix-server.example.com",
    "port": 10051,
    "user": "api-user",
    "password": "api-password",
    "tls_connect": "psk",
    "tls_psk_identity": "PSK_IDENTITY",
    "tls_psk_file": "C:\\zabbix\\psk.key",
    "tls_psk_file_linux": "/etc/zabbix/psk.key"
  }
}
```

### Monitoring Configuration

```json
{
  "monitoring": {
    "threshold": 1000,
    "queues": [
      {
        "cluster_node": "rabbitmq-prod-01.example.com",
        "vhost": "/",
        "queue": "important-queue",
        "zabbix_host": "rabbitmq-prod"
      }
    ]
  }
}
```

### Email Configuration

```json
{
  "email": {
    "smtp_server": "smtp.example.com",
    "smtp_port": 587,
    "smtp_user": "alerts@example.com",
    "smtp_password": "your-password",
    "from_address": "rabbitmq-monitor@example.com",
    "templates": {
      "drift": "templates/drift_alert.html",
      "threshold": "templates/threshold_alert.html",
      "error": "templates/error_alert.html"
    },
    "alerts": {
      "drift": {
        "subject": "RabbitMQ Queue Drift Alert - {vhost}/{queue}",
        "template": "drift",
        "to": ["team@example.com"],
        "cc": ["manager@example.com"]
      },
      "threshold": {
        "subject": "RabbitMQ Queue Threshold Alert - {vhost}/{queue}",
        "template": "threshold",
        "to": ["team@example.com"]
      }
    }
  }
}
```

## API Endpoints

The application provides a RESTful API with comprehensive documentation. All endpoints are accessible through the Swagger UI at `http://127.0.0.1:5000/api/docs`.

### RabbitMQ Endpoints

#### Get All RabbitMQ Clusters

- **Endpoint**: `/api/rabbitmq/clusters`
- **Method**: GET
- **Description**: Returns a list of all configured RabbitMQ clusters with their details (excluding sensitive auth information)
- **Response**: Array of cluster objects
- **Example Response**:
  ```json
  [
    {
      "id": "prod-cluster",
      "description": "Production RabbitMQ Cluster",
      "nodes": [
        {
          "hostname": "rabbitmq-prod-01.example.com",
          "api_port": 15672,
          "primary": true
        },
        {
          "hostname": "rabbitmq-prod-02.example.com",
          "api_port": 15672
        }
      ]
    }
  ]
  ```

#### Get a Specific RabbitMQ Cluster

- **Endpoint**: `/api/rabbitmq/clusters/<cluster_id>`
- **Method**: GET
- **Parameters**:
  - `cluster_id` (path): The cluster identifier
- **Description**: Returns details for a specific RabbitMQ cluster
- **Response**: Cluster object
- **Example Request**: `/api/rabbitmq/clusters/prod-cluster`
- **Example Response**:
  ```json
  {
    "id": "prod-cluster",
    "description": "Production RabbitMQ Cluster",
    "nodes": [
      {
        "hostname": "rabbitmq-prod-01.example.com",
        "api_port": 15672,
        "primary": true
      },
      {
        "hostname": "rabbitmq-prod-02.example.com",
        "api_port": 15672
      }
    ]
  }
  ```

#### Get All Queues for a Cluster

- **Endpoint**: `/api/rabbitmq/clusters/<cluster_id>/queues`
- **Method**: GET
- **Parameters**:
  - `cluster_id` (path): The cluster identifier
- **Description**: Returns all queues for a specific RabbitMQ cluster
- **Response**: Array of queue objects
- **Example Request**: `/api/rabbitmq/clusters/prod-cluster/queues`
- **Example Response**:
  ```json
  [
    {
      "vhost": "/",
      "name": "important-queue",
      "messages": 42,
      "consumers": 2,
      "state": "running"
    },
    {
      "vhost": "test",
      "name": "test-queue",
      "messages": 10,
      "consumers": 1,
      "state": "running"
    }
  ]
  ```

#### Get Information About a Specific Queue

- **Endpoint**: `/api/rabbitmq/clusters/<cluster_id>/queues/<vhost>/<queue_name>`
- **Method**: GET
- **Parameters**:
  - `cluster_id` (path): The cluster identifier
  - `vhost` (path): The virtual host (URL-encoded)
  - `queue_name` (path): The queue name
- **Description**: Returns detailed information about a specific queue
- **Response**: Queue object
- **Example Request**: `/api/rabbitmq/clusters/prod-cluster/queues/%2F/important-queue`
- **Example Response**:
  ```json
  {
    "vhost": "/",
    "name": "important-queue",
    "messages": 42,
    "consumers": 2,
    "state": "running"
  }
  ```

### Zabbix Endpoints

#### Get Zabbix Hosts

- **Endpoint**: `/api/zabbix/hosts`
- **Method**: GET
- **Description**: Returns a list of all Zabbix hosts
- **Response**: Array of host objects
- **Example Response**:
  ```json
  [
    {
      "hostid": "10084",
      "host": "rabbitmq-prod",
      "name": "RabbitMQ Production",
      "status": 0
    }
  ]
  ```

#### Get a Specific Zabbix Host

- **Endpoint**: `/api/zabbix/hosts/<hostname>`
- **Method**: GET
- **Parameters**:
  - `hostname` (path): The host name
- **Description**: Returns details for a specific Zabbix host
- **Response**: Host object
- **Example Request**: `/api/zabbix/hosts/rabbitmq-prod`
- **Example Response**:
  ```json
  {
    "hostid": "10084",
    "host": "rabbitmq-prod",
    "name": "RabbitMQ Production",
    "status": 0
  }
  ```

#### Send a Value to Zabbix

- **Endpoint**: `/api/zabbix/send`
- **Method**: POST, GET
- **Parameters (POST body or GET query)**:
  - `host` (required): Zabbix host name
  - `key` (required): Item key
  - `value` (required): Item value
- **Description**: Sends a single value to Zabbix
- **Response**: Result object
- **Example Request (POST)**:
  ```bash
  curl -X POST http://localhost:5000/api/zabbix/send \
    -H "Content-Type: application/json" \
    -d '{"host": "rabbitmq-prod", "key": "rabbitmq.test.queue.size[/,important-queue]", "value": 42}'
  ```
- **Example Response**:
  ```json
  {
    "success": true,
    "message": "processed: 1; failed: 0; total: 1; seconds spent: 0.000055",
    "command": "zabbix_sender -z zabbix-server.example.com -p 10051 -s rabbitmq-prod -k rabbitmq.test.queue.size[/,important-queue] -o 42",
    "returncode": 0
  }
  ```

#### Send Multiple Values to Zabbix

- **Endpoint**: `/api/zabbix/send-batch`
- **Method**: POST
- **Parameters**:
  - Request body: Array of data point objects, each with:
    - `host` (required): Zabbix host name
    - `key` (required): Item key
    - `value` (required): Item value
- **Description**: Sends multiple values to Zabbix in a single batch
- **Response**: Result object
- **Example Request**:
  ```bash
  curl -X POST http://localhost:5000/api/zabbix/send-batch \
    -H "Content-Type: application/json" \
    -d '[
      {"host": "rabbitmq-prod", "key": "rabbitmq.test.queue.size[/,queue1]", "value": 42},
      {"host": "rabbitmq-prod", "key": "rabbitmq.test.queue.size[/,queue2]", "value": 10}
    ]'
  ```
- **Example Response**:
  ```json
  {
    "success": true,
    "message": "processed: 2; failed: 0; total: 2; seconds spent: 0.000128",
    "command": "zabbix_sender -z zabbix-server.example.com -p 10051 -i /tmp/tmpfile123456",
    "returncode": 0
  }
  ```

### Monitoring Endpoints

#### Run Monitoring Cycle

- **Endpoint**: `/api/monitoring/run`
- **Method**: POST, GET
- **Description**: Runs the monitoring cycle for configured queues
- **Response**: Monitoring result object
- **Example Request**: `curl -X POST http://localhost:5000/api/monitoring/run`
- **Example Response**:
  ```json
  {
    "metrics_collected": 3,
    "data_points_sent": 9,
    "success": true,
    "zabbix_result": {
      "success": true,
      "message": "processed: 9; failed: 0; total: 9; seconds spent: 0.000342"
    }
  }
  ```

#### Run Monitoring Cycle for All Queues

- **Endpoint**: `/api/monitoring/run-all`
- **Method**: POST, GET
- **Description**: Runs the monitoring cycle for ALL queues on ALL vhosts
- **Response**: Monitoring result object
- **Example Request**: `curl -X POST http://localhost:5000/api/monitoring/run-all`
- **Example Response**:
  ```json
  {
    "metrics_collected": 15,
    "data_points_sent": 45,
    "success": true,
    "zabbix_result": {
      "success": true,
      "message": "processed: 45; failed: 0; total: 45; seconds spent: 0.001234"
    }
  }
  ```

#### Get All Monitored Queues

- **Endpoint**: `/api/monitoring/queues`
- **Method**: GET
- **Description**: Returns a list of all queues configured for monitoring
- **Response**: Array of queue configuration objects
- **Example Response**:
  ```json
  [
    {
      "cluster_node": "rabbitmq-prod-01.example.com",
      "vhost": "/",
      "queue": "important-queue",
      "zabbix_host": "rabbitmq-prod"
    }
  ]
  ```

#### Collect Metrics Without Sending to Zabbix

- **Endpoint**: `/api/monitoring/metrics`
- **Method**: GET
- **Description**: Collects metrics for configured queues without sending to Zabbix
- **Response**: Array of metric objects
- **Example Response**:
  ```json
  [
    {
      "host": "rabbitmq-prod",
      "metrics": {
        "queue.messages": 42,
        "queue.consumers": 2,
        "queue.state": 1
      },
      "queue_info": {
        "vhost": "/",
        "queue": "important-queue",
        "messages": 42,
        "consumers": 2,
        "state": "running"
      }
    }
  ]
  ```

#### Collect Metrics for All Queues Without Sending to Zabbix

- **Endpoint**: `/api/monitoring/metrics-all`
- **Method**: GET
- **Description**: Collects metrics for ALL queues on ALL vhosts without sending to Zabbix
- **Response**: Array of metric objects
- **Example Response**: Similar to `/api/monitoring/metrics` but includes all queues

#### Check for Queue Drift and Send Notifications

- **Endpoint**: `/api/monitoring/check-drift`
- **Method**: POST, GET
- **Description**: Checks all monitored queues for drift and sends notifications if needed
- **Response**: Drift result object
- **Example Request**: `curl -X POST http://localhost:5000/api/monitoring/check-drift`
- **Example Response**:
  ```json
  {
    "alerts_detected": 2,
    "notifications_sent": 2,
    "results": [
      {
        "type": "drift",
        "queue": "/important-queue",
        "result": {
          "success": true,
          "message": "Alert sent to team@example.com"
        }
      }
    ]
  }
  ```

#### Comprehensive Monitoring

- **Endpoint**: `/api/monitoring/monitor-all-drift`
- **Method**: POST, GET
- **Description**: Comprehensive monitoring that collects metrics for ALL queues and checks for drift
- **Response**: Combined monitoring and drift result object
- **Example Request**: `curl -X POST http://localhost:5000/api/monitoring/monitor-all-drift`
- **Example Response**:
  ```json
  {
    "metrics_result": {
      "metrics_collected": 15,
      "data_points_sent": 45,
      "zabbix_result": {
        "success": true,
        "message": "processed: 45; failed: 0; total: 45; seconds spent: 0.001234"
      },
      "success": true
    },
    "drift_result": {
      "alerts_detected": 2,
      "notifications_sent": 2,
      "results": [
        {
          "type": "drift",
          "queue": "/important-queue",
          "result": {
            "success": true,
            "message": "Alert sent to team@example.com"
          }
        }
      ]
    },
    "success": true
  }
  ```

### Email Endpoints

#### Send Email Notification

- **Endpoint**: `/api/email/send`
- **Method**: POST
- **Parameters**:
  - Request body:
    - `subject` (required): Email subject
    - `recipients` (required): Array of recipient email addresses
    - `body` (required): Email body content
    - `template` (optional): Template name to use
- **Description**: Sends an email notification
- **Example Request**:
  ```bash
  curl -X POST http://localhost:5000/api/email/send \
    -H "Content-Type: application/json" \
    -d '{
      "subject": "Alert notification",
      "recipients": ["user@example.com"],
      "body": "This is a test notification",
      "template": "drift"
    }'
  ```
- **Example Response**:
  ```json
  {
    "message": "Email sent successfully"
  }
  ```

## Usage Examples

### Monitoring Specific Queues

To monitor specific queues, add them to the `monitoring.queues` section in the configuration file, then run:

```bash
curl -X POST http://localhost:5000/api/monitoring/run
```

### Monitoring All Queues

To monitor all queues across all configured clusters:

```bash
curl -X POST http://localhost:5000/api/monitoring/run-all
```

### Checking for Queue Drift

To check for queue size drift and send notifications:

```bash
curl -X POST http://localhost:5000/api/monitoring/check-drift
```

### Comprehensive Monitoring

To run a complete monitoring cycle (collect metrics and check for drift):

```bash
curl -X POST http://localhost:5000/api/monitoring/monitor-all-drift
```

### Sending Values to Zabbix

To send a single value to Zabbix:

```bash
curl -X POST http://localhost:5000/api/zabbix/send \
  -H "Content-Type: application/json" \
  -d '{"host": "rabbitmq-prod", "key": "rabbitmq.test.queue.size[/,important-queue]", "value": 42}'
```

## Monitoring and Alerting

### Queue Size Monitoring

The application monitors queue sizes and sends the data to Zabbix. You can configure thresholds in the `monitoring` section of the configuration file.

### Drift Detection

The application detects abnormal queue growth patterns by comparing the current queue size with the previous measurement. If the queue size increases, a drift alert is generated.

### Email Alerts

Email alerts are sent when:
- Queue size exceeds the configured threshold
- Queue size drift is detected
- Errors occur during monitoring

Alert templates are located in the `templates` directory and can be customized.

## Deployment Options

### Standalone Deployment

Run the application as a standalone Flask application:

```bash
python app.py
```

### Systemd Service

Run as a systemd service for production environments:

```bash
sudo systemctl start rabbitmq-zabbix-monitor.service
```

### Behind a Proxy

The application can be deployed behind a proxy by setting the `BEHIND_PROXY` environment variable:

```bash
export BEHIND_PROXY=true
python app.py
```

This enables path-based routing with a prefix of `/rabbitmq-zabbix-monitor`.

### With Caddy

The application can be deployed with Caddy as a reverse proxy. Sample Caddy configuration is provided in the `systemd/setup.sh` file.

## Cron Jobs

For periodic monitoring, you can set up cron jobs:

1. Add monitoring service check (runs every 5 minutes):
   ```bash
   (crontab -l ; echo "*/5 * * * * /path/to/rabbitmq-zabbix-monitor/systemd/monitor_service.py") | crontab -
   ```

2. Add drift check (runs every 15 minutes):
   ```bash
   (crontab -l ; echo "*/15 * * * * curl -X POST http://localhost:5000/api/monitoring/check-drift > /dev/null 2>&1") | crontab -
   ```

Make sure to replace `/path/to/rabbitmq-zabbix-monitor` with the actual path to your installation.

## Troubleshooting

### Logging

Logs are stored in the `log` directory. The log level and format can be configured in `app/utils/logging.py`.

### Service Monitoring

The application includes a service monitoring script that checks if the service is running and restarts it if necessary:

```bash
python systemd/monitor_service.py
```

### Common Issues

1. **Connection to RabbitMQ fails**:
   - Check the RabbitMQ credentials in the configuration file
   - Ensure the RabbitMQ API port (default: 15672) is accessible
   - Verify that the RabbitMQ user has the necessary permissions

2. **Zabbix sender fails**:
   - Ensure the Zabbix server is accessible
   - Check the PSK configuration if TLS is enabled
   - Verify that the Zabbix host exists and is active

3. **Email alerts are not sent**:
   - Check the SMTP server configuration
   - Verify that the SMTP user has permission to send emails
   - Check the email templates for syntax errors

## Development

### Running in Debug Mode

For development, you can run the application in debug mode:

```bash
python debug.py
```

This will print all registered routes and API namespaces.

### Testing

Run the RabbitMQ client tests:

```bash
python -m tests.test_rabbitmq
```

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License.
