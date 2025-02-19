class RabbitMQClient:
  def __init__(self, host, username, password, vhost):
    import pika
    self.connection = pika.BlockingConnection(
      pika.ConnectionParameters(host=host, virtual_host=vhost, credentials=pika.PlainCredentials(username, password))
    )
    self.channel = self.connection.channel()

  def get_queue_item_count(self, queue_name):
    queue = self.channel.queue_declare(queue=queue_name, passive=True)
    return queue.method.message_count

  def close(self):
    self.connection.close()