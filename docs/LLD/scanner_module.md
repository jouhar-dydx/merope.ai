# Scanner Module – Low-Level Design (LLD)

##  Purpose
To scan AWS infrastructure across all active regions, collect metadata of resources, detect orphaned/underutilized services, assign unique scan IDs, and send structured data to RabbitMQ.

##  Components
- AWS SDK (`boto3`)
- Region discovery logic
- Parallel scanner executor
- Scan ID generator (`uuid`)
- RabbitMQ publisher
- Retry mechanism
- Throttling handler

##  Data Flow
1. Discover active AWS regions dynamically.
2. For each region:
   - Scan EC2, RDS, Lambda, IAM roles, Security Groups, etc.
   - Detect orphaned resources using tags, usage metrics, IAM access logs.
   - Assign UUID-based scan ID with timestamp prefix.
3. Send structured JSON message to RabbitMQ queue.
4. Retry failed scans up to 3 times after 300s delay.

##  Polling Interval
- Every **10 minutes**

##  Input Format
- AWS credentials via environment variables or IAM role
- Configurable list of service types to scan

##  Output Format
```json
{
  "scan_id": "SCAN-<UUID>-<TIMESTAMP>",
  "region": "us-east-1",
  "resource_type": "ec2",
  "resource_id": "i-1234567890abcdef0",
  "metadata": { ... },
  "orphaned": true,
  "timestamp": "2025-04-05T14:00:00Z"
}

 Features

- Dynamic region discovery
- Parallel scanning per region
- Orphan detection logic
- Scan retry on failure
- Rate limiting to avoid AWS throttling
- Log full scan context for debugging
- Error Handling
- Catch AWS API exceptions (e.g., rate limit)
- Retry mechanism with exponential backoff
- Log errors to stdout for monitoring
- Graceful shutdown on SIGINT/SIGTERM
- Future Enhancements
- Multi-cloud support (Azure, GCP)
- Custom resource filtering by tag
- Real-time streaming instead of polling