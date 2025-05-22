from shared.kafka_utils import start_kafka_consumer

def persist_message(message):
    print(f"[💾] Saving to DB: {message}")

start_kafka_consumer("aws_scan_data", persist_message)
