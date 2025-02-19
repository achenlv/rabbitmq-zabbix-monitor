# RabbitMQ-Zabbix Monitor

## Overview
The RabbitMQ-Zabbix Monitor is a Python project that monitors the item count of a specified RabbitMQ queue in a given virtual host. It utilizes the Zabbix API to set a trapper item and trigger, sending notifications via email if the item count increases since the last check. The project is designed to run every working day at specified times.

## Project Structure
```
rabbitmq-zabbix-monitor
├── src
│   ├── main.py                # Entry point of the application
│   ├── rabbitmq_client.py      # RabbitMQ client for queue operations
│   ├── zabbix_client.py        # Zabbix API client for monitoring
│   ├── email_client.py         # Email client for notifications
│   └── utils.py                # Utility functions
├── config
│   └── config.env             # Environment variables configuration
├── scripts
│   └── schedule_task.sh       # Script to schedule the monitoring task
├── requirements.txt           # Python dependencies
└── README.md                  # Project documentation
```

## Setup Instructions
1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd rabbitmq-zabbix-monitor
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file in the `config` directory and populate it with the following variables:
   ```
   MAIL_SERVER=<your_mail_server>
   MAIL_FROM=<your_email>
   MAIL_TO=<recipient_email>
   ZABBIX_SERVER=<your_zabbix_server>
   ZABBIX_USER=<your_zabbix_username>
   ZABBIX_PASS=<your_zabbix_password>
   ZABBIX_HOST_NAME=<your_zabbix_host_name>
   ZABBIX_ITEM_ID=<your_zabbix_item_id>
   RABBIT_HOST=<your_rabbitmq_host>
   RABBIT_USER=<your_rabbitmq_username>
   RABBIT_PASS=<your_rabbitmq_password>
   RABBIT_VHOST=<your_rabbitmq_virtual_host>
   RABBIT_QUEUE=<your_rabbitmq_queue>
   ```

## Usage
To run the monitoring script, execute the following command:
```bash
python src/main.py
```

## Scheduling
To schedule the task to run at specified times every working day, use the provided `schedule_task.sh` script. Modify the script as necessary to fit your scheduling needs.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.