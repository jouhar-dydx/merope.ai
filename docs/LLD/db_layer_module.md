
---

##  6. `db_layer_module.md`

```markdown
#  DB Layer Module – Low-Level Design (LLD)

##  Purpose
To store scan metadata in PostgreSQL, embeddings in Weaviate, and frequently accessed data in Redis.

##  Components
- PostgreSQL connector
- Weaviate connector
- Redis cache
- SQLAlchemy ORM
- Backup system
- Kill switch flag

##  Data Flow
1. Receive processed scan data
2. Insert metadata into PostgreSQL
3. Store embedding in Weaviate
4. Cache query results in Redis
5. Backup daily

##  Input Format
Processed scan result with metadata and embedding

##  Output Format
Persisted records in DBs

##  Features
- Structured relational schema
- Vector embedding storage
- Query caching
- Daily backups
- Manual kill switch

##  Error Handling
- Retry failed inserts
- Graceful degradation if DB is unreachable
- Alert on backup failure

##  Future Enhancements
- Full-text search
- Time-series partitioning
- Multi-region replication