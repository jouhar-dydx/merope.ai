import boto3
import pika
import json
import uuid
import time
import os
import logging
from datetime import datetime
from botocore.exceptions import ClientError

# Set up logger
logger = logging.getLogger("MeropeScanner")
logger.setLevel(logging.INFO)

log_dir = "/logs/merope"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "scanner.log")

file_handler = logging.FileHandler(log_file)
file_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(file_formatter)
logger.addHandler(console_handler)

# Custom JSON Encoder to handle datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        return super().default(obj)

# Generate scan ID
def generate_scan_id():
    return f"SCAN-{uuid.uuid4()}-{int(time.time())}"

# Discover active regions
def get_active_regions(session):
    try:
        ec2_client = session.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        return [region['RegionName'] for region in response['Regions']]
    except Exception as e:
        logger.warning(f" Could not fetch active regions: {e}")
        return ['us-east-1']

# Check orphaned instance
def is_orphaned(instance):
    return len(instance.get('Tags', [])) == 0

# Get associated resources
def get_associated_resources(ec2, instance):
    result = {
        "security_groups": [],
        "volumes": [],
        "network_interfaces": []
    }

    sg_ids = [sg['GroupId'] for sg in instance.get('SecurityGroups', [])]
    if sg_ids:
        try:
            result['security_groups'] = ec2.describe_security_groups(GroupIds=sg_ids).get('SecurityGroups', [])
        except Exception as e:
            logger.error(f" Error fetching security groups: {e}")

    try:
        result['volumes'] = ec2.describe_volumes(Filters=[{
            'Name': 'attachment.instance-id',
            'Values': [instance['InstanceId']]
        }]).get('Volumes', [])
    except Exception as e:
        logger.error(f" Error fetching volumes: {e}")

    try:
        result['network_interfaces'] = ec2.describe_network_interfaces(Filters=[{
            'Name': 'attachment.instance-id',
            'Values': [instance['InstanceId']]
        }]).get('NetworkInterfaces', [])
    except Exception as e:
        logger.error(f" Error fetching ENIs: {e}")

    return result

# Send message to RabbitMQ
def send_to_rabbitmq(message):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host='merope-rabbit'))
        channel = connection.channel()
        channel.queue_declare(queue='scan_queue', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='scan_queue',
            body=json.dumps(message, cls=CustomJSONEncoder),
            properties=pika.BasicProperties(delivery_mode=2),
            mandatory=True
        )
        connection.close()
        logger.info(f"[x] Sent EC2 Instance: {message['resource_id']}")
    except Exception as e:
        logger.error(f" Failed to send to RabbitMQ: {e}")

# Scan EC2 Instances
def scan_ec2_instances(session, scan_id, region):
    logger.info(f" Scanning EC2 in {region}")
    results = []

    try:
        ec2 = session.client('ec2', region_name=region)
        paginator = ec2.get_paginator('describe_instances')
        page_iterator = paginator.paginate()

        for page in page_iterator:
            reservations = page.get('Reservations', [])
            logger.info(f"Found {len(reservations)} instances in {region}")

            for reservation in reservations:
                for instance in reservation.get('Instances', []):
                    if instance['State']['Name'] != 'running':
                        continue

                    item = {
                        "scan_id": scan_id,
                        "region": region,
                        "service": "ec2",
                        "resource_type": "instance",
                        "resource_id": instance['InstanceId'],
                        "data": instance,
                        "orphaned": is_orphaned(instance),
                        "public_ip": 'PublicIpAddress' in instance,
                        "timestamp": time.time(),
                        "missing_metadata": {
                            "tags_missing": len(instance.get('Tags', [])) == 0
                        },
                        "associated_resources": get_associated_resources(ec2, instance)
                    }

                    # Save raw scan to file
                    os.makedirs("/logs/aws_scans/ec2", exist_ok=True)
                    with open(f"/logs/aws_scans/ec2/{instance['InstanceId']}.json", 'w') as f:
                        json.dump(item, f, indent=2, cls=CustomJSONEncoder)

                    # Send to RabbitMQ
                    send_to_rabbitmq(message=item)
                    results.append(item)

        return results

    except ClientError as ce:
        logger.warning(f" EC2 not supported in {region}: {ce}")
        return []

# Main entry point
if __name__ == "__main__":
    logger.info(" Initializing AWS Session...")
    session = boto3.Session()
    scan_id = generate_scan_id()
    regions = get_active_regions(session)

    all_results = []

    for region in regions:
        logger.info(f" Scanning region: {region}")
        results = scan_ec2_instances(session, scan_id, region)
        all_results.extend(results)

    logger.info(f" Sent {len(all_results)} running EC2 instances.")