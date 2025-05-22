#!/bin/bash

set -e

# Project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "📁 Creating base directory structure..."
mkdir -p config/kafka data/zookeeper/data data/kafka/logs logs/services/{scanner,processor,model_engine,notifier,storage} logs/services/scanner/ec2

# --- Rename modules if needed ---
echo "🧹 Renaming old module folders..."
mv modules/aws_scanner modules/scanner || true
mv modules/nlp_explainer modules/explainer || true
mv modules/alert_system modules/notifier || true
mv modules/db_layer modules/storage || true

# Ensure new module folders exist
mkdir -p modules/processor modules/model_engine modules/shared modules/explainer modules/storage

# --- Write shared utilities ---
cat > modules/shared/logger.py << 'EOL'
import logging
import os

def get_logger(name, log_file="app.log"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    logger.addHandler(logging.StreamHandler())

    return logger
EOL

cat > modules/shared/kafka_utils.py << 'EOL'
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

cat > modules/shared/message_schema.py << 'EOL'
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

# --- Write config files ---
cat > config/aws_scanner.yaml << EOL
scan_id: "SCAN-{uuid}-{timestamp}"
regions: auto
services:
  - ec2
  - rds
  - lambda
EOL

cat > config/kafka/zookeeper.properties << EOL
dataDir=/bitnami/zookeeper/data
clientPort=2181
maxClientCnxns=0
tickTime=2000
initLimit=5
syncLimit=2
EOL

cat > config/kafka/server.properties << EOL
broker.id=1
listeners=PLAINTEXT://:9092
advertised.listeners=PLAINTEXT://kafka:9092
zookeeper.connect=zookeeper:2181
log.dirs=/bitnami/kafka/logs
num.partitions=1
default.replication.factor=1
offsets.topic.replication.factor=1
transaction.state.log.replication.factor=1
transaction.state.log.min.isr=1
message.max.bytes=20971520
replica.fetch.wait.max.ms=10000
EOL

# --- Write Dockerfiles ---

cat > docker/Dockerfile.zookeeper << 'EOL'
FROM zookeeper:3.9.2

LABEL maintainer="Merope Team <dev@merope.com>"
LABEL version="1.0"

# Copy config
COPY ../config/kafka/zookeeper.properties /conf/zoo.cfg

# Create data dir with proper ownership
RUN mkdir -p /bitnami/zookeeper/data && \
    chown -R zookeeper:zookeeper /bitnami/zookeeper/data

# Set env vars
ENV ZOOKEEPER_CLIENT_PORT=2181
ENV ZOOKEEPER_DATA_DIR=/bitnami/zookeeper/data
EOL

cat > docker/Dockerfile.kafka << 'EOL'
FROM ubuntu/kafka:latest

LABEL maintainer="Merope Team <dev@merope.com>"
LABEL version="1.0"

# Copy custom Kafka properties
COPY ../config/kafka/server.properties /writable/config/server.properties

# Create log dir with proper ownership
RUN mkdir -p /bitnami/kafka/logs && \
    chown -R 1001:1001 /bitnami/kafka/logs

# Set environment variables
ENV KAFKA_CFG_PROCESS_ROLES="broker"
ENV KAFKA_CFG_CONTROLLER_LISTENER_NAMES="CONTROLLER"
ENV KAFKA_CFG_LISTENERS="PLAINTEXT://:9092"
ENV KAFKA_CFG_ADVERTISED_LISTENERS="PLAINTEXT://kafka:9092"
ENV KAFKA_CFG_ZOOKEEPER_CONNECT="zookeeper:2181"
ENV KAFKA_CFG_LOG_DIRS="/bitnami/kafka/logs"
EOL

# --- Go-based EC2 Scanner Dockerfile ---
cat > modules/scanner/Dockerfile.go << 'EOL'
FROM golang:1.21

WORKDIR /app

# Install required tools
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy source code
COPY . .

# Build binary
RUN go mod init merope-scanner && \
    go mod tidy && \
    CGO_ENABLED=0 go build -o /scanner ec2_scanner.go

CMD ["/scanner"]
EOL

# --- Python-based Data Processor Dockerfile ---
cat > modules/processor/Dockerfile << 'EOL'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
EOL

cat > modules/processor/main.py << 'EOL'
from shared.kafka_utils import start_kafka_consumer

def process_message(value):
    print(f"[📥] Raw message: {value}")

start_kafka_consumer("aws_scan_data", process_message)
EOL

cat > modules/processor/requirements.txt << EOL
confluent-kafka>=2.3.0
protobuf>=4.21.12
pandas>=2.2.0
numpy>=1.26.4
EOL

# --- Python-based Model Engine Dockerfile ---
cat > modules/model_engine/Dockerfile << 'EOL'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
EOL

cat > modules/model_engine/main.py << 'EOL'
from shared.kafka_utils import start_kafka_consumer
from sklearn.ensemble import IsolationForest
import numpy as np

def analyze(message):
    scores = IsolationForest(n_estimators=100).score_samples([[len(m.get("Tags", []))] for m in message])
    for i, score in enumerate(scores):
        if score < -0.5:
            print(f"🚩 Anomaly: {message[i]['resource_id']} | Score: {score}")

start_kafka_consumer("processed_data", analyze)
EOL

cat > modules/model_engine/requirements.txt << EOL
scikit-learn>=1.4.0
confluent-kafka>=2.3.0
EOL

# --- Python-based Notifier Dockerfile ---
cat > modules/notifier/Dockerfile << 'EOL'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
EOL

cat > modules/notifier/main.py << 'EOL'
from shared.kafka_utils import start_kafka_consumer

def alert(message):
    print(f"🔔 Alert sent: {message}")

start_kafka_consumer("model_output", alert)
EOL

cat > modules/notifier/requirements.txt << EOL
requests>=2.32.0
confluent-kafka>=2.3.0
EOL

# --- Python-based Storage Layer Dockerfile ---
cat > modules/storage/Dockerfile << 'EOL'
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
EOL

cat > modules/storage/main.py << 'EOL'
from shared.kafka_utils import start_kafka_consumer

def persist_message(message):
    print(f"[💾] Saving to DB: {message}")

start_kafka_consumer("aws_scan_data", persist_message)
EOL

cat > modules/storage/requirements.txt << EOL
psycopg2-binary>=2.9.9
redis>=4.6.0
confluent-kafka>=2.3.0
EOL

# --- Go-based EC2 Scanner Source Code ---
cat > modules/scanner/ec2_scanner.go << 'EOL'
package main

import (
    "context"
    "encoding/json"
    "fmt"
    "log"
    "os"
    "time"

    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/service/ec2"
    "github.com/confluentinc/confluent-kafka-go/v2/kafka"
)

type Instance struct {
    ID               string                 `json:"resource_id"`
    Region           string               `json:"region"`
    Service          string               `json:"service"`
    ResourceType     string               `json:"resource_type"`
    ScanID           string               `json:"scan_id"`
    Data             map[string]interface{} `json:"data"`
    Orphaned         bool                 `json:"orphaned"`
    PublicIP         bool                 `json:"public_ip"`
    MissingMetadata  map[string]bool      `json:"missing_metadata"`
    AssociatedResources map[string]interface{} `json:"associated_resources"`
    Timestamp        int64                `json:"timestamp"`
}

var logger *log.Logger

func init() {
    logFile, _ := os.OpenFile("/logs/merope/scanner.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
    logger = log.New(logFile, "[EC2Scanner] ", log.LstdFlags)
}

func convertInstance(instance *ec2.Instance) map[string]interface{} {
    m := make(map[string]interface{})
    m["InstanceId"] = instance.InstanceId
    m["State"] = instance.State.Name
    m["PublicIpAddress"] = instance.PublicIpAddress
    m["Tags"] = instance.Tags
    return m
}

func isOrphaned(instance map[string]interface{}) bool {
    tags, ok := instance["Tags"].([]interface{})
    return !ok || len(tags) == 0
}

func scanEC2Instances(scanID string) ([]Instance, error) {
    cfg, _ := config.LoadDefaultConfig(context.TODO())
    svc := ec2.NewFromConfig(cfg)

    input := &ec2.DescribeInstancesInput{}
    paginator := ec2.NewDescribeInstancesPaginator(svc, input)

    var results []Instance

    for paginator.HasMorePages() {
        page, err := paginator.NextPage(context.TODO())
        if err != nil {
            log.Printf("🚨 Error fetching page: %v", err)
            continue
        }

        for _, reservation := range page.Reservations {
            for _, instance := range reservation.Instances {
                instanceMap := convertInstance(instance)

                results = append(results, Instance{
                    ID:              *instance.InstanceId,
                    Region:          *svc.Options().Region,
                    Service:         "ec2",
                    ResourceType:    "instance",
                    ScanID:          scanID,
                    Data:            instanceMap,
                    Orphaned:        isOrphaned(instanceMap),
                    PublicIP:        instance.PublicIpAddress != nil,
                    MissingMetadata: map[string]bool{"tags_missing": instance.Tags == nil || len(instance.Tags) == 0},
                    AssociatedResources: map[string]interface{}{
                        "security_groups": instance.SecurityGroups,
                        "vpc_id":        instance.VpcId,
                    },
                    Timestamp: time.Now().Unix(),
                })

                sendToKafka(results[len(results)-1])
                saveToDisk(*instance.InstanceId, results[len(results)-1])
            }
        }
    }

    log.Printf("📦 Found %d running EC2 instances\n", len(results))
    return results, nil
}

func saveToDisk(id string, item Instance) {
    os.MkdirAll("/logs/aws_scans/ec2", os.ModePerm)
    jsonData, _ := json.MarshalIndent(item, "", "  ")
    os.WriteFile(fmt.Sprintf("/logs/aws_scans/ec2/%s.json", id), jsonData, 0644)
}

func sendToKafka(item Instance) {
    p, err := kafka.NewProducer(&kafka.ConfigMap{"bootstrap.servers": "kafka:9092"})
    if err != nil {
        log.Fatalf("❌ Failed to create Kafka producer: %v", err)
    }
    defer p.Close()

    jsonData, _ := json.Marshal(item)
    deliveryChan := make(chan kafka.Event)
    err = p.Produce(&kafka.Message{
        TopicPartition: kafka.TopicPartition{Topic: "aws_scan_data", Partition: kafka.PartitionAny},
        Key:            []byte(item.ID),
        Value:          jsonData,
    }, deliveryChan)

    e := <-deliveryChan
    msg := e.(*kafka.Message)
    if msg.TopicPartition.Error != nil {
        log.Printf("❌ Kafka delivery failed: %v", msg.TopicPartition.Error)
    } else {
        log.Printf("✅ Sent %s | Offset: %v", item.ID, msg.TopicPartition.Offset)
    }
    close(deliveryChan)
}

func getActiveRegions(session *ec2.Client) ([]string, error) {
    output, err := session.DescribeRegions(context.TODO(), &ec2.DescribeRegionsInput{})
    if err != nil {
        return []string{"us-east-1"}, nil
    }

    var regions []string
    for _, r := range output.Regions {
        regions = append(regions, *r.RegionName)
    }
    return regions, nil
}

func main() {
    scanID := fmt.Sprintf("SCAN-%d", time.Now().UnixNano())

    log.Println("🔌 Initializing AWS Session...")
    session := ec2.NewFromConfig(config.LoadDefaultConfig(context.TODO()))

    regions, _ := getActiveRegions(session)
    for _, region := range regions {
        client := ec2.NewFromConfig(config.LoadDefaultConfig(context.TODO(), config.WithRegion(region)))
        fmt.Printf("🌍 Scanning region: %s\n", region)

        scanner := func() ([]Instance, error) {
            return scanEC2Instances(scanID)
        }

        instances, _ := scanner()
        log.Printf("📦 Found %d running EC2 instances in %s\n", len(instances), region)
    }
}
EOL

# --- Build Go Scanner Module ---
cd modules/scanner
go mod init merope-scanner
go mod tidy

cd "$PROJECT_ROOT/docker"
sudo docker build -f Dockerfile.zookeeper -t merope-zookeeper ..
sudo docker build -f Dockerfile.kafka -t merope-kafka ..

cd "$PROJECT_ROOT/modules/scanner"
sudo docker build -f Dockerfile.go -t merope-scanner .

cd "$PROJECT_ROOT/modules/processor"
sudo docker build -f Dockerfile -t merope-data-processor .

cd "$PROJECT_ROOT/modules/model_engine"
sudo docker build -f Dockerfile -t merope-model-engine .

cd "$PROJECT_ROOT/modules/notifier"
sudo docker build -f Dockerfile -t merope-notifier .

cd "$PROJECT_ROOT/modules/storage"
sudo docker build -f Dockerfile -t merope-storage .

# --- Create Docker network ---
echo "🌐 Creating Docker network..."
sudo docker network create merope-net || true

# --- Start services ---
echo "🐋 Starting Zookeeper..."
sudo docker run -d \
  --network merope-net \
  --name merope-zookeeper \
  -v "$PROJECT_ROOT/data/zookeeper/data:/bitnami/zookeeper/data" \
  -p 2181:2181 \
  merope-zookeeper

sleep 5

echo "🐋 Starting Kafka..."
sudo docker run -d \
  --network merope-net \
  --name merope-kafka \
  -v "$PROJECT_ROOT/data/kafka/logs:/bitnami/kafka/logs" \
  -p 9092:9092 \
  merope-kafka

sleep 10

echo "🔍 Starting AWS Scanner..."
sudo docker run -d \
  --network merope-net \
  --name merope-scanner \
  -v ~/.aws:/root/.aws \
  -v "$PROJECT_ROOT/logs/services/scanner:/logs" \
  merope-scanner

sleep 5

echo "🧠 Starting Data Processor..."
sudo docker run -d \
  --network merope-net \
  --name merope-data-processor \
  -v "$PROJECT_ROOT/logs/services/processor:/logs" \
  merope-data-processor

sleep 5

echo "🤖 Starting Model Engine..."
sudo docker run -d \
  --network merope-net \
  --name merope-model-engine \
  -v "$PROJECT_ROOT/logs/services/model_engine:/logs" \
  merope-model-engine

sleep 5

echo "🔔 Starting Notifier..."
sudo docker run -d \
  --network merope-net \
  --name merope-notifier \
  -v "$PROJECT_ROOT/logs/services/notifier:/logs" \
  merope-notifier

sleep 5

echo "💾 Starting Storage Layer..."
sudo docker run -d \
  --network merope-net \
  --name merope-storage \
  -v "$PROJECT_ROOT/logs/services/storage:/logs" \
  merope-storage

# --- Final Output ---
echo "🎉 Merope system deployed successfully!"
echo "📄 Logs saved at:"
echo "  $PROJECT_ROOT/logs/services/"

echo "🐋 Running containers:"
sudo docker ps
