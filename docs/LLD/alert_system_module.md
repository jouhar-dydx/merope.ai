
---

##  5. `alert_system_module.md`

```markdown
#  Alert System Module – Low-Level Design (LLD)

##  Purpose
To route alerts by severity, format them for Google Chat, throttle duplicate messages, and retry failed sends.

##  Components
- Severity router
- GChat webhook client
- Alert deduplication cache
- Retry manager
- Alert history logger

##  Data Flow
1. Receive alert from explainer
2. Determine severity (High/Medium/Low)
3. Format alert with scan ID, resource details
4. Deduplicate identical alerts for 15 minutes
5. Send to GChat webhook
6. Log alert history in DB

##  Input Format
```json
{
  "severity": "high",
  "scan_id": "SCAN-...",
  "resource": {
    "type": "security_group",
    "id": "sg-..."
  },
  "explanation": "...",
  "action_suggestion": "..."
}

Features
- Severity routing
- Message throttling
- Retry failed alerts
- Alert history logging
- Markdown formatting
- Error Handling
- Retry up to 3 times
- Log failed alerts
- Graceful degradation if GChat fails
- Future Enhancements
- Multiple notification channels
- Alert escalation policies
- User acknowledgment tracking
