from shared.kafka_utils import start_kafka_consumer

def process_message(value):
    print(f"[📥] Raw message: {value}")

start_kafka_consumer(PROCESSED_TOPIC, process_message)
