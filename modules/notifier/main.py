from shared.kafka_utils import start_kafka_consumer
import requests

GOOGLE_CHAT_WEBHOOK = ""

def alert(message):
    if GOOGLE_CHAT_WEBHOOK:
        requests.post(GOOGLE_CHAT_WEBHOOK, json={"text": f"🚨 Orphaned resource found: {message}"})
    print(f"🔔 Alert sent: {message}")

start_kafka_consumer("model_output", alert)
