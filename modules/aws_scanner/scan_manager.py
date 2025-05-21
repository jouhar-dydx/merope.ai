import logging
import os
from botocore.exceptions import ClientError
import time

logger = logging.getLogger("ScanManager")

def setup_logger():
    log_dir = "/logs/merope"
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.FileHandler(os.path.join(log_dir, "scanner.log"))
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())

setup_logger()

def get_active_regions(session):
    try:
        ec2_client = session.client('ec2', region_name='us-east-1')
        response = ec2_client.describe_regions()
        return [r['RegionName'] for r in response['Regions']]
    except Exception as e:
        logger.warning(f" Could not fetch active regions: {e}")
        return ['us-east-1']