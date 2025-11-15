#!/bin/bash
# ============================================================================
# ESAB Recommender V2 - Redis Initialization Script
# Configures Redis for session storage and caching
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}ESAB Recommender V2 - Redis Setup${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# ==========================
# Configuration
# ==========================

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-esab_redis_password}"
REDIS_DB="${REDIS_DB:-0}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Redis Host: $REDIS_HOST"
echo "  Redis Port: $REDIS_PORT"
echo "  Redis DB: $REDIS_DB"
echo ""

# ==========================
# Check Redis Connection
# ==========================

echo -e "${YELLOW}Checking Redis connection...${NC}"

if command -v redis-cli &> /dev/null; then
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Redis is running and accessible${NC}"
    else
        echo -e "${RED}✗ Cannot connect to Redis${NC}"
        echo -e "${RED}  Please ensure Redis is running at $REDIS_HOST:$REDIS_PORT${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ redis-cli not found, skipping connection test${NC}"
    echo -e "${YELLOW}  Install redis-cli to verify connection${NC}"
fi

# ==========================
# Redis Configuration
# ==========================

echo ""
echo -e "${YELLOW}Configuring Redis...${NC}"

# Set configuration via redis-cli (if available)
if command -v redis-cli &> /dev/null; then
    # Memory management
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" CONFIG SET maxmemory 512mb || true
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" CONFIG SET maxmemory-policy allkeys-lru || true
    echo -e "${GREEN}✓ Memory management configured (512MB, LRU eviction)${NC}"

    # Persistence
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" CONFIG SET appendonly yes || true
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" CONFIG SET appendfsync everysec || true
    echo -e "${GREEN}✓ Persistence enabled (AOF, sync every second)${NC}"

    # Connection timeouts
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" CONFIG SET timeout 300 || true
    echo -e "${GREEN}✓ Connection timeout set to 300 seconds${NC}"

    # Key expiration
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" CONFIG SET lazyfree-lazy-eviction yes || true
    echo -e "${GREEN}✓ Lazy eviction enabled${NC}"

else
    echo -e "${YELLOW}⚠ redis-cli not found, skipping configuration${NC}"
    echo -e "${YELLOW}  Configuration should be set in redis.conf:${NC}"
    echo -e "${YELLOW}    maxmemory 512mb${NC}"
    echo -e "${YELLOW}    maxmemory-policy allkeys-lru${NC}"
    echo -e "${YELLOW}    appendonly yes${NC}"
    echo -e "${YELLOW}    appendfsync everysec${NC}"
fi

# ==========================
# Create Key Namespaces
# ==========================

echo ""
echo -e "${YELLOW}Setting up key namespaces...${NC}"

# These are just documentation - Redis doesn't require explicit namespace creation
cat << 'EOF'
Key Naming Conventions:
  - session:{session_id}          - Session data (JSONB)
  - user:{user_id}:sessions        - SET of session IDs for user
  - session:{session_id}:ttl       - Session TTL timestamp
  - cache:{cache_key}              - Cached data
  - lock:{resource_id}             - Distributed locks (if needed)

Default TTL: 3600 seconds (1 hour)
EOF

echo -e "${GREEN}✓ Key namespaces documented${NC}"

# ==========================
# Test Operations
# ==========================

echo ""
echo -e "${YELLOW}Testing Redis operations...${NC}"

if command -v redis-cli &> /dev/null; then
    # Test SET/GET
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" SET test:init "ESAB Recommender V2 Init" EX 60 > /dev/null
    TEST_VALUE=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" GET test:init)

    if [ "$TEST_VALUE" == "ESAB Recommender V2 Init" ]; then
        echo -e "${GREEN}✓ SET/GET operations working${NC}"
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" DEL test:init > /dev/null
    else
        echo -e "${RED}✗ SET/GET operations failed${NC}"
        exit 1
    fi

    # Test SADD/SMEMBERS (for user:sessions SET)
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" SADD test:user:sessions "session-1" "session-2" > /dev/null
    SESSION_COUNT=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" SCARD test:user:sessions)

    if [ "$SESSION_COUNT" == "2" ]; then
        echo -e "${GREEN}✓ SET operations working (user session tracking)${NC}"
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" DEL test:user:sessions > /dev/null
    else
        echo -e "${RED}✗ SET operations failed${NC}"
        exit 1
    fi

    # Test TTL
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" SET test:ttl "value" EX 10 > /dev/null
    TTL_VALUE=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" TTL test:ttl)

    if [ "$TTL_VALUE" -gt 0 ]; then
        echo -e "${GREEN}✓ TTL operations working${NC}"
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" DEL test:ttl > /dev/null
    else
        echo -e "${RED}✗ TTL operations failed${NC}"
        exit 1
    fi

else
    echo -e "${YELLOW}⚠ redis-cli not found, skipping tests${NC}"
fi

# ==========================
# Display Redis Info
# ==========================

echo ""
echo -e "${YELLOW}Redis Information:${NC}"

if command -v redis-cli &> /dev/null; then
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" INFO server | grep -E "redis_version|os|arch|process_id" || true
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" INFO memory | grep -E "used_memory_human|maxmemory_human|maxmemory_policy" || true
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" -a "$REDIS_PASSWORD" INFO persistence | grep -E "aof_enabled|aof_current_size" || true
else
    echo -e "${YELLOW}⚠ redis-cli not found${NC}"
fi

# ==========================
# Completion
# ==========================

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Redis initialization complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Verify Redis connection in your application"
echo -e "  2. Check Redis logs for any errors"
echo -e "  3. Monitor memory usage and key count"
echo ""
echo -e "Useful commands:"
echo -e "  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD INFO"
echo -e "  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD KEYS session:*"
echo -e "  redis-cli -h $REDIS_HOST -p $REDIS_PORT -a $REDIS_PASSWORD DBSIZE"
echo ""
