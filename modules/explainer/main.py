from shared.kafka_utils import start_kafka_consumer

def explain(message):
    print(f"[📝] Explanation: {message}")

start_kafka_consumer(MODEL_TOPIC, explain)
