from shared.kafka_utils import start_kafka_consumer

def alert(message):
    print(f"🔔 Alert sent: {message}")

start_kafka_consumer("model_output", alert)
