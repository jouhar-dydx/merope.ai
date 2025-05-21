import json
import logging
import signal
from functools import partial
from shared.rabbitmq_consumer import RabbitMQConsumer
import time, os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DataProcessor")

# Validate scan message structure
def validate_scan_data(data):
    required_fields = ["scan_id", "region", "resource_type", "data", "timestamp"]
    missing = [field for field in required_fields if field not in data]
    if missing:
        logger.warning(f" Missing required fields: {missing}")
        return False
    return True

# Process incoming scan data
def process_message(ch, method, properties, body, logger_instance):
    try:
        message = json.loads(body.decode())
        logger_instance.info(f" Received scan: {message.get('scan_id')}")

        if not validate_scan_data(message):
            logger_instance.warning(" Invalid scan data format.")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        # Basic featurization / validation
        scan_data = message["data"]
        if "tags" not in scan_data or not scan_data.get("tags"):
            message["orphaned"] = True
            logger_instance.warning(f" Resource marked orphaned: {message['scan_id']}")

        # Future ML integration point
        logger_instance.info(f" Scan processed: {message['scan_id']}")
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as je:
        logger_instance.error(f" JSON decode error: {je}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger_instance.error(f" Processing failed: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

# Graceful shutdown handler
def graceful_shutdown(signal, frame, consumer):
    logger.info(" Data Processor shutting down gracefully...")
    consumer.stop_consuming()
    exit(0)

# Set up logger
logger = logging.getLogger("DataProcessor")
logger.setLevel(logging.INFO)

log_dir = "/logs/merope"
os.makedirs(log_dir, exist_ok=True)

log_file = os.path.join(log_dir, "data_processor.log")

file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(file_handler.formatter)
logger.addHandler(console_handler)

if __name__ == "__main__":
    logger.info(" Starting Data Processor Service...")

    # Initialize RabbitMQ Consumer
    try:
        callback = partial(process_message, logger_instance=logger)
        consumer = RabbitMQConsumer(queue_name="scan_queue", callback=callback)
    except Exception as e:
        logger.error(f" Failed to initialize RabbitMQ consumer: {e}")
        exit(1)

    # Register signal handlers
    signal.signal(signal.SIGINT, lambda s, f: graceful_shutdown(s, f, consumer))
    signal.signal(signal.SIGTERM, lambda s, f: graceful_shutdown(s, f, consumer))

    try:
        logger.info(" Listening for scan messages...")
        consumer.start_consuming()
    except Exception as e:
        logger.error(f" Consumer error: {e}")
        exit(1)