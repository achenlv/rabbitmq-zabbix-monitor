def load_env_variables(env_file):
  """Load environment variables from a .env file."""
  from dotenv import load_dotenv
  import os

  load_dotenv(env_file)

  env_vars = {
    'MAIL_SERVER': os.getenv('MAIL_SERVER'),
    'MAIL_FROM': os.getenv('MAIL_FROM'),
    'MAIL_TO': os.getenv('MAIL_TO'),
    'ZABBIX_SERVER': os.getenv('ZABBIX_SERVER'),
    'ZABBIX_USER': os.getenv('ZABBIX_USER'),
    'ZABBIX_PASS': os.getenv('ZABBIX_PASS'),
    'ZABBIX_HOST_NAME': os.getenv('ZABBIX_HOST_NAME'),
    'ZABBIX_HOST': os.getenv('ZABBIX_HOST'),
    'ZABBIX_ITEM_ID': os.getenv('ZABBIX_ITEM_ID'),
    'ZABBIX_TRIGGER_ID': os.getenv('ZABBIX_TRIGGER_ID'),
    'ZABBIX_HOST_ID': os.getenv('ZABBIX_HOST_ID'),
    'RABBIT_HOST': os.getenv('RABBIT_HOST'),
    'RABBIT_USER': os.getenv('RABBIT_USER'),
    'RABBIT_PASS': os.getenv('RABBIT_PASS'),
    'RABBIT_VHOST': os.getenv('RABBIT_VHOST'),
    'RABBIT_QUEUE': os.getenv('RABBIT_QUEUE')
  }

  for key, value in env_vars.items():
    if value is None:
      raise ValueError(f"Environment variable '{key}' not found.")

  return env_vars

def get_env_variable(var_name):
  """Get an environment variable or raise an error if not found."""
  import os

  value = os.getenv(var_name)
  if value is None:
    raise ValueError(f"Environment variable '{var_name}' not found.")
  return value