from shared.kafka_utils import start_kafka_consumer
from sklearn.ensemble import IsolationForest
import numpy as np

def analyze(message):
    scores = IsolationForest(n_estimators=100).score_samples([[len(m.get("Tags", []))] for m in message])
    for i, score in enumerate(scores):
        if score < -0.5:
            print(f"🚩 Anomaly: {message[i]['resource_id']} | Score: {score}")

start_kafka_consumer("processed_data", analyze)
