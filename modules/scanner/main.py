import time
import uuid
import logging
import signal
from shared.rabbitmq_producer import RabbitMQProducer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ScannerService")

# Generate meaningful scan ID
def generate_scan_id():
    return f"SCAN-{uuid.uuid4()}-{int(time.time())}"

# Simulate scanning an AWS resource (mocked)
def mock_aws_resource_scan(scan_id):
    return {
        "scan_id": scan_id,
        "region": "us-east-1",
        "resource_type": "ec2",
        "data": {
            "instance_id": f"i-{uuid.uuid4().hex[:12]}",
            "state": "running",
            "tags": {"owner": "dev-team", "purpose": "testing"},
            "launch_time": time.time(),
            "public_ip": "54.89.123.45"
        },
        "timestamp": time.time(),
        "orphaned": False  # Will be detected later based on tags/usage
    }

# Graceful shutdown handler
def graceful_shutdown(signal, frame):
    logger.info(" Scanner shutting down gracefully...")
    producer.close()
    exit(0)

if __name__ == "__main__":
    scan_interval = 10  # seconds
    logger.info(" Starting Merope Scanner Service...")

    # Initialize RabbitMQ Producer
    try:
        producer = RabbitMQProducer(host="merope-rabbit")
    except Exception as e:
        logger.error(f" Failed to connect to RabbitMQ: {e}")
        exit(1)

    # Register signal handlers
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    try:
        while True:
            scan_id = generate_scan_id()
            scan_data = mock_aws_resource_scan(scan_id)
            producer.send_message(scan_data)
            logger.info(f" Sent scan: {scan_id}")
            time.sleep(scan_interval)
    except Exception as e:
        logger.error(f" Scanner error: {e}")
        producer.close()
        exit(1)