#!/bin/bash
# ============================================================================
# ESAB Recommender V2 - Database Restore Script
# Restores Neo4j, PostgreSQL, and Redis from backup
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${RED}============================================${NC}"
echo -e "${RED}ESAB Recommender V2 - Database Restore${NC}"
echo -e "${RED}⚠️  WARNING: This will OVERWRITE databases!${NC}"
echo -e "${RED}============================================${NC}"
echo ""

# ==========================
# Configuration
# ==========================

# Backup directory
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"

# Check if backup timestamp provided
if [ -z "$1" ]; then
    echo -e "${YELLOW}Available backups:${NC}"
    ls -1 "$BACKUP_ROOT"/*.tar.gz 2>/dev/null | xargs -n 1 basename | sed 's/.tar.gz//' || echo "  No backups found"
    echo ""
    echo -e "${RED}Usage: $0 <backup-timestamp>${NC}"
    echo -e "${RED}Example: $0 20250115_143022${NC}"
    exit 1
fi

BACKUP_TIMESTAMP="$1"
BACKUP_ARCHIVE="$BACKUP_ROOT/$BACKUP_TIMESTAMP.tar.gz"
BACKUP_DIR="$BACKUP_ROOT/$BACKUP_TIMESTAMP"

# Verify backup exists
if [ ! -f "$BACKUP_ARCHIVE" ]; then
    echo -e "${RED}✗ Backup not found: $BACKUP_ARCHIVE${NC}"
    exit 1
fi

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

echo -e "${YELLOW}Restore Configuration:${NC}"
echo "  Backup Archive: $BACKUP_ARCHIVE"
echo "  Restore Timestamp: $BACKUP_TIMESTAMP"
echo ""

# ==========================
# Confirmation
# ==========================

echo -e "${RED}⚠️  THIS WILL DELETE ALL CURRENT DATA!${NC}"
echo -e "${RED}⚠️  Make sure you have a recent backup before proceeding!${NC}"
echo ""
read -p "Are you sure you want to restore from $BACKUP_TIMESTAMP? (yes/NO): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Restore cancelled.${NC}"
    exit 0
fi

echo ""

# ==========================
# Extract Backup
# ==========================

echo -e "${YELLOW}Extracting backup archive...${NC}"

# Remove old extracted backup if exists
if [ -d "$BACKUP_DIR" ]; then
    rm -rf "$BACKUP_DIR"
fi

# Extract
cd "$BACKUP_ROOT"
tar -xzf "$BACKUP_TIMESTAMP.tar.gz"

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}✗ Failed to extract backup${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Backup extracted${NC}"

# Read metadata
if [ -f "$BACKUP_DIR/backup-metadata.json" ]; then
    echo ""
    echo -e "${YELLOW}Backup Metadata:${NC}"
    cat "$BACKUP_DIR/backup-metadata.json" | grep -E "date|host|database|backed_up" | sed 's/^/  /'
    echo ""
else
    echo -e "${YELLOW}⚠ No metadata file found in backup${NC}"
fi

# ==========================
# Stop Services (if using Docker)
# ==========================

echo -e "${YELLOW}Stopping services...${NC}"

if command -v docker-compose &> /dev/null; then
    if [ -f "docker-compose.yml" ]; then
        docker-compose stop backend neo4j postgres redis || true
        echo -e "${GREEN}✓ Docker services stopped${NC}"
    fi
fi

echo ""

# ==========================
# Restore Neo4j
# ==========================

echo -e "${YELLOW}Restoring Neo4j...${NC}"

if [ -f "$BACKUP_DIR/neo4j-dump.tar" ]; then
    echo "  Restoring from neo4j-admin dump..."

    if command -v neo4j-admin &> /dev/null; then
        # Stop Neo4j if running
        neo4j stop || true
        sleep 2

        # Restore from dump
        neo4j-admin load \
            --database=neo4j \
            --from="$BACKUP_DIR/neo4j-dump.tar" \
            --force \
            2>&1 | tee "$BACKUP_DIR/neo4j-restore.log"

        # Start Neo4j
        neo4j start || true

        echo -e "${GREEN}✓ Neo4j restored from dump${NC}"
    else
        echo -e "${RED}✗ neo4j-admin not found${NC}"
    fi

elif [ -f "$BACKUP_DIR/neo4j-export.cypher" ]; then
    echo "  Restoring from Cypher export..."

    if command -v cypher-shell &> /dev/null; then
        # Clear existing data
        echo "  Clearing existing Neo4j data..."
        cypher-shell -u "$NEO4J_USERNAME" -p "$NEO4J_PASSWORD" \
            "MATCH (n) DETACH DELETE n" 2>&1 | tee "$BACKUP_DIR/neo4j-restore.log"

        # Import from Cypher file
        echo "  Importing from Cypher file..."
        cypher-shell -u "$NEO4J_USERNAME" -p "$NEO4J_PASSWORD" \
            -f "$BACKUP_DIR/neo4j-export.cypher" \
            2>&1 | tee -a "$BACKUP_DIR/neo4j-restore.log"

        echo -e "${GREEN}✓ Neo4j restored from Cypher export${NC}"
    else
        echo -e "${RED}✗ cypher-shell not found${NC}"
    fi

elif [ -d "$BACKUP_DIR/neo4j-data" ]; then
    echo "  Restoring from data directory copy..."
    # This requires stopping Neo4j and replacing data directory
    echo -e "${YELLOW}⚠ Manual restore required:${NC}"
    echo -e "${YELLOW}  1. Stop Neo4j${NC}"
    echo -e "${YELLOW}  2. Copy $BACKUP_DIR/neo4j-data to /var/lib/neo4j/data${NC}"
    echo -e "${YELLOW}  3. Start Neo4j${NC}"

else
    echo -e "${YELLOW}⚠ No Neo4j backup found in archive${NC}"
fi

# ==========================
# Restore PostgreSQL
# ==========================

echo ""
echo -e "${YELLOW}Restoring PostgreSQL...${NC}"

if [ -f "$BACKUP_DIR/postgres-$POSTGRES_DB.dump" ]; then
    echo "  Restoring database: $POSTGRES_DB..."

    if command -v pg_restore &> /dev/null; then
        # Set password
        export PGPASSWORD="$POSTGRES_PASSWORD"

        # Drop and recreate database (⚠️ destructive!)
        echo "  Dropping existing database..."
        dropdb -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            --if-exists "$POSTGRES_DB" 2>&1 | tee "$BACKUP_DIR/postgres-restore.log"

        echo "  Creating fresh database..."
        createdb -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            "$POSTGRES_DB" 2>&1 | tee -a "$BACKUP_DIR/postgres-restore.log"

        # Restore from dump
        echo "  Restoring from dump..."
        pg_restore -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" -v \
            "$BACKUP_DIR/postgres-$POSTGRES_DB.dump" \
            2>&1 | tee -a "$BACKUP_DIR/postgres-restore.log"

        # Unset password
        unset PGPASSWORD

        echo -e "${GREEN}✓ PostgreSQL restored${NC}"
    else
        echo -e "${RED}✗ pg_restore not found${NC}"
    fi

elif [ -f "$BACKUP_DIR/postgres-$POSTGRES_DB.sql" ]; then
    echo "  Restoring from SQL file..."

    if command -v psql &> /dev/null; then
        export PGPASSWORD="$POSTGRES_PASSWORD"

        # Drop and recreate
        dropdb -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            --if-exists "$POSTGRES_DB" 2>&1 | tee "$BACKUP_DIR/postgres-restore.log"

        createdb -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            "$POSTGRES_DB" 2>&1 | tee -a "$BACKUP_DIR/postgres-restore.log"

        # Restore from SQL
        psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            -f "$BACKUP_DIR/postgres-$POSTGRES_DB.sql" \
            2>&1 | tee -a "$BACKUP_DIR/postgres-restore.log"

        unset PGPASSWORD

        echo -e "${GREEN}✓ PostgreSQL restored from SQL${NC}"
    else
        echo -e "${RED}✗ psql not found${NC}"
    fi

else
    echo -e "${YELLOW}⚠ No PostgreSQL backup found in archive${NC}"
fi

# ==========================
# Restore Redis
# ==========================

echo ""
echo -e "${YELLOW}Restoring Redis...${NC}"

if [ -f "$BACKUP_DIR/redis-dump.rdb" ]; then
    echo "  Restoring from RDB file..."

    # Stop Redis if running
    if command -v redis-cli &> /dev/null; then
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
            SHUTDOWN NOSAVE || true
        sleep 2
    fi

    # Copy RDB file
    if [ -d "/var/lib/redis" ]; then
        cp "$BACKUP_DIR/redis-dump.rdb" /var/lib/redis/dump.rdb
        chown redis:redis /var/lib/redis/dump.rdb || true
    elif [ -d "/data" ]; then
        cp "$BACKUP_DIR/redis-dump.rdb" /data/dump.rdb
    else
        echo -e "${YELLOW}⚠ Redis data directory not found${NC}"
        echo -e "${YELLOW}  Copy $BACKUP_DIR/redis-dump.rdb to your Redis data directory manually${NC}"
    fi

    # Start Redis
    if command -v redis-server &> /dev/null; then
        redis-server --daemonize yes || true
        sleep 2
    fi

    echo -e "${GREEN}✓ Redis restored from RDB${NC}"

elif [ -f "$BACKUP_DIR/redis-export.rdb" ]; then
    echo "  Restoring from export RDB..."
    # Same process as above with redis-export.rdb
    echo -e "${YELLOW}⚠ Use redis-export.rdb similarly to redis-dump.rdb${NC}"

else
    echo -e "${YELLOW}⚠ No Redis backup found in archive${NC}"
fi

# ==========================
# Start Services
# ==========================

echo ""
echo -e "${YELLOW}Starting services...${NC}"

if command -v docker-compose &> /dev/null; then
    if [ -f "docker-compose.yml" ]; then
        docker-compose start neo4j postgres redis
        sleep 5
        docker-compose start backend
        echo -e "${GREEN}✓ Docker services started${NC}"
    fi
fi

# ==========================
# Verify Restore
# ==========================

echo ""
echo -e "${YELLOW}Verifying restore...${NC}"

# Neo4j
if command -v cypher-shell &> /dev/null; then
    NODE_COUNT=$(cypher-shell -u "$NEO4J_USERNAME" -p "$NEO4J_PASSWORD" \
        "MATCH (n) RETURN count(n) AS count" --format plain 2>/dev/null | tail -n 1 | tr -d ' ')
    echo -e "  Neo4j nodes: ${GREEN}$NODE_COUNT${NC}"
fi

# PostgreSQL
if command -v psql &> /dev/null; then
    export PGPASSWORD="$POSTGRES_PASSWORD"
    ROW_COUNT=$(psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" -t -c "SELECT count(*) FROM archived_sessions" 2>/dev/null | tr -d ' ')
    unset PGPASSWORD
    echo -e "  PostgreSQL rows (archived_sessions): ${GREEN}$ROW_COUNT${NC}"
fi

# Redis
if command -v redis-cli &> /dev/null; then
    KEY_COUNT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" \
        DBSIZE 2>/dev/null | tr -d '()')
    echo -e "  Redis keys: ${GREEN}$KEY_COUNT${NC}"
fi

# ==========================
# Summary
# ==========================

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Restore Complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Restored from: ${BLUE}$BACKUP_TIMESTAMP${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Verify application functionality"
echo -e "  2. Check database integrity"
echo -e "  3. Review restore logs in $BACKUP_DIR"
echo ""
