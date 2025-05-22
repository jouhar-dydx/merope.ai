import boto3
import json
import uuid
import time
import logging
from datetime import datetime
from botocore.exceptions import ClientError

# Set up logger
logger = logging.getLogger("EC2Scanner")
logger.setLevel(logging.INFO)
handler = logging.FileHandler("/logs/merope/scanner.log")
handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(handler)
logger.addHandler(logging.StreamHandler())

# Custom JSON Encoder
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, bytes):
            return obj.decode('utf-8', errors='ignore')
        return super().default(obj)

# Generate unique scan ID
def generate_scan_id():
    return f"SCAN-{uuid.uuid4()}-{int(time.time())}"

# Get active regions
def get_active_regions(session):
    try:
        ec2_client = session.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        return [region['RegionName'] for region in response['Regions']]
    except Exception as e:
        logger.warning(f"⚠️ Could not fetch active regions: {e}")
        return ['us-east-1']

# Check if instance is orphaned
def is_orphaned(instance):
    return len(instance.get('Tags', [])) == 0

# Convert datetimes to string
def convert_datetimes(obj):
    if isinstance(obj, dict):
        return {key: convert_datetimes(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetimes(v) for v in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    else:
        return obj

# Main scanner function
def scan_ec2_instances(session, scan_id, region):
    logger.info(f"🌍 Scanning EC2 instances in {region}")
    results = []

    try:
        ec2 = session.client('ec2', region_name=region)
        paginator = ec2.get_paginator('describe_instances')

        page_iterator = paginator.paginate()
        for page in page_iterator:
            reservations = page.get('Reservations', [])
            logger.info(f"📦 Found {len(reservations)} instances in {region}")

            for reservation in reservations:
                for instance in reservation['Instances']:
                    if instance['State']['Name'] != 'running':
                        continue

                    item = {
                        "scan_id": scan_id,
                        "region": region,
                        "service": "ec2",
                        "resource_type": "instance",
                        "resource_id": instance['InstanceId'],
                        "data": convert_datetimes(instance),
                        "orphaned": is_orphaned(instance),
                        "public_ip": 'PublicIpAddress' in instance,
                        "timestamp": time.time(),
                        "missing_metadata": {"tags_missing": len(instance.get('Tags', [])) == 0}
                    }

                    # Save raw scan
                    os.makedirs("/logs/aws_scans/ec2", exist_ok=True)
                    with open(f"/logs/aws_scans/ec2/{instance['InstanceId']}.json", 'w') as f:
                        json.dump(item, f, cls=CustomJSONEncoder, indent=2)

                    # Send to Kafka
                    send_to_kafka(SCAN_TOPIC, item)
                    results.append(item)

        return results

    except ClientError as ce:
        logger.warning(f"🚫 EC2 not supported in {region}: {ce}")
        return []

if __name__ == "__main__":
    logger.info("🔌 Initializing AWS Session...")
    session = boto3.Session()
    scan_id = generate_scan_id()

    regions = get_active_regions(session)
    logger.info(f"🌐 Active Regions: {regions}")

    all_results = []
    for region in regions:
        logger.info(f"🔄 Scanning {region}")
        results = scan_ec2_instances(session, scan_id, region)
        all_results.extend(results)

    logger.info(f"✅ Sent {len(all_results)} running EC2 instances.")
