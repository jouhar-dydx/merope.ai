
---

## 2. `data_processor_module.md`

```markdown
#  Data Processor Module – Low-Level Design (LLD)

##  Purpose
To parse raw AWS JSON responses, normalize fields, extract unstructured text, perform feature engineering, filter security-critical data, and store structured output in DB.

##  Components
- JSON parser
- Text extractor (logs/cloudwatch)
- Feature encoder (categorical + numerical)
- Validator
- PostgreSQL writer
- Weaviate vector writer

##  Data Flow
1. Consume messages from RabbitMQ
2. Parse and clean JSON input
3. Extract unstructured text from logs
4. Encode categorical values
5. Scale numerical features
6. Filter critical fields (missing tags, open SGs, unused IAM roles)
7. Store processed data in PostgreSQL + Weaviate

##  Input Format
Same as scanner output format

##  Output Format
Structured + embedded format ready for ML consumption

##  Features
- Null value detection and handling
- Field validation
- Metadata normalization
- Embedding generation
- Batch writes
- Schema versioning

##  Error Handling
- Reject malformed inputs
- Log invalid entries
- Graceful degradation if DB is down
- Alert on high error rates

##  Future Enhancements
- Streaming transformations
- Real-time schema validation
- Auto-detect new field types