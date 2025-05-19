# Merope – Autonomous Cloud Engineer

An enterprise-grade autonomous AI platform for continuous scanning, anomaly detection, explanation generation, alerting, and learning from AWS environments.

Built with Docker, Python, RabbitMQ, PostgreSQL, Weaviate, FastAPI, and Jenkins.

Goal: Fully autonomous cloud intelligence at scale.

See `/docs/` for design docs.

Each service runs in a lightweight Docker container (amd64).

CI/CD built with Jenkins pipelines.

Monitoring available via Prometheus + Grafana.

ML/NLP components provide explainable decisions.

RBAC via Google SSO.

Folder structure optimized for modularity and scalability.