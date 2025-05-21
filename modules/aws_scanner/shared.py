import logging
import os
from datetime import datetime
import json
from logging.handlers import RotatingFileHandler
from botocore.exceptions import ClientError, NoRegionError
import time

def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    log_path = "/logs/merope/scanner.log"
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=2)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    return logger

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