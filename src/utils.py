def load_env_variables(env_file):
  """Load environment variables from a .env file."""
  from dotenv import load_dotenv
  import os

  load_dotenv(env_file)

def get_env_variable(var_name):
  """Get an environment variable or raise an error if not found."""
  import os

  value = os.getenv(var_name)
  if value is None:
    raise ValueError(f"Environment variable '{var_name}' not found.")
  return value