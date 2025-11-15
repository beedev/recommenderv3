# Systemd Deployment

This directory contains systemd service files and deployment scripts for running ESAB Recommender V2 on Linux servers with systemd init system (Ubuntu, Debian, CentOS, RHEL, etc.).

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Service Files](#service-files)
- [Manual Installation](#manual-installation)
- [Service Management](#service-management)
- [Logs and Monitoring](#logs-and-monitoring)
- [Troubleshooting](#troubleshooting)
- [Advanced Configuration](#advanced-configuration)

---

## Overview

The application runs as two systemd services:

| Service | Description | Port |
|---------|-------------|------|
| `esab-recommender.service` | Backend FastAPI application | 8000 |
| `esab-recommender-frontend.service` | Frontend HTTP server (optional) | 3000 |
| `esab-recommender.target` | Target unit to control both services | N/A |

**Installation Location**: Auto-detected from script location (works anywhere on your system)

**Path Detection**: The deploy script automatically detects:
- Installation directory from script location
- Application user from current sudo user or logged-in user
- No hardcoded paths - works in any directory structure

---

## Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04/22.04 LTS, Debian 11+, CentOS 8+, RHEL 8+
- **Python**: 3.11+ (tested with 3.11 and 3.12)
- **RAM**: 4GB minimum (8GB recommended)
- **CPU**: 2+ cores recommended
- **Disk**: 20GB+ free space
- **User**: Services run as the user executing the script (auto-detected)

### Required Services Running

1. **Neo4j** - Product catalog (port 7687)
   - Neo4j Aura (cloud) or local installation
2. **PostgreSQL** - Session archival (port 5432)
3. **Redis** - Session caching (port 6379, optional but recommended)
   - Local installation or cloud managed service (Azure Cache, AWS ElastiCache)
   - **Setup Guide**: See [Redis Configuration Guide](../Redis-Config.md) for complete Redis installation and configuration
   - Required for session management and conversation state caching

### Installation Tools

```bash
# Install required system packages
sudo apt-get update
sudo apt-get install -y python3.11 python3.11-venv python3-pip git curl
```

---

## Quick Start

### Automated Installation

The easiest way to deploy is using the provided deployment script. The script automatically detects your installation directory - no need to configure paths!

```bash
# 1. Clone or copy the repository to your desired location
cd /home/your-user/
git clone <repository-url> ayna-pod-recommender
cd ayna-pod-recommender

# Or if copying from another location:
# rsync -avz --progress ./ user@your-server:/home/your-user/ayna-pod-recommender/

# 2. Run deployment script from the deployment/systemd directory
chmod +x deployment/systemd/deploy.sh
sudo ./deployment/systemd/deploy.sh install

# The script will display detected configuration:
# - Installation Directory: /home/your-user/ayna-pod-recommender
# - Application User: your-user
# - Backend Directory: /home/your-user/ayna-pod-recommender/src/backend
# - Log Directory: /home/your-user/ayna-pod-recommender/logs

# 3. Configure environment
nano src/backend/.env

# 4. Start services
sudo systemctl start esab-recommender.target
sudo systemctl status esab-recommender.target
```

**Note**: The script works from any installation path. It detects the repository root automatically and configures all systemd services with the correct paths.

---

## Service Files

### esab-recommender.service

Backend FastAPI service running with uvicorn.

**Key Features**:
- Runs 4 uvicorn workers for production
- Automatic restart on failure
- Log files written to `<INSTALL_DIR>/logs/` (auto-detected)
- Environment loaded from `<INSTALL_DIR>/src/backend/.env` (auto-detected)
- 120s startup timeout (allows time for model loading)

**File Location**: `/etc/systemd/system/esab-recommender.service`

**Configuration** (Example - actual paths are auto-detected during installation):
```ini
[Unit]
Description=ESAB Recommender V2 Backend API
After=network.target neo4j.service postgresql.service redis.service

[Service]
Type=exec
User=<YOUR_USER>
Group=<YOUR_USER>
WorkingDirectory=<YOUR_INSTALL_DIR>/src/backend
EnvironmentFile=<YOUR_INSTALL_DIR>/src/backend/.env

ExecStart=<YOUR_INSTALL_DIR>/src/backend/venv/bin/uvicorn \
    app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    --log-level info

Restart=always
RestartSec=10
TimeoutStartSec=120

StandardOutput=append:<YOUR_INSTALL_DIR>/logs/esab-recommender.log
StandardError=append:<YOUR_INSTALL_DIR>/logs/esab-recommender-error.log

[Install]
WantedBy=multi-user.target
```

**Note**: The deploy.sh script automatically generates the actual service file with your detected paths. You don't need to manually edit these values.

### esab-recommender-frontend.service

Optional frontend HTTP server (if serving separate frontend).

**Key Features**:
- Serves static files on port 3000
- Python's http.server module
- Optional service (backend can serve static files via `/static/`)

**File Location**: `/etc/systemd/system/esab-recommender-frontend.service`

**Note**: If you're using the backend's built-in static file serving (`http://localhost:8000/static/`), you don't need this service.

### esab-recommender.target

Target unit for controlling both services together.

**Usage**:
```bash
# Start both services
sudo systemctl start esab-recommender.target

# Stop both services
sudo systemctl stop esab-recommender.target
```

**File Location**: `/etc/systemd/system/esab-recommender.target`

---

## Manual Installation

**⚠️ IMPORTANT**: Manual installation is **NOT RECOMMENDED** because the service files contain placeholder paths. The automated `deploy.sh` script should always be used as it dynamically generates service files with correct paths.

If you absolutely must install manually, you would need to:

1. **Clone/copy repository to desired location**
2. **Create virtual environment and install dependencies**
3. **Configure .env file**
4. **Run the deploy script** (recommended) OR manually generate service files

### Recommended: Use the Deploy Script

Even for "manual" setups, always use the deploy script:

```bash
# From your repository directory
cd /path/to/your/ayna-pod-recommender
sudo ./deployment/systemd/deploy.sh install
```

This automatically:
- Detects your installation directory
- Detects current user
- Creates virtual environment
- Installs dependencies
- Generates systemd service files with correct paths
- Configures and enables services

### Alternative: Generate Service Files Only

If you want to manage dependencies yourself but need systemd services:

```bash
cd /path/to/your/ayna-pod-recommender

# Manually create venv and install deps
cd src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ../..

# Configure .env
cp deployment/env/.env.production.example src/backend/.env
nano src/backend/.env

# Run deploy script (it will detect existing venv)
sudo ./deployment/systemd/deploy.sh install
```

The deploy script will handle:
- Generating service files with correct paths
- Copying service files to `/etc/systemd/system/`
- Reloading systemd daemon
- Enabling services
- Starting services

**Required environment variables in src/backend/.env**:
- `OPENAI_API_KEY` - OpenAI API key
- `NEO4J_URI` - Neo4j connection URI
- `NEO4J_USERNAME`, `NEO4J_PASSWORD` - Neo4j credentials
- `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - PostgreSQL config
- `REDIS_HOST`, `REDIS_PASSWORD` - Redis config (if using Redis)
- `SECRET_KEY`, `JWT_SECRET_KEY` - Application secrets

See [../env/README.md](../env/README.md) for full environment configuration guide.

### Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# API documentation
curl http://localhost:8000/docs

# Test configurator endpoint
curl -X POST http://localhost:8000/api/v1/configurator/message \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a 500A MIG welder", "language": "en"}'
```

---

## Service Management

### Start/Stop/Restart Services

**Control both services together** (recommended):
```bash
# Start
sudo systemctl start esab-recommender.target

# Stop
sudo systemctl stop esab-recommender.target

# Restart
sudo systemctl restart esab-recommender.target

# Status
sudo systemctl status esab-recommender.target
```

**Control backend only**:
```bash
sudo systemctl start esab-recommender.service
sudo systemctl stop esab-recommender.service
sudo systemctl restart esab-recommender.service
sudo systemctl status esab-recommender.service
```

**Control frontend only**:
```bash
sudo systemctl start esab-recommender-frontend.service
sudo systemctl stop esab-recommender-frontend.service
sudo systemctl restart esab-recommender-frontend.service
sudo systemctl status esab-recommender-frontend.service
```

### Enable/Disable Auto-Start

```bash
# Enable (start on boot)
sudo systemctl enable esab-recommender.target

# Disable (don't start on boot)
sudo systemctl disable esab-recommender.target

# Check if enabled
systemctl is-enabled esab-recommender.service
```

### Reload Configuration

After changing service files:

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Restart service to apply changes
sudo systemctl restart esab-recommender.service
```

---

## Logs and Monitoring

### View Logs

**File logs** (recommended):
```bash
# Follow main log
tail -f /home/azureuser/esab_recommender-bh/logs/esab-recommender.log

# Follow error log
tail -f /home/azureuser/esab_recommender-bh/logs/esab-recommender-error.log

# View last 100 lines
tail -n 100 /home/azureuser/esab_recommender-bh/logs/esab-recommender.log

# Search for errors
grep -i error /home/azureuser/esab_recommender-bh/logs/esab-recommender.log

# Follow both logs
tail -f /home/azureuser/esab_recommender-bh/logs/*.log
```

**Systemd journal**:
```bash
# View backend logs
sudo journalctl -u esab-recommender.service -n 100

# Follow logs in real-time
sudo journalctl -u esab-recommender.service -f

# View both services
sudo journalctl -u esab-recommender.service -u esab-recommender-frontend.service -f

# View logs from specific time
sudo journalctl -u esab-recommender.service --since "1 hour ago"
sudo journalctl -u esab-recommender.service --since "2025-01-15 10:00:00"

# View logs with priority
sudo journalctl -u esab-recommender.service -p err  # Errors only
sudo journalctl -u esab-recommender.service -p warning  # Warnings and above
```

### Health Checks

```bash
# Backend API health
curl http://localhost:8000/health

# Frontend health
curl -I http://localhost:3000/

# Check listening ports
sudo netstat -tlnp | grep -E '(8000|3000)'
sudo ss -tlnp | grep -E '(8000|3000)'

# Check service status
systemctl is-active esab-recommender.service
systemctl is-active esab-recommender-frontend.service
```

### Resource Monitoring

```bash
# Service status (includes memory/CPU)
systemctl status esab-recommender.service

# Detailed resource usage
systemd-cgtop

# Check process details
ps aux | grep uvicorn

# Memory usage
free -h
```

### Log Rotation

Prevent log files from growing too large:

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/esab-recommender
```

Add this configuration:
```
/home/azureuser/esab_recommender-bh/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 azureuser azureuser
    sharedscripts
    postrotate
        systemctl reload esab-recommender.service > /dev/null 2>&1 || true
    endscript
}
```

Test configuration:
```bash
sudo logrotate -d /etc/logrotate.d/esab-recommender
```

---

## Troubleshooting

### Service Won't Start or Times Out

**Symptom**: Service shows "activating" but never completes, or times out

**Cause**: With 4 workers, initialization takes 40-60 seconds. Default systemd timeout may be too short.

**Solution**:

```bash
# 1. Check if service is actually working (it often is)
curl http://localhost:8000/health

# 2. If the above works, service IS running - just timeout issue
# Increase timeout in service file
sudo nano /etc/systemd/system/esab-recommender.service

# Add this line in [Service] section:
TimeoutStartSec=120

# Change Type from "notify" to "exec"
Type=exec

# 3. Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart esab-recommender.service

# 4. Alternative: Reduce workers for faster startup
# Change: --workers 4 to --workers 2
```

### Database Connection Errors

```bash
# Test Neo4j
cypher-shell -u neo4j -p your_password "RETURN 1;"

# Test PostgreSQL
PGPASSWORD=your_password psql -h localhost -U postgres -d pconfig -c "SELECT 1;"

# Test Redis
redis-cli -a your_password PING

# Check if services are running
sudo systemctl status neo4j
sudo systemctl status postgresql
sudo systemctl status redis
```

### Redis Connection Issues

Redis is critical for session management. Common Redis issues:

**Test Redis Connection**:
```bash
# Test from localhost
redis-cli -h 127.0.0.1 -a '<REDIS_PASSWORD>' ping
# Expected: PONG

# Test from Docker bridge (for RedisInsight)
redis-cli -h 172.17.0.1 -a '<REDIS_PASSWORD>' ping

# Check Redis service status
sudo systemctl status redis-server

# View Redis logs
sudo journalctl -u redis-server -n 50
```

**Check Redis Configuration**:
```bash
# View Redis config
sudo cat /etc/redis/redis.conf | grep -E 'bind|requirepass|maxmemory'

# Check Redis is listening on correct IPs
sudo ss -ltnp | grep 6379
# Should show: 127.0.0.1:6379, ::1:6379, 172.17.0.1:6379
```

**Verify Docker Bridge IP**:
```bash
# Get Docker bridge IP
ip -4 addr show docker0 | awk '/inet /{print $2}' | cut -d/ -f1
# Expected: 172.17.0.1

# Redis must bind to this IP for Docker containers (RedisInsight) to connect
```

**Common Redis Errors**:

**Error: "NOAUTH Authentication required"**
- Check password in `/etc/redis/redis.conf`: `sudo grep requirepass /etc/redis/redis.conf`
- Update `REDIS_PASSWORD` in `src/backend/.env` to match
- Restart backend: `sudo systemctl restart esab-recommender.service`

**Error: "Could not connect to Redis at 127.0.0.1:6379"**
- Check Redis is running: `sudo systemctl status redis-server`
- Check firewall isn't blocking: `sudo ufw status | grep 6379`
- Start Redis: `sudo systemctl start redis-server`

**Error: "Connection refused" from RedisInsight**
- RedisInsight containers must use `172.17.0.1`, NOT `127.0.0.1`
- Verify Redis binds to Docker bridge: `sudo grep bind /etc/redis/redis.conf`
- Should include: `bind 127.0.0.1 ::1 172.17.0.1`

**Sessions Disappearing**:
- Check Redis memory: `redis-cli -a '<PASSWORD>' INFO memory | grep used_memory_human`
- Check TTL settings: `grep CACHE_TTL src/backend/.env`
- Increase TTL if needed: `CACHE_TTL=7200` (2 hours)
- Check Redis eviction: `redis-cli -a '<PASSWORD>' INFO stats | grep evicted_keys`

**Restart Redis**:
```bash
sudo systemctl restart redis-server
sudo journalctl -u redis-server -f
```

**For comprehensive Redis documentation**, see:
- **[Redis Configuration Guide](../Redis-Config.md)** - Complete setup for all environments
- **[Redis Quick Troubleshooting](../../docs/deployment/redis-guide.md)** - Common issues and solutions

### Port Already in Use

```bash
# Find process using port 8000
sudo netstat -tlnp | grep 8000
sudo lsof -i :8000

# Kill process if needed
sudo kill -9 <PID>

# Or restart service properly
sudo systemctl stop esab-recommender.service
sudo systemctl start esab-recommender.service
```

### Permission Denied Errors

```bash
# Reset ownership
sudo chown -R azureuser:azureuser /home/azureuser/esab_recommender-bh

# Set directory permissions
sudo chmod -R 755 /home/azureuser/esab_recommender-bh

# Secure .env file
sudo chmod 600 /home/azureuser/esab_recommender-bh/src/backend/.env
```

### Virtual Environment Missing or Broken

```bash
# Check if venv exists
test -f /home/azureuser/esab_recommender-bh/src/backend/venv/bin/uvicorn && echo "OK" || echo "MISSING"

# Recreate venv if needed
cd /home/azureuser/esab_recommender-bh/src/backend
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Restart service
sudo systemctl restart esab-recommender.service
```

### Environment File Issues

```bash
# Check if .env exists
ls -la /home/azureuser/esab_recommender-bh/src/backend/.env

# Verify required variables
grep OPENAI_API_KEY /home/azureuser/esab_recommender-bh/src/backend/.env
grep NEO4J_URI /home/azureuser/esab_recommender-bh/src/backend/.env

# Test environment loading
cd /home/azureuser/esab_recommender-bh/src/backend
source venv/bin/activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
deactivate
```

### High Memory Usage

```bash
# Reduce workers in service file
sudo nano /etc/systemd/system/esab-recommender.service

# Change: --workers 4 to --workers 2
# Or use formula: (CPU cores × 2) + 1

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart esab-recommender.service
```

### Service Crashes on Restart

```bash
# View crash logs
sudo journalctl -u esab-recommender.service -n 200

# Check for Python errors
tail -n 100 /home/azureuser/esab_recommender-bh/logs/esab-recommender-error.log

# Reset failed state
sudo systemctl reset-failed esab-recommender.service

# Try starting again
sudo systemctl start esab-recommender.service
```

---

## Advanced Configuration

### Customizing Workers

Edit service file to adjust worker count:

```bash
sudo nano /etc/systemd/system/esab-recommender.service
```

Change `--workers` value:
```ini
# For 2-core machine:
ExecStart=... --workers 5

# For 4-core machine:
ExecStart=... --workers 9

# For 8-core machine:
ExecStart=... --workers 17

# Formula: (CPU cores × 2) + 1
```

### Changing Ports

Edit service file:

```bash
sudo nano /etc/systemd/system/esab-recommender.service
```

Change `--port`:
```ini
ExecStart=... --port 9000  # Change from 8000 to 9000
```

Also update:
- Environment variable `PORT=9000` in .env
- Nginx configuration (if using)
- Firewall rules

### Running as Different User

Edit service file:

```bash
sudo nano /etc/systemd/system/esab-recommender.service
```

Change `User` and `Group`:
```ini
[Service]
User=myappuser
Group=myappuser
```

Adjust ownership:
```bash
sudo chown -R myappuser:myappuser /home/azureuser/esab_recommender-bh
```

### Environment-Specific Configurations

Use different .env files:

```bash
# Development
EnvironmentFile=/home/azureuser/esab_recommender-bh/src/backend/.env.dev

# Staging
EnvironmentFile=/home/azureuser/esab_recommender-bh/src/backend/.env.staging

# Production
EnvironmentFile=/home/azureuser/esab_recommender-bh/src/backend/.env.prod
```

### Adding Environment Variables

Edit service file to add inline variables:

```bash
sudo nano /etc/systemd/system/esab-recommender.service
```

```ini
[Service]
Environment="LOG_LEVEL=DEBUG"
Environment="WORKERS=4"
EnvironmentFile=/path/to/.env
```

**Note**: Inline `Environment=` takes precedence over `EnvironmentFile`.

### Restart Policies

Customize restart behavior:

```ini
[Service]
# Always restart (default)
Restart=always

# Restart only on failure
Restart=on-failure

# Restart on success and failure
Restart=on-abnormal

# Never restart
Restart=no

# Restart delay
RestartSec=10

# Maximum restart attempts
StartLimitBurst=5
StartLimitIntervalSec=30
```

---

## Updating the Application

### Using Deployment Script

```bash
cd /home/azureuser/esab_recommender-bh
sudo ./deployment/systemd/deploy.sh update
```

### Manual Update

```bash
# 1. Stop service
sudo systemctl stop esab-recommender.target

# 2. Backup current installation
tar -czf /tmp/esab-backup-$(date +%Y%m%d).tar.gz \
    /home/azureuser/esab_recommender-bh

# 3. Update code
cd /home/azureuser/esab_recommender-bh
git pull origin main

# 4. Update dependencies
cd src/backend
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate

# 5. Update service files if changed
sudo cp deployment/systemd/*.service /etc/systemd/system/
sudo cp deployment/systemd/*.target /etc/systemd/system/
sudo systemctl daemon-reload

# 6. Restart services
sudo systemctl start esab-recommender.target

# 7. Verify
curl http://localhost:8000/health
tail -f /home/azureuser/esab_recommender-bh/logs/esab-recommender.log
```

---

## Nginx Reverse Proxy (Recommended)

For production, run behind Nginx:

```nginx
upstream esab_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 50M;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;

    location / {
        proxy_pass http://esab_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Install SSL:
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Security Considerations

### Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Don't expose backend port 8000 if using Nginx
# Block external access to databases
sudo ufw deny 7687/tcp  # Neo4j
sudo ufw deny 5432/tcp  # PostgreSQL
sudo ufw deny 6379/tcp  # Redis
```

### File Permissions

```bash
# Application directory
chmod 755 /home/azureuser/esab_recommender-bh

# Environment file (sensitive)
chmod 600 /home/azureuser/esab_recommender-bh/src/backend/.env

# Log directory
chmod 755 /home/azureuser/esab_recommender-bh/logs
chmod 644 /home/azureuser/esab_recommender-bh/logs/*.log
```

### Systemd Security Hardening

Add to service file:

```ini
[Service]
# Restrict filesystem access
ProtectSystem=strict
ReadWritePaths=/home/azureuser/esab_recommender-bh/logs
ReadOnlyPaths=/home/azureuser/esab_recommender-bh

# Restrict network
RestrictAddressFamilies=AF_INET AF_INET6

# Restrict capabilities
CapabilityBoundingSet=
AmbientCapabilities=

# Restrict privileges
NoNewPrivileges=true
PrivateTmp=true
```

**Note**: Test thoroughly after adding security hardening.

---

## Need Help?

- **Environment Configuration**: See [../env/README.md](../env/README.md)
- **Docker Deployment**: See [../docker/README.md](../docker/README.md)
- **Database Setup**: See [../database/README.md](../database/README.md)
- **Application Architecture**: See CLAUDE.md in root directory
- **Deployment Overview**: See [../README.md](../README.md)
