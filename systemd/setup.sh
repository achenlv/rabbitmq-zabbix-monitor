#!/usr/bin/env bash

echo >> /etc/systemd/system/rabbitmq-zabbix-monitor.service <<EOF
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

EOF
echo ./wsgi.py <<EOF
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
EOF
# ExecStart=/path/to/rabbitmq-zabbix-monitor/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:app
# pip install gunicorn

# Reload systemd to recognize the new service
systemctl daemon-reload
systemctl enable rabbitmq-zabbix-monitor.service
systemctl start rabbitmq-zabbix-monitor.service
systemctl status rabbitmq-zabbix-monitor.service
# Start the service
systemctl start rabbitmq-zabbix-monitor.service
# Stop the service
systemctl stop rabbitmq-zabbix-monitor.service
# Restart the service
systemctl restart rabbitmq-zabbix-monitor.service
# View the logs
journalctl -u rabbitmq-zabbix-monitor.service
# View live logs
journalctl -fu rabbitmq-zabbix-monitor.service

(crontab -l ; echo "*/5 * * * * /path/to/rabbitmq-zabbix-monitor/monitor_service.py") | crontab -
(crontab -l ; echo "*/15 * * * * curl -X POST http://localhost:5000/api/monitoring/check-drift > /dev/null 2>&1") | crontab -

### SELINUX
# Create a temporary policy file
ausearch -c 'python' --raw | audit2allow -M rabbitmq-zabbix-monitor
# Install the policy
semodule -i rabbitmq-zabbix-monitor.pp


### Caddy
# Add the Caddy repository
sudo dnf install 'dnf-command(copr)'
sudo dnf copr enable @caddy/caddy
sudo dnf install caddy

# Start and enable Caddy service
sudo systemctl enable caddy
sudo systemctl start caddy

# Configure Caddy
echo /etc/caddy/Caddyfile <<EOF
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

# 2 & 3. Listen on port 80 for both apps with path-based routing
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
    
    # Route for Zabbix service
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

# 4 & 5. Listen on port 443 for both apps with path-based routing
# Replace example.com with your actual domain name
example.com:443 {
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
    
    # Route for Zabbix service
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
EOF

### Zabbix
echo /etc/zabbix/web/zabbix.conf.php <<EOF
// Add this line to set the base URL
$ZBX_SERVER_NAME = 'Zabbix';
$ZBX_SERVER = 'localhost';
$DB_TYPE = 'POSTGRESQL';
$DB_SERVER = 'localhost';
$DB_PORT = '5432';
$DB_DATABASE = 'zabbix';
$DB_USER = 'zabbix';
$DB_PASSWORD = 'password';
// Add this line:
$ZBX_SERVER_NAME = 'Zabbix';
// Add this for path-based routing:
define('ZBX_ROOT_PATH', '/zabbix/');
EOF

# For RHEL 8
sudo setsebool -P httpd_can_network_connect 1
