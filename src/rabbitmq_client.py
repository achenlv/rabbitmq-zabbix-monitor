import pika
import os

class RabbitMQClient:
  def __init__(self, host, username, password, vhost, queue):
    self.host = host
    self.username = username
    self.password = password
    self.vhost = vhost
    self.queue = queue
    self.connection = None
    self.channel = None

  def connect(self):
    credentials = pika.PlainCredentials(self.username, self.password)
    parameters = pika.ConnectionParameters(self.host, virtual_host=self.vhost, credentials=credentials)
    self.connection = pika.BlockingConnection(parameters)
    self.channel = self.connection.channel()

  def get_queue_item_count(self):
    if not self.channel:
      self.connect()
    queue = self.channel.queue_declare(queue=self.queue, passive=True)
    return queue.method.message_count

  def close(self):
    if self.connection:
      self.connection.close()