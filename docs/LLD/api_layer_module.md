#  API Layer Module – Low-Level Design (LLD)

##  Purpose
To expose RESTful endpoints for scan status, alert history, feedback ratings, model version, and performance metrics.

##  Components
- FastAPI server
- Pydantic models
- Prometheus metrics exporter
- RBAC middleware
- Swagger UI

##  Data Flow
1. Receive HTTP request
2. Validate auth
3. Process request
4. Return response
5. Export metrics

##  Endpoints
- `/scan/start` – Trigger manual scan
- `/scan/status/<id>` – Get scan status
- `/alert/list` – List alerts
- `/explanation/<id>` – Get explanation
- `/feedback` – Submit rating
- `/model/version` – Get current model
- `/metrics` – Prometheus metrics

## Features
- JWT authentication
- RBAC (via Google SSO)
- Request rate limiting
- Metrics export
- Swagger documentation

## Error Handling
- Standard HTTP status codes
- Graceful timeout handling
- Auth fallback

## Future Enhancements
- Webhooks
- Long-polling for status updates
- GraphQL support