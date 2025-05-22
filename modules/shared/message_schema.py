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
