# 🧠 Merope – High-Level Design (HLD)

##  Overview

Merope is an autonomous AI-powered system that continuously scans AWS infrastructure, detects anomalies, explains findings in plain English, sends intelligent alerts, stores data securely, learns from history, and improves over time — all in real-time, scalable, and secure.

##  Architecture Overview

AWS → Scanner → RabbitMQ → Data Processor → Model Engine → NLP Explainer → Alert System
↘ ↗
DB Layer
↘
→ Dashboard + Monitoring


##  Core Modules

| Module | Responsibility |
|--------|----------------|
| **Scanner** | Scans AWS resources across regions, detects orphaned services |
| **Data Processor** | Normalizes and featurizes raw scan data |
| **Model Engine** | Runs ML models (Random Forest + LSTM) for anomaly detection |
| **NLP Explainer** | Generates human-readable explanations using transformers |
| **Alert System** | Sends alerts to Google Chat based on severity |
| **DB Layer** | Stores metadata in PostgreSQL, embeddings in Weaviate |
| **API Layer** | Exposes RESTful endpoints via FastAPI |

##  Communication

- All modules communicate via **RabbitMQ** message bus.
- Internal communication uses JSON over AMQP.
- External communication uses HTTP REST APIs.

##  Storage

- **PostgreSQL**: Structured scan metadata
- **Weaviate**: Vector embeddings from NLP and ML outputs
- **Redis**: Caching frequent queries

##  Monitoring & Dashboard

- Prometheus metrics exposed by each service
- Grafana dashboard for performance monitoring
- Custom React-based UI for alert tracking, scan status, feedback ratings

##  Security

- RBAC with Google SSO integration
- Secure Docker images using distroless/base images
- Secrets managed via Vault or environment variables

##  Deployment

- Each microservice runs in its own **Docker container**
- Built using **docker buildx** targeting **amd64 only**
- Deployed via **Jenkins multi-pipeline CI/CD**

##  Continuous Learning

- Models retrained every 12 hours using historical scan data
- Feedback loop via engineer ratings
- Reinforcement learning stored in knowledge base

##  Auto-Adjustments

- Anomaly detection thresholds auto-adjusted based on rolling averages
- Alerts throttled to avoid spamming
- Failed scans automatically retried after 300s

##  Kill Switch

- Manual override flag in DB to pause/resume processing
- Separate Jenkins pipeline for model retraining

##  Testing

- Unit tests with pytest
- Integration tests across full pipeline
- Static code analysis and linting

##  Future Enhancements

- Kubernetes support
- Multi-cloud support (Azure, GCP)
- Full UI dashboard with drill-down capabilities
