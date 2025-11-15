# Database Setup and Management

This directory contains database initialization scripts, migrations, and backup/restore procedures for the ESAB Recommender V2 application.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Database Architecture](#database-architecture)
- [Initialization](#initialization)
- [Migrations](#migrations)
- [Backup & Restore](#backup--restore)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Overview

ESAB Recommender V2 uses a **multi-database architecture** with three specialized databases:

| Database | Purpose | Technology | Port |
|----------|---------|------------|------|
| **Neo4j** | Product catalog with compatibility relationships | Graph database | 7474 (HTTP), 7687 (Bolt) |
| **PostgreSQL** | Session archival and analytics | Relational database | 5432 |
| **Redis** | Active session caching with TTL | In-memory key-value store | 6379 |

**Data Flow**:
```
User Session → Redis (hot storage, 1 hour TTL)
                 ↓
            PostgreSQL (archival, long-term analytics)

Product Queries → Neo4j (graph relationships, compatibility)
```

---

## Quick Start

### Option 1: Docker Compose (Recommended for Development)

```bash
# Start all databases with application
cd deployment/docker
docker-compose up -d

# Databases will be initialized automatically from init/ scripts
# Access points:
# - Neo4j Browser: http://localhost:7474 (neo4j/esab_neo4j_password)
# - PostgreSQL: localhost:5432 (postgres/esab_postgres_password)
# - Redis: localhost:6379 (esab_redis_password)
# - RedisInsight: http://localhost:8001
```

### Option 2: Manual Setup (Production)

```bash
# 1. Ensure databases are running
sudo systemctl start neo4j
sudo systemctl start postgresql
sudo systemctl start redis

# 2. Run initialization scripts
cd deployment/database/init

# Initialize Neo4j
cypher-shell -u neo4j -p your_password -f neo4j-init.cypher

# Initialize PostgreSQL
psql -U postgres -d pconfig -f postgres-init.sql

# Initialize Redis
chmod +x redis-init.sh
./redis-init.sh
```

---

## Database Architecture

### Neo4j - Product Catalog Graph

**Purpose**: Store product information with compatibility relationships

**Schema**:
```
Nodes:
  - PowerSource (GIN, name, process, current_output, material, ...)
  - Feeder (GIN, name, cooling_type, ...)
  - Cooler (GIN, name, cooling_capacity, ...)
  - Interconnector (GIN, name, cable_length, ...)
  - Torch (GIN, name, amperage, cooling, ...)
  - Accessory (GIN, name, category, ...)

Relationships:
  - COMPATIBLE_WITH (directional, from component to PowerSource)
```

**Example Query**:
```cypher
// Find all feeders compatible with a specific power source
MATCH (ps:PowerSource {gin: '0446200880'})
MATCH (feeder:Feeder)-[:COMPATIBLE_WITH]->(ps)
RETURN feeder
```

**Key Features**:
- Unique GIN (Global Item Number) constraints for all product types
- Full-text search index on product names
- Property indexes for common search fields (process, current, amperage)
- Relationship index for fast compatibility lookups

**File**: `init/neo4j-init.cypher`

### PostgreSQL - Session Archival

**Purpose**: Long-term storage of completed sessions for analytics

**Schema**:
```sql
Table: archived_sessions
  - id (SERIAL PRIMARY KEY)
  - session_id (VARCHAR UNIQUE)
  - user_id (VARCHAR)
  - created_at, archived_at, last_activity_at (TIMESTAMP)
  - current_state, language, status (VARCHAR)
  - conversation_history (JSONB)
  - master_parameters (JSONB)
  - response_json (JSONB)
  - agent_logs (JSONB)
  - finalized (BOOLEAN)
  - message_count, product_selections_count, session_duration_seconds (INTEGER)
```

**Views**:
- `session_summary_stats` - Aggregate statistics across all sessions
- `user_session_history` - Per-user session analytics

**Triggers**:
- `trigger_calculate_session_duration` - Auto-calculates session duration on insert/update

**Example Queries**:
```sql
-- Get all sessions for a user
SELECT * FROM archived_sessions WHERE user_id = 'user-123';

-- Get summary statistics
SELECT * FROM session_summary_stats;

-- Search conversation history (JSONB query)
SELECT session_id, conversation_history
FROM archived_sessions
WHERE conversation_history @> '{"messages": [{"role": "user"}]}';
```

**File**: `init/postgres-init.sql`

### Redis - Session Caching

**Purpose**: Fast in-memory storage for active sessions

**Key Namespaces**:
```
session:{session_id}          - Full session data (JSONB)
user:{user_id}:sessions        - SET of session IDs for multi-session tracking
session:{session_id}:ttl       - Session TTL timestamp
cache:{cache_key}              - General cache data
lock:{resource_id}             - Distributed locks (if needed)
```

**Configuration**:
- **Max Memory**: 512 MB
- **Eviction Policy**: allkeys-lru (Least Recently Used)
- **Persistence**: AOF (Append-Only File) with everysec sync
- **TTL**: 3600 seconds (1 hour) for sessions
- **Timeout**: 300 seconds for idle connections

**Example Commands**:
```bash
# Get session data
redis-cli GET session:abc-123-def

# Get all sessions for a user
redis-cli SMEMBERS user:user-123:sessions

# Check TTL
redis-cli TTL session:abc-123-def

# Database size
redis-cli DBSIZE
```

**File**: `init/redis-init.sh`

---

## Initialization

### First-Time Setup

**All Databases (Docker Compose)**:
```bash
cd deployment/docker
docker-compose up -d

# Verify initialization
docker-compose logs neo4j | grep "Started"
docker-compose logs postgres | grep "database system is ready"
docker-compose logs redis | grep "Ready to accept connections"
```

**Neo4j Only**:
```bash
cd deployment/database/init

# Via cypher-shell
cypher-shell -u neo4j -p password -f neo4j-init.cypher

# Via Neo4j Browser
# 1. Navigate to http://localhost:7474
# 2. Copy and paste contents of neo4j-init.cypher
# 3. Execute

# Via Docker
docker-compose exec neo4j cypher-shell -u neo4j -p password < neo4j-init.cypher
```

**PostgreSQL Only**:
```bash
cd deployment/database/init

# Via psql
psql -U postgres -d pconfig -f postgres-init.sql

# Via Docker
docker-compose exec postgres psql -U postgres -d pconfig < postgres-init.sql

# Verify setup
psql -U postgres -d pconfig -c "\d archived_sessions"
psql -U postgres -d pconfig -c "SELECT * FROM session_summary_stats;"
```

**Redis Only**:
```bash
cd deployment/database/init

# Make script executable
chmod +x redis-init.sh

# Run initialization
./redis-init.sh

# Or set environment variables
REDIS_HOST=localhost REDIS_PORT=6379 REDIS_PASSWORD=yourpass ./redis-init.sh

# Verify setup
redis-cli INFO server
redis-cli INFO memory
```

### Environment Variables

**Neo4j**:
- `NEO4J_URI` - Connection URI (e.g., `bolt://localhost:7687` or `neo4j://localhost:7687`)
- `NEO4J_USERNAME` - Username (default: neo4j)
- `NEO4J_PASSWORD` - Password

**PostgreSQL**:
- `POSTGRES_HOST` - Host (default: localhost)
- `POSTGRES_PORT` - Port (default: 5432)
- `POSTGRES_DB` - Database name (default: pconfig)
- `POSTGRES_USER` - Username (default: postgres)
- `POSTGRES_PASSWORD` - Password

**Redis**:
- `REDIS_HOST` - Host (default: localhost)
- `REDIS_PORT` - Port (default: 6379)
- `REDIS_PASSWORD` - Password
- `REDIS_DB` - Database number (default: 0)

---

## Migrations

### Strategy

**Neo4j**: Cypher-based schema migrations
**PostgreSQL**: Versioned SQL migrations with up/down scripts
**Redis**: Schema-less, document configuration changes only

See [migrations/README.md](migrations/README.md) for detailed migration procedures.

### Quick Reference

**Neo4j Migration**:
```bash
cypher-shell -u neo4j -p password -f migrations/2025-01-15-001-description.cypher
```

**PostgreSQL Migration**:
```bash
# Apply
psql -U postgres -d pconfig -f migrations/V001-description-up.sql

# Rollback
psql -U postgres -d pconfig -f migrations/V001-description-down.sql
```

**Migration Tracking**:
- Current Neo4j schema: v1.0.0
- Current PostgreSQL schema: v1.0.0
- Current Redis version: v1.0.0

---

## Backup & Restore

### Automated Backup

**Full Backup (All Databases)**:
```bash
cd deployment/database/backups

# Run backup script
./backup.sh

# Output: backups/YYYYMMDD_HHMMSS.tar.gz
# Includes: Neo4j dump, PostgreSQL dump, Redis RDB
```

**Backup Features**:
- Neo4j: neo4j-admin dump (preferred) or Cypher export
- PostgreSQL: pg_dump in both custom and plain SQL formats
- Redis: RDB file copy after SAVE command
- Compression: tar.gz archive
- Retention: 7 days (configurable via RETENTION_DAYS)
- Metadata: JSON file with backup info

**Custom Retention**:
```bash
RETENTION_DAYS=30 ./backup.sh
```

### Restore from Backup

**Full Restore**:
```bash
cd deployment/database/backups

# List available backups
./restore.sh

# Restore specific backup
./restore.sh 20250115_143022

# WARNING: This will OVERWRITE all current data!
# Script will prompt for confirmation
```

**Restore Process**:
1. Interactive confirmation prompt
2. Extract backup archive
3. Stop services (if using Docker)
4. Restore Neo4j (via neo4j-admin load or cypher import)
5. Restore PostgreSQL (dropdb → createdb → pg_restore)
6. Restore Redis (copy RDB file)
7. Start services
8. Verify restoration (node count, row count, key count)

**Manual Backup**:
```bash
# Neo4j
neo4j-admin dump --database=neo4j --to=/path/to/backup.tar

# PostgreSQL
pg_dump -U postgres -d pconfig -F c -f /path/to/backup.dump

# Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb /path/to/backup.rdb
```

See [backups/backup.sh](backups/backup.sh) and [backups/restore.sh](backups/restore.sh) for full documentation.

---

## Monitoring

### Health Checks

**Neo4j**:
```bash
# Via cypher-shell
cypher-shell -u neo4j -p password "RETURN 1;"

# Via HTTP
curl http://localhost:7474/

# Check node count
cypher-shell -u neo4j -p password "MATCH (n) RETURN count(n);"
```

**PostgreSQL**:
```bash
# Connection test
psql -U postgres -d pconfig -c "SELECT 1;"

# Check table size
psql -U postgres -d pconfig -c "
  SELECT pg_size_pretty(pg_total_relation_size('archived_sessions'));
"

# Check row count
psql -U postgres -d pconfig -c "SELECT COUNT(*) FROM archived_sessions;"
```

**Redis**:
```bash
# Ping test
redis-cli PING

# Database size
redis-cli DBSIZE

# Memory usage
redis-cli INFO memory

# Key count by namespace
redis-cli KEYS "session:*" | wc -l
```

### Application Health Check

The application provides a unified health check endpoint:

```bash
curl http://localhost:8000/health
```

Response includes status for all databases:
```json
{
  "status": "healthy",
  "databases": {
    "neo4j": "connected",
    "postgresql": "connected",
    "redis": "connected"
  }
}
```

### Metrics to Monitor

**Neo4j**:
- Node count by label
- Relationship count
- Query performance (slow query log)
- Heap memory usage
- Page cache hit ratio

**PostgreSQL**:
- `archived_sessions` table size
- Row count growth rate
- Index usage statistics
- Connection count
- Cache hit ratio

**Redis**:
- Memory usage (should stay under 512MB)
- Eviction count
- Key count
- Hit rate
- Persistence lag (AOF)

---

## Troubleshooting

### Neo4j Issues

**Problem**: "Database 'neo4j' is unavailable"
```bash
# Check if Neo4j is running
sudo systemctl status neo4j

# Check logs
tail -f /var/log/neo4j/neo4j.log

# Restart Neo4j
sudo systemctl restart neo4j
```

**Problem**: Slow queries
```bash
# Enable query logging in neo4j.conf:
# dbms.logs.query.enabled=true
# dbms.logs.query.threshold=1s

# View slow queries
tail -f /var/log/neo4j/query.log

# Check indexes
cypher-shell -u neo4j -p password "SHOW INDEXES;"
```

**Problem**: Connection refused
- Check firewall: `sudo ufw status`
- Verify `dbms.default_listen_address=0.0.0.0` in neo4j.conf
- Check port 7687 is open: `netstat -tlnp | grep 7687`

### PostgreSQL Issues

**Problem**: "FATAL: password authentication failed"
```bash
# Reset password
sudo -u postgres psql
ALTER USER postgres PASSWORD 'new_password';

# Check pg_hba.conf for authentication method
sudo nano /etc/postgresql/*/main/pg_hba.conf
```

**Problem**: Table not found
```bash
# Check database connection
psql -U postgres -d pconfig

# List tables
\dt

# Re-run initialization
psql -U postgres -d pconfig -f init/postgres-init.sql
```

**Problem**: Slow queries
```bash
# Enable slow query logging in postgresql.conf:
# log_min_duration_statement = 1000  # milliseconds

# Check indexes
psql -U postgres -d pconfig -c "\d archived_sessions"

# Analyze query plan
psql -U postgres -d pconfig
EXPLAIN ANALYZE SELECT * FROM archived_sessions WHERE user_id = 'test';
```

### Redis Issues

**Problem**: "MISCONF Redis is configured to save RDB snapshots"
```bash
# Check disk space
df -h

# Disable RDB persistence (use AOF only)
redis-cli CONFIG SET save ""

# Or increase maxmemory
redis-cli CONFIG SET maxmemory 1gb
```

**Problem**: Memory limit reached
```bash
# Check current memory usage
redis-cli INFO memory

# Clear all keys (⚠️ DANGER - development only!)
redis-cli FLUSHALL

# Increase maxmemory
redis-cli CONFIG SET maxmemory 1gb

# Change eviction policy
redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

**Problem**: Connection timeout
```bash
# Check Redis is running
sudo systemctl status redis

# Test connection
redis-cli PING

# Check password
redis-cli -a your_password PING

# Increase timeout
redis-cli CONFIG SET timeout 600
```

### Docker Compose Issues

**Problem**: Database container won't start
```bash
# Check logs
docker-compose logs neo4j
docker-compose logs postgres
docker-compose logs redis

# Remove volumes and restart (⚠️ DATA LOSS!)
docker-compose down -v
docker-compose up -d

# Check disk space
docker system df
```

**Problem**: Data not persisting
```bash
# Check volumes
docker volume ls

# Inspect volume
docker volume inspect esab-neo4j-data

# Verify volume mounts
docker-compose config
```

---

## Performance Tuning

### Neo4j

**neo4j.conf** optimizations:
```conf
# Memory settings (adjust based on available RAM)
dbms.memory.heap.initial_size=2g
dbms.memory.heap.max_size=4g
dbms.memory.pagecache.size=4g

# Query timeout
dbms.transaction.timeout=30s

# Connection pooling
dbms.connector.bolt.thread_pool_min_size=5
dbms.connector.bolt.thread_pool_max_size=400
```

### PostgreSQL

**postgresql.conf** optimizations:
```conf
# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB

# Connection pooling
max_connections = 100

# Checkpoint tuning
checkpoint_completion_target = 0.9
wal_buffers = 16MB
```

### Redis

**redis.conf** optimizations:
```conf
# Memory
maxmemory 512mb
maxmemory-policy allkeys-lru

# Persistence (choose one)
appendonly yes           # AOF (safer, slower)
save 900 1              # RDB (faster, less safe)

# Performance
tcp-backlog 511
timeout 300
```

---

## Security Considerations

### Passwords

**Production**:
- Use strong, randomly generated passwords (20+ characters)
- Store in environment variables, never in code
- Use secret management tools (e.g., HashiCorp Vault, AWS Secrets Manager)

**Docker**:
- Override default passwords in docker-compose.override.yml (gitignored)
- Never commit passwords to version control

### Network Security

**Neo4j**:
- Enable SSL/TLS for Bolt connections
- Restrict access to trusted IPs
- Use `bolt+s://` URI for encrypted connections

**PostgreSQL**:
- Configure SSL in postgresql.conf
- Restrict pg_hba.conf to specific IPs
- Use connection pooling (PgBouncer)

**Redis**:
- Enable requirepass in redis.conf
- Bind to localhost in production (use reverse proxy)
- Disable dangerous commands: `rename-command FLUSHALL ""`

### Backup Security

- Encrypt backup archives before uploading to cloud storage
- Use separate backup credentials with read-only access
- Store backups in geographically separate location
- Test restore procedures regularly

---

## References

- **Neo4j Documentation**: https://neo4j.com/docs/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Redis Documentation**: https://redis.io/documentation

---

## Need Help?

For application-specific database issues:
1. Check application logs: `/home/azureuser/esab_recommender-bh/logs/`
2. Review health check endpoint: `curl http://localhost:8000/health`
3. Check CLAUDE.md for database operation commands
4. Review [migrations/README.md](migrations/README.md) for schema changes
5. See [backups/README.md](backups/) for backup procedures

For deployment issues, see [../docker/README.md](../docker/README.md).
