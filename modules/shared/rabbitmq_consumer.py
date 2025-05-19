import pika
import json
import logging
from functools import partial

logging.basicConfig(level=logging.INFO)

def default_callback(ch, method, properties, body):
    try:
        logging.info(f"[x] Received: {body.decode()}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logging.error(f" Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

class RabbitMQConsumer:
    def __init__(
        self,
        host="merope-rabbit",
        queue_name="scan_queue",
        callback=default_callback
    ):
        self.host = host
        self.queue_name = queue_name
        self.callback = callback

        self.credentials = pika.PlainCredentials('scanner', 'scannerpass')
        self.parameters = pika.ConnectionParameters(
            host=self.host,
            port=5672,
            credentials=self.credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )

        try:
            self.connection = pika.BlockingConnection(self.parameters)
            self.channel = self.connection.channel()
            self.channel.basic_qos(prefetch_count=1, global_qos=True)
            logging.info(" RabbitMQ consumer connected.")
        except Exception as e:
            logging.error(f" Failed to connect to RabbitMQ: {e}")
            raise

    def start_consuming(self):
        try:
            logging.info(f" [*] Waiting for messages in {self.queue_name}. To exit press CTRL+C")
            self.channel.basic_consume(queue=self.queue_name, on_message_callback=self.callback)
            self.channel.start_consuming()
        except Exception as e:
            logging.error(f" Error consuming messages: {e}")
            self.stop_consuming()

    def stop_consuming(self):
        if self.connection and self.connection.is_open:
            self.connection.add_callback_threadsafe(self.connection.close)
            logging.info(" RabbitMQ consumer stopped.")