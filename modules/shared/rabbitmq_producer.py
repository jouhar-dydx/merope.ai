import pika
import json
import logging

logging.basicConfig(level=logging.INFO)

class RabbitMQProducer:
    def __init__(self, host="merope-rabbit", queue_name="scan_queue"):
        self.host = host
        self.queue_name = queue_name
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
            self.channel.confirm_delivery()
            logging.info(" RabbitMQ producer connected.")
        except Exception as e:
            logging.error(f" Failed to connect to RabbitMQ: {e}")
            raise

    def send_message(self, message: dict):
        try:
            self.channel.basic_publish(
                exchange='scan_exchange',
                routing_key='scan.key',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2),  # Persistent message
                mandatory=True
            )
            logging.info(f"[x] Sent scan: {message.get('scan_id')}")
        except Exception as e:
            logging.error(f" Failed to send message: {e}")

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            logging.info(" RabbitMQ connection closed.")