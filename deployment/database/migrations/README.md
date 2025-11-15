# Database Migrations

This directory contains database migration scripts for schema changes and data migrations.

## Migration Strategy

### Neo4j Migrations

Neo4j uses a schema-less graph model, but we track:
- Constraint changes
- Index changes
- Label/property additions
- Relationship type changes

**Migration Format:**
```
YYYY-MM-DD-NNN-description.cypher
```

Example: `2025-01-15-001-add-product-rating-index.cypher`

**How to Run:**
```bash
# Via cypher-shell
cypher-shell -u neo4j -p password -f migration-file.cypher

# Via Neo4j Browser
# Copy and paste the migration script

# Via Docker
docker-compose exec neo4j cypher-shell -u neo4j -p password < migration-file.cypher
```

###

 PostgreSQL Migrations

PostgreSQL uses structured schema migrations.

**Migration Format:**
```
VNN-description-up.sql    # Apply migration
VNN-description-down.sql  # Rollback migration
```

Example:
- `V001-add-session-tags-up.sql`
- `V001-add-session-tags-down.sql`

**How to Run:**
```bash
# Via psql
psql -U postgres -d pconfig -f V001-add-session-tags-up.sql

# Via Docker
docker-compose exec postgres psql -U postgres -d pconfig < V001-add-session-tags-up.sql

# Rollback
psql -U postgres -d pconfig -f V001-add-session-tags-down.sql
```

### Redis Migrations

Redis is schema-less and typically doesn't require migrations. However, track:
- Key naming convention changes
- Data structure changes
- Configuration changes

Document changes in: `redis-changes.md`

## Migration Best Practices

1. **Always test migrations in development first**
2. **Create rollback scripts for PostgreSQL**
3. **Backup databases before running migrations**
4. **Document breaking changes**
5. **Use transactions where possible**
6. **Version control all migrations**

## Example Migrations

### Neo4j Example: Add Index

**2025-01-15-001-add-product-rating-index.cypher:**
```cypher
// Add rating property index for products
CREATE INDEX product_rating IF NOT EXISTS
FOR (p:PowerSource) ON (p.rating);

CREATE INDEX feeder_rating IF NOT EXISTS
FOR (f:Feeder) ON (f.rating);

// Verify
SHOW INDEXES;
```

### PostgreSQL Example: Add Column

**V001-add-session-tags-up.sql:**
```sql
-- Add tags column to archived_sessions
ALTER TABLE archived_sessions
ADD COLUMN IF NOT EXISTS tags TEXT[];

-- Add index
CREATE INDEX IF NOT EXISTS idx_archived_sessions_tags
ON archived_sessions USING GIN (tags);

-- Add comment
COMMENT ON COLUMN archived_sessions.tags IS 'User-defined tags for session categorization';
```

**V001-add-session-tags-down.sql:**
```sql
-- Rollback: Remove tags column
DROP INDEX IF EXISTS idx_archived_sessions_tags;

ALTER TABLE archived_sessions
DROP COLUMN IF EXISTS tags;
```

## Migration Tracking

### Current Schema Version

- **Neo4j**: v1.0.0 (initial schema from `../init/neo4j-init.cypher`)
- **PostgreSQL**: v1.0.0 (initial schema from `../init/postgres-init.sql`)
- **Redis**: v1.0.0 (key-value store, no schema)

### Migration History

| Version | Date | Database | Description | Status |
|---------|------|----------|-------------|--------|
| v1.0.0 | 2025-01-XX | All | Initial schema | ✅ Applied |

## Future Migrations

Add future migrations here as they're planned:

- [ ] Add product ratings to Neo4j
- [ ] Add session tags to PostgreSQL
- [ ] Add analytics tables to PostgreSQL
- [ ] Add full-text search indexes to Neo4j

## Tools

### Recommended Migration Tools

**PostgreSQL:**
- [Alembic](https://alembic.sqlalchemy.org/) - Python-based migrations (integrates with SQLAlchemy)
- [Flyway](https://flywaydb.org/) - Java-based migrations
- [migrate](https://github.com/golang-migrate/migrate) - Go-based migrations

**Neo4j:**
- [neo4j-migrations](https://github.com/michael-simons/neo4j-migrations) - Java-based Neo4j migrations
- Custom Cypher scripts (current approach)

**Redis:**
- Redis doesn't typically need migration tools
- Use versioned configuration files

## Automated Migrations

To integrate migrations into deployment:

```bash
# Example deployment script
#!/bin/bash

# 1. Backup databases
./backups/backup.sh

# 2. Run PostgreSQL migrations
for migration in migrations/V*.sql; do
    if [ -f "$migration" ]; then
        echo "Running $migration..."
        psql -U postgres -d pconfig -f "$migration"
    fi
done

# 3. Run Neo4j migrations
for migration in migrations/*-*.cypher; do
    if [ -f "$migration" ]; then
        echo "Running $migration..."
        cypher-shell -u neo4j -p password -f "$migration"
    fi
done

# 4. Start application
docker-compose up -d
```

## Rollback Procedure

If a migration fails:

1. **Stop the application immediately**
   ```bash
   docker-compose down
   ```

2. **Restore from backup**
   ```bash
   ./backups/restore.sh <backup-timestamp>
   ```

3. **Run rollback migration** (PostgreSQL only)
   ```bash
   psql -U postgres -d pconfig -f VNN-description-down.sql
   ```

4. **Verify database state**
   ```bash
   psql -U postgres -d pconfig -c "SELECT * FROM archived_sessions LIMIT 1;"
   cypher-shell -u neo4j -p password "MATCH (n) RETURN count(n);"
   ```

5. **Investigate root cause**
6. **Fix migration script**
7. **Test in development**
8. **Retry deployment**

## Questions?

See `../README.md` for general database setup instructions.
