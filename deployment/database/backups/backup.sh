#!/bin/bash
# ============================================================================
# ESAB Recommender V2 - Database Backup Script
# Backs up Neo4j, PostgreSQL, and Redis databases
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}ESAB Recommender V2 - Database Backup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ==========================
# Configuration
# ==========================

# Backup directory
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_DIR="$BACKUP_ROOT/$TIMESTAMP"

# Database configuration (from environment or defaults)
NEO4J_HOST="${NEO4J_HOST:-localhost}"
NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-esab_neo4j_password}"

POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-pconfig}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-esab_postgres_password}"

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-esab_redis_password}"

# Retention settings (days)
RETENTION_DAYS="${RETENTION_DAYS:-7}"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${YELLOW}Backup Configuration:${NC}"
echo "  Backup Directory: $BACKUP_DIR"
echo "  Timestamp: $TIMESTAMP"
echo "  Retention: $RETENTION_DAYS days"
echo ""

# ==========================
# Backup Neo4j
# ==========================

echo -e "${YELLOW}Backing up Neo4j...${NC}"

if command -v neo4j-admin &> /dev/null; then
    # Using neo4j-admin (preferred method)
    echo "  Using neo4j-admin dump..."
    neo4j-admin dump \
        --database=neo4j \
        --to="$BACKUP_DIR/neo4j-dump.tar" \
        2>&1 | tee "$BACKUP_DIR/neo4j-backup.log"

    echo -e "${GREEN}✓ Neo4j backup complete (neo4j-admin)${NC}"

elif command -v cypher-shell &> /dev/null; then
    # Export to Cypher statements (alternative method)
    echo "  Using cypher-shell export..."
    cypher-shell -u "$NEO4J_USERNAME" -p "$NEO4J_PASSWORD" \
        "CALL apoc.export.cypher.all('$BACKUP_DIR/neo4j-export.cypher', {format: 'cypher-shell'})" \
        2>&1 | tee "$BACKUP_DIR/neo4j-backup.log"

    echo -e "${GREEN}✓ Neo4j backup complete (cypher export)${NC}"

elif [ -d "/var/lib/neo4j/data" ]; then
    # Fallback: Copy data directory
    echo "  Copying Neo4j data directory..."
    cp -r /var/lib/neo4j/data "$BACKUP_DIR/neo4j-data"
    echo -e "${GREEN}✓ Neo4j backup complete (data directory copy)${NC}"

else
    echo -e "${RED}✗ Neo4j backup failed - no backup method available${NC}"
    echo -e "${YELLOW}  Install neo4j-admin or cypher-shell, or provide data directory path${NC}"
fi

# ==========================
# Backup PostgreSQL
# ==========================

echo ""
echo -e "${YELLOW}Backing up PostgreSQL...${NC}"

if command -v pg_dump &> /dev/null; then
    # Set password for pg_dump
    export PGPASSWORD="$POSTGRES_PASSWORD"

    # Full database dump
    echo "  Dumping database: $POSTGRES_DB..."
    pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -F c -b -v -f "$BACKUP_DIR/postgres-$POSTGRES_DB.dump" \
        "$POSTGRES_DB" \
        2>&1 | tee "$BACKUP_DIR/postgres-backup.log"

    # Also create a plain SQL backup for easy inspection
    pg_dump -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -F p -f "$BACKUP_DIR/postgres-$POSTGRES_DB.sql" \
        "$POSTGRES_DB" \
        2>> "$BACKUP_DIR/postgres-backup.log"

    # Unset password
    unset PGPASSWORD

    echo -e "${GREEN}✓ PostgreSQL backup complete${NC}"

else
    echo -e "${RED}✗ PostgreSQL backup failed - pg_dump not found${NC}"
    echo -e "${YELLOW}  Install postgresql-client to enable backups${NC}"
fi

# ==========================
# Backup Redis
# ==========================

echo ""
echo -e "${YELLOW}Backing up Redis...${NC}"

if command -v redis-cli &> /dev/null; then
    # Trigger Redis SAVE
    echo "  Triggering Redis SAVE..."
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
        SAVE 2>&1 | tee "$BACKUP_DIR/redis-backup.log"

    # Copy RDB file if accessible
    if [ -f "/var/lib/redis/dump.rdb" ]; then
        cp /var/lib/redis/dump.rdb "$BACKUP_DIR/redis-dump.rdb"
        echo -e "${GREEN}✓ Redis backup complete (RDB copied)${NC}"
    elif [ -f "/data/dump.rdb" ]; then
        cp /data/dump.rdb "$BACKUP_DIR/redis-dump.rdb"
        echo -e "${GREEN}✓ Redis backup complete (RDB copied)${NC}"
    else
        echo -e "${YELLOW}⚠ Redis SAVE triggered, but RDB file not accessible${NC}"
        echo -e "${YELLOW}  Copy dump.rdb manually from Redis data directory${NC}"
    fi

    # Export all keys (alternative method)
    echo "  Exporting Redis keys..."
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
        --rdb "$BACKUP_DIR/redis-export.rdb" \
        2>> "$BACKUP_DIR/redis-backup.log" || true

else
    echo -e "${RED}✗ Redis backup failed - redis-cli not found${NC}"
    echo -e "${YELLOW}  Install redis-tools to enable backups${NC}"
fi

# ==========================
# Create Metadata File
# ==========================

echo ""
echo -e "${YELLOW}Creating backup metadata...${NC}"

cat > "$BACKUP_DIR/backup-metadata.json" << EOF
{
  "timestamp": "$TIMESTAMP",
  "date": "$(date -Iseconds)",
  "databases": {
    "neo4j": {
      "host": "$NEO4J_HOST",
      "backed_up": $([ -f "$BACKUP_DIR/neo4j-dump.tar" ] && echo "true" || echo "false")
    },
    "postgresql": {
      "host": "$POSTGRES_HOST",
      "database": "$POSTGRES_DB",
      "backed_up": $([ -f "$BACKUP_DIR/postgres-$POSTGRES_DB.dump" ] && echo "true" || echo "false")
    },
    "redis": {
      "host": "$REDIS_HOST",
      "port": $REDIS_PORT,
      "backed_up": $([ -f "$BACKUP_DIR/redis-dump.rdb" ] && echo "true" || echo "false")
    }
  },
  "retention_days": $RETENTION_DAYS
}
EOF

echo -e "${GREEN}✓ Metadata file created${NC}"

# ==========================
# Compress Backup
# ==========================

echo ""
echo -e "${YELLOW}Compressing backup...${NC}"

cd "$BACKUP_ROOT"
tar -czf "$TIMESTAMP.tar.gz" "$TIMESTAMP/" 2>&1 | tee "$TIMESTAMP/compression.log"

BACKUP_SIZE=$(du -sh "$TIMESTAMP.tar.gz" | cut -f1)
echo -e "${GREEN}✓ Backup compressed: $TIMESTAMP.tar.gz ($BACKUP_SIZE)${NC}"

# ==========================
# Clean Old Backups
# ==========================

echo ""
echo -e "${YELLOW}Cleaning old backups (older than $RETENTION_DAYS days)...${NC}"

find "$BACKUP_ROOT" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -exec rm -f {} \;
find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +$RETENTION_DAYS ! -name "." -exec rm -rf {} \;

REMAINING_BACKUPS=$(find "$BACKUP_ROOT" -name "*.tar.gz" -type f | wc -l)
echo -e "${GREEN}✓ Cleanup complete. Remaining backups: $REMAINING_BACKUPS${NC}"

# ==========================
# Summary
# ==========================

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}Backup Summary${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "  Backup Location: ${GREEN}$BACKUP_DIR${NC}"
echo -e "  Compressed Archive: ${GREEN}$TIMESTAMP.tar.gz${NC}"
echo -e "  Backup Size: ${GREEN}$BACKUP_SIZE${NC}"
echo ""

# List backup contents
echo -e "${YELLOW}Backup Contents:${NC}"
ls -lh "$BACKUP_DIR" | tail -n +2 | awk '{printf "  %-40s %s\n", $9, $5}'

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Backup Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "To restore this backup, run:"
echo -e "  ${BLUE}./restore.sh $TIMESTAMP${NC}"
echo ""
