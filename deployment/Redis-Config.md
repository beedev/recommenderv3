# Redis Configuration Guide

Complete guide for Redis setup, configuration, and operations across all deployment environments.

---

## Table of Contents

1. [Quick Start](#quick-start)
   - [Docker Development](#docker-development)
   - [Docker Production](#docker-production)
   - [Linux Systemd Production](#linux-systemd-production)
2. [Configuration Comparison](#configuration-comparison)
3. [Viewing Redis Logs](#viewing-redis-logs)
   - [Docker Environment Logs](#docker-environment-logs)
   - [Linux Systemd Logs](#linux-systemd-logs)
   - [RedisInsight UI](#redisinsight-ui)
4. [Environment Variables](#environment-variables)
   - [Docker Configuration](#docker-configuration)
   - [Linux Configuration](#linux-configuration)
   - [Cloud Redis (Azure/AWS)](#cloud-redis-azureaws)
5. [Security Hardening](#security-hardening)
   - [Development Security](#development-security)
   - [Production Security (Docker)](#production-security-docker)
   - [Production Security (Linux)](#production-security-linux)
6. [Common Operations](#common-operations)
7. [Troubleshooting](#troubleshooting)
8. [Related Documentation](#related-documentation)

---

## Quick Start

### Docker Development

**Overview**: Redis runs as a Docker container with RedisInsight UI for monitoring.

**Configuration** (from `docker-compose.yml`):
- **Container**: `esab-redis`
- **Port**: `6379` (exposed to host)
- **Password**: `esab_redis_password` (default dev password)
- **Memory Limit**: 512MB
- **Persistence**: AOF (appendonly)
- **Eviction Policy**: allkeys-lru
- **Volume**: `esab-redis-data`
- **RedisInsight UI**: `http://localhost:8001`

**Start Redis**:
```bash
cd deployment/docker
docker-compose up -d redis
```

**Verify Redis is running**:
```bash
# Check container status
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli -a esab_redis_password ping
# Expected output: PONG

# Check memory usage
docker-compose exec redis redis-cli -a esab_redis_password INFO memory
```

**Access RedisInsight UI**:
1. Navigate to: `http://localhost:8001`
2. Add database connection:
   - **Host**: `redis` (Docker service name)
   - **Port**: `6379`
   - **Password**: `esab_redis_password`
   - **Database**: `0`

**Common Development Tasks**:
```bash
# Clear all cached data
docker-compose exec redis redis-cli -a esab_redis_password FLUSHALL

# Monitor real-time commands
docker-compose exec redis redis-cli -a esab_redis_password MONITOR

# View all keys with pattern
docker-compose exec redis redis-cli -a esab_redis_password KEYS "session:*"

# Get session data
docker-compose exec redis redis-cli -a esab_redis_password GET "session:your-session-id"

# Check TTL on a key
docker-compose exec redis redis-cli -a esab_redis_password TTL "session:your-session-id"
```

---

### Docker Production

**Overview**: Production Redis with resource limits, backup configuration, and enhanced monitoring.

**Configuration** (from `docker-compose.prod.yml`):
- **Container**: `esab-redis-prod`
- **Port**: `6379` (internal network only)
- **Password**: `${REDIS_PASSWORD}` (environment variable)
- **Memory Limit**: 1GB
- **Resource Limits**: 0.5 CPU, 1.5GB RAM
- **Persistence**: RDB snapshots + AOF
- **RDB Snapshots**: save 900 1, save 300 10, save 60 10000
- **Log Rotation**: 50MB max size, 5 backup files
- **Volume**: `esab-redis-data-prod`

**Start Redis**:
```bash
cd deployment/docker

# Set Redis password in environment or .env file
export REDIS_PASSWORD="your-strong-production-password"

# Start production stack
docker-compose -f docker-compose.prod.yml up -d redis
```

**Verify Redis is running**:
```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps redis

# Test connection
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" ping
# Expected output: PONG

# Check resource usage
docker stats esab-redis-prod --no-stream

# View health check
docker inspect esab-redis-prod --format='{{json .State.Health}}' | python -m json.tool
```

**Backup Redis Data**:
```bash
# Trigger RDB snapshot
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" BGSAVE

# Copy RDB file to host
docker cp esab-redis-prod:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb

# Copy AOF file to host
docker cp esab-redis-prod:/data/appendonly.aof ./redis-aof-backup-$(date +%Y%m%d).aof
```

**Monitoring**:
```bash
# Check memory usage
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" INFO memory

# View connected clients
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" CLIENT LIST

# Check slow log (commands taking > 10ms)
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" SLOWLOG GET 10

# View statistics
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" INFO stats
```

---

### Linux Systemd Production

**Overview**: Redis installed as a system service on Linux VM with RedisInsight in Docker for monitoring.

**Prerequisites**:
- Ubuntu/Debian Linux with `sudo` access
- Docker installed for RedisInsight UI
- UFW or cloud firewall (Azure NSG, AWS Security Groups)

**Installation Steps**:

**1. Install Redis**:
```bash
sudo apt-get update
sudo apt-get install -y redis-server
```

**2. Configure Redis** (`/etc/redis/redis.conf`):
```bash
# Bind to loopback + Docker bridge (secure)
sudo sed -i 's/^#\? *bind .*/bind 127.0.0.1 ::1 172.17.0.1/' /etc/redis/redis.conf

# Set systemd supervision
sudo sed -i 's/^#\?supervised .*/supervised systemd/' /etc/redis/redis.conf

# Set strong password
sudo sed -i '/^requirepass /d' /etc/redis/redis.conf
echo 'requirepass <REDIS_PASSWORD>' | sudo tee -a /etc/redis/redis.conf

# Memory configuration
echo 'maxmemory 1gb' | sudo tee -a /etc/redis/redis.conf
echo 'maxmemory-policy allkeys-lru' | sudo tee -a /etc/redis/redis.conf

# Persistence (cache profile)
echo 'save ""' | sudo tee -a /etc/redis/redis.conf
sudo sed -i 's/^appendonly .*/appendonly no/' /etc/redis/redis.conf

# Allow Docker bridge clients
sudo sed -i 's/^protected-mode .*/protected-mode no/' /etc/redis/redis.conf
```

**3. Start Redis Service**:
```bash
sudo systemctl enable redis-server
sudo systemctl restart redis-server
sudo systemctl status redis-server
```

**4. Verify Installation**:
```bash
# Check Docker bridge IP
ip -4 addr show docker0 | awk '/inet /{print $2}' | cut -d/ -f1
# Expected output: 172.17.0.1

# Verify Redis is listening on all configured interfaces
sudo ss -ltnp | grep 6379
# Expected: 127.0.0.1:6379, ::1:6379, 172.17.0.1:6379

# Test connection via Docker bridge
redis-cli -h 172.17.0.1 -a '<REDIS_PASSWORD>' ping
# Expected output: PONG
```

**5. Create Read-Only ACL User (Optional)**:
```bash
# For RedisInsight with read-only access
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' ACL SETUSER viewer on >'<VIEWER_PASSWORD>' ~* +@read -@write -@admin
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' CONFIG REWRITE
```

**6. Deploy RedisInsight UI**:
```bash
# Create volume
sudo docker volume create redisinsight-data

# Run RedisInsight (bind to localhost by default for security)
sudo docker run -d --name redisinsight \
  -p 127.0.0.1:6380:5540 \
  -v redisinsight-data:/data \
  --restart unless-stopped \
  redis/redisinsight:latest

# Verify RedisInsight health
curl -f http://127.0.0.1:6380/api/health/
# Expected: {"status":"up"}
```

**7. Configure Firewall**:
```bash
# Block Redis port from external access
sudo ufw deny 6379

# Allow SSH (if not already allowed)
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
sudo ufw status
```

**Accessing RedisInsight UI**:

**Option A - SSH Tunnel (Recommended)**:
```bash
# From your local machine (Windows - PuTTY)
"C:\Program Files\PuTTY\plink.exe" -i "path\key.ppk" -N -L 6380:127.0.0.1:6380 azureuser@<VM_IP>

# From your local machine (macOS/Linux/Windows OpenSSH)
ssh -i /path/to/key.pem -N -L 6380:127.0.0.1:6380 azureuser@<VM_IP>

# Open browser to: http://localhost:6380
```

**Option B - Public Access with Firewall** (for temporary admin access):
```bash
# Re-deploy RedisInsight with public binding
sudo docker rm -f redisinsight
sudo docker run -d --name redisinsight \
  -p 0.0.0.0:6380:5540 \
  -v redisinsight-data:/data \
  --restart unless-stopped \
  redis/redisinsight:latest

# Allow ONLY your IP to access RedisInsight
sudo ufw allow from <YOUR_PUBLIC_IP> to any port 6380 proto tcp

# Open browser to: http://<VM_IP>:6380
```

**Connect RedisInsight to Redis** (inside the UI):
- **Host**: `172.17.0.1` (Docker bridge IP)
- **Port**: `6379`
- **Username**: `default` (or `viewer` for read-only)
- **Password**: `<REDIS_PASSWORD>` (or `<VIEWER_PASSWORD>`)
- **Database**: `0`

**Service Management**:
```bash
# Start Redis
sudo systemctl start redis-server

# Stop Redis
sudo systemctl stop redis-server

# Restart Redis
sudo systemctl restart redis-server

# Check status
sudo systemctl status redis-server

# View logs
sudo journalctl -u redis-server -f

# Check configuration
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' CONFIG GET maxmemory
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' CONFIG GET requirepass
```

---

## Configuration Comparison

### Redis Settings: Development vs Production

| Setting | Docker Dev | Docker Prod | Linux Systemd |
|---------|------------|-------------|---------------|
| **Container Name** | `esab-redis` | `esab-redis-prod` | `redis-server` (systemd) |
| **Password** | `esab_redis_password` | `${REDIS_PASSWORD}` | `<REDIS_PASSWORD>` (in redis.conf) |
| **Max Memory** | 512MB | 1GB | 1GB |
| **Eviction Policy** | allkeys-lru | allkeys-lru | allkeys-lru |
| **Persistence** | AOF only | RDB + AOF | Optional (cache profile) |
| **RDB Snapshots** | None | save 900 1, save 300 10, save 60 10000 | Disabled (save "") |
| **AOF** | appendonly yes, everysec | appendonly yes, everysec | Disabled |
| **Bind Address** | 0.0.0.0 (all interfaces) | 0.0.0.0 (internal network) | 127.0.0.1, ::1, 172.17.0.1 |
| **Port** | 6379 (exposed to host) | 6379 (internal only) | 6379 (private IPs only) |
| **Resource Limits** | None | 0.5 CPU, 1.5GB RAM | None (system-managed) |
| **Log Driver** | json-file (default) | json-file (50MB, 5 files) | systemd journal |
| **Health Check** | Every 10s | Every 10s | N/A (systemd monitoring) |
| **Restart Policy** | unless-stopped | always | systemd auto-restart |
| **Protected Mode** | yes | yes | no (bind to private IPs) |
| **Volume** | esab-redis-data | esab-redis-data-prod | /var/lib/redis |

### RedisInsight UI Configuration

| Setting | Docker Dev | Docker Prod | Linux Systemd |
|---------|------------|-------------|---------------|
| **Container Name** | `esab-redisinsight` | `esab-redisinsight-prod` | `redisinsight` |
| **Port** | 8001 | 8001 | 6380 (localhost) or 5540 |
| **Volume** | esab-redisinsight-data | esab-redisinsight-data-prod | redisinsight-data |
| **Resource Limits** | None | 0.5 CPU, 512MB | None |
| **Access** | http://localhost:8001 | http://localhost:8001 | SSH tunnel or public |

---

## Viewing Redis Logs

### Docker Environment Logs

#### Basic Log Commands

```bash
# View logs from all services (including Redis)
docker-compose logs

# View only Redis logs
docker-compose logs redis

# View last 100 lines
docker-compose logs --tail=100 redis

# Follow logs in real-time
docker-compose logs -f redis

# View logs with timestamps
docker-compose logs -f -t redis
```

#### Time-Based Filtering

```bash
# View logs from last 5 minutes
docker-compose logs --since 5m redis

# View logs from last hour
docker-compose logs --since 1h redis

# View logs from last 24 hours
docker-compose logs --since 24h redis

# View logs from specific date/time (ISO8601 format)
docker-compose logs --since 2025-01-11T10:00:00 redis

# View logs between two timestamps
docker-compose logs --since 2025-01-11T10:00:00 --until 2025-01-11T12:00:00 redis
```

#### Log Level Filtering

```bash
# Filter by error messages
docker-compose logs redis | grep -i error

# Filter by warnings
docker-compose logs redis | grep -i warning

# Filter by multiple levels (error OR warning)
docker-compose logs redis | grep --color=always -iE 'error|warning'

# Filter by INFO level
docker-compose logs redis | grep -i info

# Exclude certain patterns
docker-compose logs redis | grep -v "Accepted connection"
```

#### Combined Filtering

```bash
# Errors from last hour
docker-compose logs --since 1h redis | grep -i error

# Warnings from today with timestamps
docker-compose logs --since 00:00:00 -t redis | grep -i warning

# Real-time error monitoring
docker-compose logs -f redis | grep --color=always -i error
```

#### Production Environment

```bash
# Use production docker-compose file
docker-compose -f docker-compose.prod.yml logs redis

# View production Redis logs (container name)
docker logs esab-redis-prod

# Follow production logs
docker logs -f esab-redis-prod

# Export logs to file
docker-compose -f docker-compose.prod.yml logs --since 24h redis > redis-logs-$(date +%Y%m%d).txt
```

#### JSON Log Parsing

```bash
# View structured JSON logs (if json-file driver)
docker-compose logs redis | grep '^{' | python -m json.tool

# Use jq for advanced filtering (install: sudo apt-get install jq)
docker-compose logs redis | grep '^{' | jq 'select(.level == "error")'
docker-compose logs redis | grep '^{' | jq 'select(.timestamp > "2025-01-11T10:00:00")'
```

#### RedisInsight Container Logs

```bash
# View RedisInsight logs
docker-compose logs redisinsight

# Follow RedisInsight logs
docker-compose logs -f redisinsight

# Check RedisInsight health
curl -f http://localhost:8001/api/health/
```

#### Common Use Cases

**Debug connection issues**:
```bash
docker-compose logs redis | grep -i "connection\|auth\|denied"
```

**Monitor performance**:
```bash
docker-compose logs redis | grep -i "slow\|latency\|memory"
```

**Check startup sequence**:
```bash
docker-compose logs --tail=50 redis | grep -i "ready\|listening"
```

**Find specific session operations**:
```bash
docker-compose logs redis | grep "session:abc-123"
```

---

### Linux Systemd Logs

#### Systemd Journal Commands

```bash
# View Redis service logs
sudo journalctl -u redis-server

# Follow logs in real-time
sudo journalctl -u redis-server -f

# View last 100 lines
sudo journalctl -u redis-server -n 100

# View logs with timestamps
sudo journalctl -u redis-server -o short-iso
```

#### Time-Based Filtering

```bash
# Logs from last hour
sudo journalctl -u redis-server --since "1 hour ago"

# Logs from last 24 hours
sudo journalctl -u redis-server --since "1 day ago"

# Logs from specific date
sudo journalctl -u redis-server --since "2025-01-11"

# Logs between two dates
sudo journalctl -u redis-server --since "2025-01-11 10:00:00" --until "2025-01-11 12:00:00"

# Logs since last boot
sudo journalctl -u redis-server -b
```

#### Log Level Filtering

```bash
# Priority filtering (err = error level)
sudo journalctl -u redis-server -p err

# Warning and above
sudo journalctl -u redis-server -p warning

# Info and above
sudo journalctl -u redis-server -p info

# Multiple priorities
sudo journalctl -u redis-server -p warning..err
```

#### Combined Filtering with grep

```bash
# Filter for specific patterns
sudo journalctl -u redis-server | grep -i error
sudo journalctl -u redis-server | grep -i "connection\|auth"
sudo journalctl -u redis-server | grep --color=always -iE 'error|warning'
```

#### Export Systemd Logs

```bash
# Export to file
sudo journalctl -u redis-server --since "1 day ago" > redis-logs-$(date +%Y%m%d).txt

# Export errors only
sudo journalctl -u redis-server -p err --since "1 week ago" > redis-errors.txt

# Export in JSON format
sudo journalctl -u redis-server -o json > redis-logs.json
```

#### RedisInsight Container Logs (on Linux)

```bash
# View RedisInsight container logs
sudo docker logs redisinsight

# Follow logs
sudo docker logs -f redisinsight

# Last 100 lines
sudo docker logs --tail=100 redisinsight

# Check health
curl -f http://127.0.0.1:6380/api/health/
```

#### Redis Log File (if configured)

If Redis is configured to write to a log file (`/var/log/redis/redis-server.log`):

```bash
# View log file
sudo tail -f /var/log/redis/redis-server.log

# Last 100 lines
sudo tail -n 100 /var/log/redis/redis-server.log

# Filter errors
sudo grep -i error /var/log/redis/redis-server.log

# Search for specific pattern
sudo grep "session:" /var/log/redis/redis-server.log
```

#### Common Systemd Use Cases

**Check service status**:
```bash
sudo systemctl status redis-server
```

**View startup errors**:
```bash
sudo journalctl -u redis-server --since "5 minutes ago" -p err
```

**Monitor real-time activity**:
```bash
sudo journalctl -u redis-server -f | grep --color=always -iE 'error|warning|connection'
```

**Verify successful restart**:
```bash
sudo journalctl -u redis-server --since "1 minute ago" | grep "Ready to accept connections"
```

---

### RedisInsight UI

RedisInsight provides a browser-based UI for monitoring and managing Redis.

#### Accessing RedisInsight

**Docker Development**:
- URL: `http://localhost:8001`

**Docker Production**:
- URL: `http://localhost:8001` (if on same machine)
- SSH Tunnel: Forward port 8001

**Linux Systemd**:
- SSH Tunnel: `ssh -L 6380:127.0.0.1:6380 user@server`
- URL: `http://localhost:6380`

#### Features Available in RedisInsight

**1. Browser**:
- View all keys with pattern matching
- Search keys by pattern (e.g., `session:*`, `user:*`)
- View key values (strings, hashes, lists, sets, zsets)
- Edit key values
- Set TTL on keys
- Delete keys

**2. Workbench** (CLI):
- Execute Redis commands
- View command history
- Auto-complete for commands
- Syntax highlighting

**3. Analysis Tools**:
- **Slow Log**: Commands taking longer than threshold
- **Memory Analysis**: Memory usage by key pattern
- **Database Statistics**: Total keys, memory used, hit rate
- **Client List**: Connected clients and their activity

**4. Monitoring**:
- Real-time command monitoring
- Memory usage graphs
- Connected clients
- Operations per second
- Hit/miss ratio

#### Useful RedisInsight Commands

Inside the RedisInsight CLI (Workbench):

```redis
# View all session keys
KEYS session:*

# Get specific session
GET session:your-session-id

# Check TTL on session
TTL session:your-session-id

# View memory usage by pattern
MEMORY USAGE session:your-session-id

# Get server info
INFO memory
INFO stats
INFO clients

# Monitor commands in real-time
MONITOR

# View slow log
SLOWLOG GET 10

# Check connected clients
CLIENT LIST

# View keyspace statistics
INFO keyspace
```

#### Connecting RedisInsight to Redis

**Docker Environment**:
- **Host**: `redis` (Docker service name from within network)
- **Port**: `6379`
- **Password**: `esab_redis_password` (dev) or `${REDIS_PASSWORD}` (prod)
- **Database**: `0`

**Linux Systemd Environment**:
- **Host**: `172.17.0.1` (Docker bridge IP)
- **Port**: `6379`
- **Username**: `default` (or `viewer` for read-only)
- **Password**: `<REDIS_PASSWORD>` from redis.conf
- **Database**: `0`

---

## Environment Variables

### Docker Configuration

#### Development Environment

**File Location**: `src/backend/.env`

```env
# Redis Configuration (Docker Development)
ENABLE_REDIS_CACHING=true
REDIS_HOST=redis                    # Docker service name
REDIS_PORT=6379
REDIS_PASSWORD=esab_redis_password  # Default dev password
REDIS_DB=0

# Session Configuration
CACHE_TTL=3600                      # 1 hour session timeout
CACHE_PREFIX=esabcfg:
```

#### Production Environment

**File Location**: `src/backend/.env`

```env
# Redis Configuration (Docker Production)
ENABLE_REDIS_CACHING=true
REDIS_HOST=redis                    # Docker service name
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}    # Set via environment or .env
REDIS_DB=0

# Session Configuration
CACHE_TTL=3600                      # 1 hour
CACHE_PREFIX=esabcfg:
```

**Set password via environment variable**:
```bash
# In shell
export REDIS_PASSWORD="your-strong-production-password"

# Or in docker-compose command
REDIS_PASSWORD="your-password" docker-compose -f docker-compose.prod.yml up -d
```

---

### Linux Configuration

**File Location**: `src/backend/.env`

```env
# Redis Configuration (Linux Systemd)
ENABLE_REDIS_CACHING=true

# Option 1: Use connection URL (recommended)
REDIS_URL='redis://default:<REDIS_PASSWORD>@127.0.0.1:6379/0'

# Option 2: Use individual parameters (fallback)
REDIS_HOST=127.0.0.1                # Loopback
REDIS_PORT=6379
REDIS_DB=0
REDIS_USERNAME=default
REDIS_PASSWORD=<REDIS_PASSWORD>     # From redis.conf

# Connection Pool Settings
REDIS_POOL_MAX_CONNECTIONS=100
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# Namespacing & TTLs
CACHE_PREFIX=esabcfg:
CACHE_TTL=3600                      # Default session TTL
CACHE_TTL_SHORT=300                 # 5 minutes
CACHE_TTL_LONG=86400                # 24 hours

LOCK_PREFIX=esabcfg:lock:
LOCK_TTL=30                         # Lock timeout

# Health Check
REDIS_HEALTHCHECK_ON_START=true
REDIS_HEALTHCHECK_KEY=esabcfg:health
```

**Test configuration**:
```bash
cd src/backend
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('REDIS_URL'))"
```

---

### Cloud Redis (Azure/AWS)

For managed Redis services (Azure Cache for Redis, AWS ElastiCache), use SSL connections.

**Azure Cache for Redis**:

```env
# Azure Redis Configuration (SSL enabled)
REDIS_URL='rediss://:<PRIMARY_ACCESS_KEY>@<CACHE_NAME>.redis.cache.windows.net:6380/0'

# Or individual parameters
REDIS_HOST=<CACHE_NAME>.redis.cache.windows.net
REDIS_PORT=6380                     # SSL port
REDIS_PASSWORD=<PRIMARY_ACCESS_KEY>
REDIS_DB=0
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

**AWS ElastiCache**:

```env
# AWS ElastiCache (SSL enabled)
REDIS_URL='rediss://:<AUTH_TOKEN>@<CLUSTER_ENDPOINT>:6379/0'

# Or individual parameters
REDIS_HOST=<CLUSTER_ENDPOINT>.cache.amazonaws.com
REDIS_PORT=6379
REDIS_PASSWORD=<AUTH_TOKEN>
REDIS_DB=0
REDIS_SSL=true
```

**Connection URL Format**:
```
redis://[username][:password]@host:port/db      # Non-SSL
rediss://[username][:password]@host:port/db     # SSL (note the extra 's')
```

**Python Connection Example**:
```python
import os
from redis.asyncio import Redis

# Automatically handles SSL based on rediss:// scheme
r = Redis.from_url(
    os.getenv("REDIS_URL"),
    decode_responses=True,
    ssl_cert_reqs="required"  # For SSL connections
)

# Test connection
await r.ping()  # Returns True if successful
```

---

## Security Hardening

### Development Security

**Basic Security for Local Development**:

1. **Change Default Password**:
   - Edit `docker-compose.yml` or set in `.env`
   - Restart containers after change

2. **Don't Expose Publicly**:
   - Keep Redis on port 6379 accessible only to Docker network
   - Don't publish port 6379 to `0.0.0.0` unnecessarily

3. **Use Internal Docker Network**:
   - Services communicate via service names (`redis`)
   - No need for host networking in development

4. **RedisInsight Access**:
   - Bind to `localhost:8001` by default
   - Only accessible from development machine

**Development `docker-compose.yml` already implements**:
```yaml
redis:
  ports:
    - "6379:6379"  # OK for development
  command: redis-server --requirepass esab_redis_password
```

---

### Production Security (Docker)

**Enhanced Security for Docker Production**:

1. **Strong Passwords**:
```bash
# Generate strong password
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set in environment
export REDIS_PASSWORD="your-strong-password-here"
```

2. **Resource Limits** (prevent memory exhaustion):
```yaml
redis:
  deploy:
    resources:
      limits:
        cpus: '0.5'
        memory: 1.5G
```

3. **Network Isolation**:
```yaml
# Don't expose Redis port externally
# Only backend service needs access
redis:
  networks:
    - esab-network  # Internal network only
```

4. **Monitoring and Alerting**:
   - Enable health checks
   - Monitor memory usage
   - Track slow queries
   - Set up log aggregation

5. **Backup Configuration**:
```bash
# Regular backups of RDB and AOF files
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" BGSAVE

# Copy backup files
docker cp esab-redis-prod:/data/dump.rdb ./backups/
docker cp esab-redis-prod:/data/appendonly.aof ./backups/
```

6. **Log Rotation**:
```yaml
redis:
  logging:
    driver: "json-file"
    options:
      max-size: "50m"
      max-file: "5"
```

7. **TLS/SSL** (for production with external clients):
```bash
# Generate certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout redis.key -out redis.crt

# Mount certificates in container
volumes:
  - ./certs:/certs:ro

# Enable TLS
command: |
  redis-server
  --requirepass ${REDIS_PASSWORD}
  --tls-port 6380
  --port 0
  --tls-cert-file /certs/redis.crt
  --tls-key-file /certs/redis.key
```

---

### Production Security (Linux)

**Comprehensive Security for Linux Systemd Deployment**:

1. **Bind to Private IPs Only**:
```bash
# /etc/redis/redis.conf
bind 127.0.0.1 ::1 172.17.0.1
```

2. **Strong Authentication**:
```bash
# Set strong password
requirepass <STRONG_RANDOM_PASSWORD>
```

3. **ACL Users** (Redis 6+):
```bash
# Create read-only user for monitoring tools
redis-cli ACL SETUSER viewer on >'<VIEWER_PASSWORD>' ~* +@read -@write -@admin

# Create application user with limited permissions
redis-cli ACL SETUSER appuser on >'<APP_PASSWORD>' ~esabcfg:* +@all -@dangerous

# Save ACL
redis-cli CONFIG REWRITE
```

4. **Firewall Rules**:
```bash
# Block Redis from external access
sudo ufw deny 6379

# Allow only from specific IPs (if needed)
sudo ufw allow from 10.0.0.0/24 to any port 6379 proto tcp
```

5. **Disable Protected Mode** (when binding to private IPs):
```bash
# /etc/redis/redis.conf
protected-mode no
```

6. **File Permissions**:
```bash
# Secure Redis configuration
sudo chmod 640 /etc/redis/redis.conf
sudo chown redis:redis /etc/redis/redis.conf

# Secure data directory
sudo chmod 750 /var/lib/redis
sudo chown redis:redis /var/lib/redis
```

7. **Disable Dangerous Commands** (optional):
```bash
# /etc/redis/redis.conf
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command CONFIG ""
rename-command SHUTDOWN SHUTDOWN_SECRET_NAME
```

8. **RedisInsight Access Control**:

**Option A - SSH Tunnel (Most Secure)**:
```bash
# No public port exposure
# Bind RedisInsight to localhost only
sudo docker run -d --name redisinsight \
  -p 127.0.0.1:6380:5540 \
  -v redisinsight-data:/data \
  --restart unless-stopped redis/redisinsight:latest

# Access via SSH tunnel
ssh -L 6380:127.0.0.1:6380 user@server
```

**Option B - NGINX with HTTPS + Basic Auth**:
```bash
# Install NGINX
sudo apt-get install -y nginx apache2-utils

# Create basic auth file
sudo htpasswd -c /etc/nginx/.redisinsight_htpasswd admin

# Configure NGINX (see full config in redis-linux-systemd.md)
# Requires SSL certificate (Let's Encrypt)
```

9. **Azure/AWS Cloud Firewall**:
```
Azure NSG Rules:
- DENY: Source=Any, Port=6379 (Redis)
- ALLOW: Source=<Your_IP>, Port=6380 (RedisInsight - optional)
- ALLOW: Source=Any, Port=22 (SSH)

AWS Security Group Rules:
- Inbound: DENY 6379 from 0.0.0.0/0
- Inbound: ALLOW 22 from <Your_IP>
- Inbound: ALLOW 6380 from <Your_IP> (optional)
```

10. **Regular Security Maintenance**:
```bash
# Rotate passwords quarterly
# Update Redis to latest stable version
sudo apt-get update
sudo apt-get install --only-upgrade redis-server

# Review ACL users
redis-cli ACL LIST

# Review slow log for suspicious activity
redis-cli SLOWLOG GET 100

# Check for unauthorized connections
redis-cli CLIENT LIST
```

---

## Common Operations

### Clear All Cached Data

**Docker Development**:
```bash
docker-compose exec redis redis-cli -a esab_redis_password FLUSHALL
```

**Docker Production**:
```bash
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" FLUSHALL
```

**Linux Systemd**:
```bash
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' FLUSHALL
```

### Monitor Real-Time Commands

**Docker**:
```bash
docker-compose exec redis redis-cli -a esab_redis_password MONITOR
```

**Linux**:
```bash
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' MONITOR
```

### Check Memory Usage

**Docker**:
```bash
docker-compose exec redis redis-cli -a esab_redis_password INFO memory
```

**Linux**:
```bash
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' INFO memory
```

### View Slow Queries

**Docker**:
```bash
docker-compose exec redis redis-cli -a esab_redis_password SLOWLOG GET 10
```

**Linux**:
```bash
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' SLOWLOG GET 10
```

### List All Keys (Use with Caution)

**Docker**:
```bash
# Count keys
docker-compose exec redis redis-cli -a esab_redis_password DBSIZE

# List keys with pattern (production use SCAN instead)
docker-compose exec redis redis-cli -a esab_redis_password KEYS "session:*"

# Use SCAN for production (doesn't block)
docker-compose exec redis redis-cli -a esab_redis_password SCAN 0 MATCH "session:*" COUNT 100
```

### Get Key Information

**Docker**:
```bash
# Get key value
docker-compose exec redis redis-cli -a esab_redis_password GET "session:abc-123"

# Get key type
docker-compose exec redis redis-cli -a esab_redis_password TYPE "session:abc-123"

# Get key TTL
docker-compose exec redis redis-cli -a esab_redis_password TTL "session:abc-123"

# Get memory usage
docker-compose exec redis redis-cli -a esab_redis_password MEMORY USAGE "session:abc-123"
```

### Set Key Expiration

**Docker**:
```bash
# Set TTL to 1 hour (3600 seconds)
docker-compose exec redis redis-cli -a esab_redis_password EXPIRE "session:abc-123" 3600

# Remove expiration (make key persistent)
docker-compose exec redis redis-cli -a esab_redis_password PERSIST "session:abc-123"
```

### Backup and Restore

**Docker Backup**:
```bash
# Trigger background save
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" BGSAVE

# Wait for save to complete
docker exec esab-redis-prod redis-cli -a "${REDIS_PASSWORD}" LASTSAVE

# Copy backup file
docker cp esab-redis-prod:/data/dump.rdb ./redis-backup-$(date +%Y%m%d-%H%M%S).rdb
```

**Docker Restore**:
```bash
# Stop Redis container
docker-compose -f docker-compose.prod.yml stop redis

# Copy backup file
docker cp ./redis-backup-20250111-120000.rdb esab-redis-prod:/data/dump.rdb

# Start Redis container
docker-compose -f docker-compose.prod.yml start redis
```

**Linux Backup**:
```bash
# Trigger background save
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' BGSAVE

# Copy RDB file
sudo cp /var/lib/redis/dump.rdb /backup/redis-backup-$(date +%Y%m%d-%H%M%S).rdb
```

**Linux Restore**:
```bash
# Stop Redis service
sudo systemctl stop redis-server

# Restore backup
sudo cp /backup/redis-backup-20250111-120000.rdb /var/lib/redis/dump.rdb
sudo chown redis:redis /var/lib/redis/dump.rdb

# Start Redis service
sudo systemctl start redis-server
```

---

## Troubleshooting

### Connection Errors

#### "Error 111 connecting to localhost:6379" (from Docker container)

**Cause**: Using `localhost` instead of Docker service name.

**Fix for Backend Container**:
```env
# In src/backend/.env
REDIS_HOST=redis  # Docker service name, NOT localhost
```

**Test**:
```bash
# From host machine (works)
redis-cli -h localhost -a esab_redis_password ping

# From container (use service name)
docker-compose exec backend redis-cli -h redis -a esab_redis_password ping
```

---

#### "Could not connect to 127.0.0.1:6379" (from RedisInsight container)

**Cause**: Container trying to reach its own `127.0.0.1`, not the host's Redis.

**Fix**: Use Docker bridge IP `172.17.0.1` for Linux systemd Redis.

**In RedisInsight UI**:
- **Host**: `172.17.0.1` (NOT `127.0.0.1`)
- **Port**: `6379`
- **Password**: `<REDIS_PASSWORD>`

**Verify Docker bridge IP**:
```bash
ip -4 addr show docker0 | awk '/inet /{print $2}' | cut -d/ -f1
```

---

#### "NOAUTH Authentication required"

**Cause**: Password not provided or incorrect.

**Fix for Docker**:
```env
# In src/backend/.env
REDIS_PASSWORD=esab_redis_password  # Must match docker-compose.yml
```

**Fix for Linux**:
```bash
# Check password in redis.conf
sudo grep requirepass /etc/redis/redis.conf

# Update .env to match
REDIS_PASSWORD=<REDIS_PASSWORD>
```

**Test**:
```bash
redis-cli -h 127.0.0.1 -a '<CORRECT_PASSWORD>' ping
```

---

#### "Connection refused" or timeout

**Possible Causes**:
1. Redis not running
2. Firewall blocking port 6379
3. Wrong host/port in configuration

**Diagnosis**:
```bash
# Check if Redis is running (Docker)
docker-compose ps redis

# Check if Redis is running (Linux)
sudo systemctl status redis-server

# Check if port is listening
sudo netstat -tlnp | grep 6379
# or
sudo ss -ltnp | grep 6379

# Test connection
redis-cli -h 127.0.0.1 -a '<PASSWORD>' ping
```

**Fix for Docker**:
```bash
# Start Redis
docker-compose up -d redis
```

**Fix for Linux**:
```bash
# Start Redis service
sudo systemctl start redis-server

# Check for errors
sudo journalctl -u redis-server -n 50
```

---

### Performance Issues

#### Out of Memory Errors

**Symptom**: Redis evicting keys or rejecting writes.

**Diagnosis**:
```bash
# Check memory usage
docker-compose exec redis redis-cli -a esab_redis_password INFO memory

# Check current memory
redis-cli INFO memory | grep used_memory_human

# Check maxmemory setting
redis-cli CONFIG GET maxmemory
```

**Fix 1 - Increase Memory Limit**:

Docker Development (`docker-compose.yml`):
```yaml
redis:
  command: |
    redis-server
    --requirepass esab_redis_password
    --maxmemory 1gb  # Increase from 512mb
```

Docker Production (`docker-compose.prod.yml`):
```yaml
redis:
  command: |
    redis-server
    --requirepass ${REDIS_PASSWORD}
    --maxmemory 2gb  # Increase from 1gb
```

Linux (`/etc/redis/redis.conf`):
```bash
sudo sed -i 's/maxmemory 1gb/maxmemory 2gb/' /etc/redis/redis.conf
sudo systemctl restart redis-server
```

**Fix 2 - Check Eviction Policy**:
```bash
# Verify eviction policy
redis-cli CONFIG GET maxmemory-policy
# Should return: allkeys-lru

# If not set correctly
redis-cli CONFIG SET maxmemory-policy allkeys-lru
redis-cli CONFIG REWRITE
```

**Fix 3 - Clear Stale Data**:
```bash
# Find keys without TTL
redis-cli --scan --pattern "*" | while read key; do
  ttl=$(redis-cli TTL "$key")
  if [ "$ttl" == "-1" ]; then
    echo "No TTL: $key"
  fi
done

# Set TTL on keys without expiration
redis-cli EXPIRE "key-name" 3600
```

---

#### Slow Commands / High Latency

**Diagnosis**:
```bash
# Check slow log
docker-compose exec redis redis-cli -a esab_redis_password SLOWLOG GET 10

# Check latency
redis-cli --latency -h 127.0.0.1 -a '<PASSWORD>'

# Check blocking commands
redis-cli INFO commandstats | grep -E "KEYS|SMEMBERS|HGETALL"
```

**Common Issues**:
1. **Using `KEYS` command** - Blocks Redis
   - **Fix**: Use `SCAN` instead

2. **Large key sizes** - Memory and network overhead
   - **Fix**: Break into smaller keys or use compression

3. **Too many keys** - Memory overhead
   - **Fix**: Increase TTL, implement cleanup job

**Optimization Tips**:
```python
# Bad: Blocks Redis
keys = redis.keys("session:*")

# Good: Non-blocking scan
cursor = 0
keys = []
while True:
    cursor, partial_keys = redis.scan(cursor, match="session:*", count=100)
    keys.extend(partial_keys)
    if cursor == 0:
        break
```

---

### Data Loss Issues

#### Sessions Disappearing

**Possible Causes**:
1. TTL expiring (expected behavior)
2. Memory eviction (maxmemory reached)
3. Redis restart without persistence
4. Application bug not refreshing TTL

**Diagnosis**:
```bash
# Check TTL on session
redis-cli TTL "session:abc-123"
# Returns: -2 (expired/not found), -1 (no TTL), or seconds remaining

# Check eviction stats
redis-cli INFO stats | grep evicted_keys

# Check if persistence is enabled
redis-cli CONFIG GET appendonly
redis-cli CONFIG GET save
```

**Fix 1 - Increase Session TTL**:
```env
# In src/backend/.env
CACHE_TTL=7200  # Increase from 3600 (2 hours)
```

**Fix 2 - Enable Persistence** (if needed for production):

Docker (`docker-compose.prod.yml` already has this):
```yaml
redis:
  command: |
    redis-server
    --requirepass ${REDIS_PASSWORD}
    --appendonly yes
    --appendfsync everysec
    --save 900 1
    --save 300 10
    --save 60 10000
```

**Fix 3 - Verify Application Refreshes TTL**:
```python
# Good: Refresh TTL on each access
await redis.get("session:id")
await redis.expire("session:id", 3600)  # Reset TTL
```

---

#### Redis Container/Service Restarting

**Diagnosis**:
```bash
# Check container status (Docker)
docker-compose ps redis

# Check restart count
docker inspect esab-redis --format='{{.RestartCount}}'

# Check logs for errors
docker-compose logs redis | grep -i error

# Check systemd status (Linux)
sudo systemctl status redis-server

# Check for crash logs
sudo journalctl -u redis-server -p err --since "1 hour ago"
```

**Common Causes**:
1. **Out of memory** (Docker resource limits)
2. **Disk full** (can't write RDB/AOF files)
3. **Configuration errors**
4. **Corrupted RDB/AOF files**

**Fix for OOM** (Docker):
```yaml
redis:
  deploy:
    resources:
      limits:
        memory: 2G  # Increase from 1.5G
```

**Fix for Disk Full**:
```bash
# Check disk space
df -h

# Clean up old Docker volumes/images
docker system prune -a
```

**Fix for Corrupted Files**:
```bash
# Docker: Remove corrupted volume and restart
docker-compose down redis
docker volume rm esab-redis-data
docker-compose up -d redis

# Linux: Remove and restart
sudo systemctl stop redis-server
sudo rm /var/lib/redis/dump.rdb
sudo rm /var/lib/redis/appendonly.aof
sudo systemctl start redis-server
```

---

### RedisInsight Issues

#### "Could not connect" from RedisInsight

**Cause**: Using wrong host/port or network isolation.

**Fix for Linux Systemd Redis**:
- **Host**: `172.17.0.1` (Docker bridge IP)
- **Port**: `6379`
- **Password**: `<REDIS_PASSWORD>` from redis.conf

**Fix for Docker Redis**:
- **Host**: `redis` (service name) or `host.docker.internal` (from RedisInsight container)
- **Port**: `6379`
- **Password**: `esab_redis_password` or `${REDIS_PASSWORD}`

**Verify Docker Network**:
```bash
# Check if RedisInsight is on same network
docker network inspect esab-network

# Should show both redis and redisinsight containers
```

---

#### RedisInsight UI not accessible

**Diagnosis**:
```bash
# Check if container is running
docker ps | grep redisinsight

# Check health endpoint
curl -f http://127.0.0.1:8001/api/health/  # Docker dev
curl -f http://127.0.0.1:6380/api/health/  # Linux systemd

# Check container logs
docker logs redisinsight
```

**Fix**:
```bash
# Restart container
docker restart redisinsight

# Check port binding
sudo netstat -tlnp | grep -E '8001|6380'

# Verify SSH tunnel (if using)
# Windows (PuTTY)
"C:\Program Files\PuTTY\plink.exe" -i "key.ppk" -N -L 6380:127.0.0.1:6380 user@server

# Linux/macOS
ssh -L 6380:127.0.0.1:6380 user@server
```

---

## Related Documentation

### Architecture & Implementation

- **[Redis Session Lifecycle](../docs/redis_session_lifecycle.md)** - Session data models, lifecycle, multi-user support
- **[Redis Multi-User Session Review](../docs/REDIS_MULTI_USER_SESSION_REVIEW.md)** - Implementation review and performance analysis
- **[Linux Redis Configuration (Systemd)](../docs/deployment/redis-linux-systemd.md)** - Detailed Linux-specific production setup

### Deployment Guides

- **[Main Deployment Guide](README.md)** - Overview of all deployment methods
- **[Docker Deployment Guide](docker/README.md)** - Complete Docker deployment documentation
- **[Linux Systemd Deployment](systemd/README.md)** - Production Linux deployment with systemd
- **[Environment Variables Guide](env/README.md)** - Complete environment configuration reference
- **[Database Setup Guide](database/README.md)** - Neo4j, PostgreSQL, and Redis setup

### Troubleshooting & Operations

- **[Redis Quick Troubleshooting](../docs/deployment/redis-guide.md)** - Common issues and quick solutions
- **[Deployment Troubleshooting](../docs/deployment/troubleshooting.md)** - General deployment issues
- **[Operations Runbook](../docs/operations/runbook.md)** - Day-to-day operations and maintenance

### Main Documentation

- **[CLAUDE.md](../CLAUDE.md)** - Main project documentation and development guide

---

## Support

For questions or issues:

1. Check this guide's troubleshooting section
2. Review related documentation links above
3. Check application logs: `docker-compose logs redis` or `sudo journalctl -u redis-server`
4. Review health check: `curl http://localhost:8000/health`
5. Open issue on project repository

---

**Last Updated**: 2025-01-11
**Version**: 2.0
**Deployment Environments**: Docker (dev/prod), Linux Systemd
