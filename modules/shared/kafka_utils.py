from confluent_kafka import Producer, Consumer

KAFKA_BOOTSTRAP_SERVER = "kafka:9092"
SCAN_TOPIC = "aws_scan_data"
PROCESS_TOPIC = "processed_data"
MODEL_TOPIC = "model_output"
NOTIFIER_TOPIC = "alerts"

def send_to_kafka(topic, message):
    p = Producer({'bootstrap.servers': KAFKA_BOOTSTRAP_SERVER})
    def delivery_report(err, msg):
        if err:
            print(f"❌ Message delivery failed: {err}")
        else:
            print(f"[x] Delivered to {msg.topic()} [{msg.partition()}]")
    try:
        p.produce(topic, key=message["resource_id"], value=str(message), callback=delivery_report)
        p.poll(0)
        p.flush(timeout=10)
    finally:
        p.close()

def start_kafka_consumer(topic, handler_func):
    c = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVER,
        'group.id': f"{topic}_consumer",
        'auto.offset.reset': 'earliest'
    })
    c.subscribe([topic])
    print(f"👂 Listening to topic '{topic}'...")

    while True:
        msg = c.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            print(f"❌ Kafka error: {msg.error()}")
            continue
        try:
            handler_func(msg.value().decode('utf-8'))
        except Exception as e:
            print(f"💥 Processing error: {e}")

    c.close()
