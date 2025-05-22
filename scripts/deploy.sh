#!/bin/bash

set -e

echo "🧹 Starting folder cleanup..."
cd "$(dirname "$0")"
PROJECT_ROOT="$(pwd)"

# --- Step 1: Ensure base directories exist ---
echo "📁 Creating base structure if not exists..."

mkdir -p "$PROJECT_ROOT/shared" \
         "$PROJECT_ROOT/modules/scanner" \
         "$PROJECT_ROOT/modules/data_processor" \
         "$PROJECT_ROOT/modules/model_engine" \
         "$PROJECT_ROOT/modules/notifier" \
         "$PROJECT_ROOT/modules/storage" \
         "$PROJECT_ROOT/modules/explainer" \
         "$PROJECT_ROOT/data/zookeeper/data" \
         "$PROJECT_ROOT/data/kafka/logs" \
         "$PROJECT_ROOT/logs/services/{scanner,data_processor,model_engine,notifier,storage,explainer}/ec2"

# --- Step 2: Make sure shared utilities are present ---
echo "🧱 Writing dummy shared files (if not exist)..."
cat > "$PROJECT_ROOT/shared/logger.py" << 'EOL'
import logging
import os

def get_logger(name, log_file="app.log"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler())

    return logger
EOL

cat > "$PROJECT_ROOT/shared/kafka_utils.py" << 'EOL'
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
EOL

cat > "$PROJECT_ROOT/shared/message_schema.py" << 'EOL'
import json
from datetime import datetime

class ScanMessage:
    def __init__(self, scan_id, region, service, resource_type, resource_id, data):
        self.scan_id = scan_id
        self.region = region
        self.service = service
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.data = data
        self.timestamp = int(datetime.now().timestamp())
        self.orphaned = False
        self.public_ip = False
        self.missing_metadata = {"tags_missing": True}
        self.associated_resources = {}

    def to_json(self):
        return json.dumps(self.__dict__)
EOL

# --- Step 3: Remove broken symlinks or old containers ---
echo "🗑️ Removing old containers..."
sudo docker stop $(sudo docker ps -a -f "name=merope-*" -q) 2>/dev/null || true
sudo docker rm $(sudo docker ps -a -f "name=merope-*" -q) 2>/dev/null || true

# --- Step 4: Link shared into each module ---
echo "🔗 Linking shared/ into each module..."
for module in scanner data_processor model_engine notifier storage explainer; do
    MODULE_DIR="$PROJECT_ROOT/modules/$module"
    echo "🔗 $module -> shared/"

    # Remove any old symlink or dir
    if [ -L "$MODULE_DIR/shared" ]; then
        rm "$MODULE_DIR/shared"
    elif [ -d "$MODULE_DIR/shared" ]; then
        rm -rf "$MODULE_DIR/shared"
    fi

    # Create new symlink
    ln -sf ../shared "$MODULE_DIR/shared"
done

# --- Step 5: Fix data dirs ---
echo "📁 Creating data directories..."
mkdir -p "$PROJECT_ROOT/data/zookeeper/data" "$PROJECT_ROOT/data/kafka/logs"

# --- Step 6: Fix log dirs ---
echo "📁 Creating log directories..."
mkdir -p "$PROJECT_ROOT/logs/services/{scanner,data_processor,model_engine,notifier,storage,explainer}/ec2"

# --- Step 7: Done! ---
echo "✅ Restructure complete!"
echo ""
echo "Now run:"
echo "cd modules/scanner && sudo docker build -t merope-scanner ."
echo "cd ../data_processor && sudo docker build -t merope-data-processor ."
echo "cd ../model_engine && sudo docker build -t merope-model-engine ."
echo ""
echo "Then start services with deploy.sh or manually"