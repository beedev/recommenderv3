# Docker Deployment Guide - ESAB Recommender V2

Complete guide for deploying the ESAB Recommender application using Docker in development and production environments.

---

## 📑 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
  - [Development](#development)
  - [Production](#production)
- [Files Structure](#files-structure)
- [Configuration](#configuration)
- [Common Commands](#common-commands)
- [Troubleshooting](#troubleshooting)
- [Logs Management](#logs-management)
- [Advanced Usage](#advanced-usage)
- [Best Practices](#best-practices)
- [Additional Resources](#additional-resources)

---

## Overview

### Architecture

This Docker setup is optimized for **cloud database deployment**:

| Component | Environment |
|-----------|-------------|
| **Backend API** | Docker container (FastAPI) |
| **Neo4j** | Cloud (Neo4j Aura) |
| **PostgreSQL** | Cloud (Azure PostgreSQL / AWS RDS) |
| **Redis Cache** | Local Docker container |
| **RedisInsight** | Local Docker container (monitoring) |

### Key Features

✅ **Multi-stage builds** for optimized production images  
✅ **Non-root user** for security  
✅ **Health checks** for automatic restart  
✅ **Hot reload** in development  
✅ **Resource limits** in production  
✅ **Logging** with rotation  
✅ **Cloud database** integration  

---

## Prerequisites

### System Requirements

- **Docker**: 20.10+ 
- **Docker Compose**: 2.0+
- **OS**: Linux, macOS, or Windows
- **Memory**: 4GB+ RAM
- **Disk**: 10GB+ free space

### Installation

<details>
<summary><strong>Linux (Ubuntu/Debian)</strong></summary>

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (run without sudo)
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```
</details>

<details>
<summary><strong>macOS</strong></summary>

```bash
# Install Docker Desktop (includes Docker Compose)
brew install --cask docker

# Or download from: https://www.docker.com/products/docker-desktop

# Verify installation
docker --version
docker compose version
```
</details>

<details>
<summary><strong>Windows</strong></summary>

```powershell
# Install Docker Desktop from: 
# https://www.docker.com/products/docker-desktop

# Verify installation (PowerShell)
docker --version
docker compose version
```
</details>

### ⚠️ Important Notes

- **Docker Compose v2.0+** is required (this project uses the new syntax)
- If you have Docker Compose v1.x, you must upgrade
- Verify with: `docker compose version` (not `docker-compose --version`)

---

## Quick Start

### Development

**Start development environment with hot reload:**

```bash
# 1. Navigate to docker directory
cd deployment/docker

# 2. Create environment file
cp ../env/.env.development.example ../../src/backend/.env

# 3. Edit .env with your credentials
nano ../../src/backend/.env

# Required variables:
# - OPENAI_API_KEY
# - NEO4J_URI (Neo4j Aura connection string)
# - NEO4J_USERNAME, NEO4J_PASSWORD
# - POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD

# 4. Start services
sudo docker compose -f docker-compose.yml up -d

# 5. View logs
sudo docker compose -f docker-compose.yml logs -f backend

# 6. Access services
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - RedisInsight: http://localhost:8001
```

**Stop services:**
```bash
sudo docker compose -f docker-compose.yml down
```

**Rebuild and restart:**
```bash
sudo docker compose -f docker-compose.yml down && \
sudo docker compose -f docker-compose.yml build --no-cache && \
sudo docker compose -f docker-compose.yml up -d
```

### Production

**Deploy production environment:**

```bash
# 1. Navigate to docker directory
cd deployment/docker

# 2. Create environment file
cp ../env/.env.production.example ../../src/backend/.env

# 3. Edit .env with production credentials
nano ../../src/backend/.env

# IMPORTANT: Set secure passwords!
# - SECRET_KEY (32+ random characters)
# - JWT_SECRET_KEY (32+ random characters)
# - REDIS_PASSWORD (change from default)

# Generate secure keys:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 4. Deploy
sudo docker compose -f docker-compose.prod.yml down && \
sudo docker rmi esab-recommender:latest 2>/dev/null; \
sudo docker compose -f docker-compose.prod.yml build --no-cache && \
sudo docker compose -f docker-compose.prod.yml up -d

# 5. Verify deployment
sudo docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health

# 6. View logs
sudo docker compose -f docker-compose.prod.yml logs -f backend
```

**Expected health check response:**
```json
{"status":"healthy"}
```

---

## Files Structure

```
deployment/docker/
├── Dockerfile                    # Production build (multi-stage)
├── Dockerfile.dev               # Development build (with hot reload)
├── docker-compose.yml           # Development environment
├── docker-compose.prod.yml      # Production environment
├── .dockerignore               # Files to exclude from build
└── README.md                   # This file

deployment/env/
├── .env.development.example    # Dev environment template
└── .env.production.example     # Prod environment template

src/backend/
└── .env                        # Your actual environment variables
```

### File Descriptions

| File | Purpose | User |
|------|---------|------|
| **Dockerfile** | Multi-stage production image with security | Production |
| **Dockerfile.dev** | Development image with hot reload & dev tools | Development |
| **docker-compose.yml** | Dev stack (backend + Redis + RedisInsight) | Development |
| **docker-compose.prod.yml** | Production stack with resource limits | Production |
| **.dockerignore** | Excludes unnecessary files from build context | Both |

---

## Configuration

### Environment Variables

Create `src/backend/.env` with the following variables:

#### Required (All Environments)

```bash
# OpenAI API
OPENAI_API_KEY=sk-xxxxx

# Neo4j Aura (Cloud)
NEO4J_URI=bolt+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# Azure PostgreSQL (Cloud)
POSTGRES_HOST=xxxxx.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DB=pconfig
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password
```

#### Production Only (Additional)

```bash
# Security (MUST CHANGE!)
SECRET_KEY=generate_32_char_random_string_here
JWT_SECRET_KEY=generate_another_32_char_random_string

# Redis (Local - MUST CHANGE PASSWORD!)
REDIS_PASSWORD=your_secure_redis_password_here

# Application
ENVIRONMENT=production
DEBUG=False
```

#### Optional (All Environments)

```bash
# LangSmith (Tracing)
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=Recommender
LANGSMITH_TRACING=false

# Redis Cache Settings
REDIS_DB=0
CACHE_TTL=3600

# Ports (if customizing)
BACKEND_PORT=8000
REDIS_PORT=6379
REDISINSIGHT_PORT=8001
```

### Generate Secure Keys

```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# JWT_SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Redis password
python -c "import secrets; print(secrets.token_urlsafe(24))"
```

---

## Common Commands

### Development Commands

```bash
# Start services
sudo docker compose -f docker-compose.yml up -d

# Stop services
sudo docker compose -f docker-compose.yml down

# Restart services
sudo docker compose -f docker-compose.yml restart

# Rebuild and restart
sudo docker compose -f docker-compose.yml down && \
sudo docker compose -f docker-compose.yml build --no-cache && \
sudo docker compose -f docker-compose.yml up -d

# View logs (all services)
sudo docker compose -f docker-compose.yml logs -f

# View logs (specific service)
sudo docker compose -f docker-compose.yml logs -f backend
sudo docker compose -f docker-compose.yml logs -f redis

# Check service status
sudo docker compose -f docker-compose.yml ps

# Execute command in container
sudo docker compose -f docker-compose.yml exec backend bash
sudo docker compose -f docker-compose.yml exec redis redis-cli -a esab_redis_password ping
```

### Production Commands

```bash
# Start services
sudo docker compose -f docker-compose.prod.yml up -d

# Stop services
sudo docker compose -f docker-compose.prod.yml down

# Full rebuild and redeploy
sudo docker compose -f docker-compose.prod.yml down && \
sudo docker rmi esab-recommender:latest 2>/dev/null; \
sudo docker compose -f docker-compose.prod.yml build --no-cache && \
sudo docker compose -f docker-compose.prod.yml up -d

# View logs
sudo docker compose -f docker-compose.prod.yml logs -f backend

# Check health
curl http://localhost:8000/health

# Monitor resources
sudo docker stats
```

### Image Management

```bash
# List all images
sudo docker images

# Remove specific image
sudo docker rmi image_name:tag

# Remove dangling images (<none>)
sudo docker image prune -f

# Remove all unused images
sudo docker image prune -a

# Remove old backend images
sudo docker rmi docker-backend:latest docker_backend:latest
```

### Cleanup Commands

```bash
# Remove stopped containers
sudo docker container prune

# Remove unused volumes
sudo docker volume prune

# Remove unused networks
sudo docker network prune

# Remove everything unused (⚠️ careful!)
sudo docker system prune -a --volumes

# Check disk usage
sudo docker system df
```

---

## Troubleshooting

### Common Issues

#### 1. **Permission Denied: uvicorn**

**Error:**
```bash
sh: 1: uvicorn: Permission denied
esab-backend-prod exited with code 127
```

**Cause:** Production Dockerfile has permission mismatch (non-root user can't access `/root/.local/bin`)

**Solution:** Use the fixed Dockerfile provided in the outputs folder

**Quick fix:**
1. Replace `deployment/docker/Dockerfile` with the fixed version
2. Rebuild:
   ```bash
   sudo docker compose -f docker-compose.prod.yml down
   sudo docker rmi esab-recommender:latest
   sudo docker compose -f docker-compose.prod.yml build --no-cache
   sudo docker compose -f docker-compose.prod.yml up -d
   ```

**See:** `FIX_PERMISSION_ERROR.md` for detailed explanation

---

#### 2. **Container Exits Immediately**

**Check logs:**
```bash
sudo docker compose logs backend
```

**Common causes:**
- Missing environment variables
- Database connection failed
- Port already in use

**Verify environment:**
```bash
sudo docker compose exec backend env | grep -E "NEO4J|POSTGRES|REDIS"
```

**Test database connections:**
```bash
# Test Redis
sudo docker compose exec backend ping redis

# Test from outside
curl http://localhost:8000/health
```

---

#### 3. **Redis Connection Failed**

**Error:** `Connection refused` or `Authentication failed`

**Check Redis status:**
```bash
sudo docker compose ps redis
sudo docker compose logs redis
```

**Test Redis:**
```bash
# From host
sudo docker compose exec redis redis-cli -a your_password ping

# From backend container
sudo docker compose exec backend redis-cli -h redis -a your_password ping
```

**Common fixes:**
- Ensure Redis service is running
- Check password in `.env` matches docker-compose
- Verify `REDIS_HOST=redis` (service name, not localhost)

---

#### 4. **Health Check Failing**

**Check backend logs:**
```bash
sudo docker compose logs backend | grep -i error
```

**Test health endpoint manually:**
```bash
curl -v http://localhost:8000/health
```

**Common causes:**
- Backend not starting (check logs)
- Database connections failing
- Port not exposed correctly

**Verify container is running:**
```bash
sudo docker compose ps
```

---

#### 5. **Port Already in Use**

**Error:** `bind: address already in use`

**Find process using port:**
```bash
sudo netstat -tlnp | grep 8000
sudo lsof -i :8000
```

**Kill process:**
```bash
sudo kill -9 <PID>
```

**Or change port in docker-compose:**
```yaml
ports:
  - "9000:8000"  # Use port 9000 instead
```

---

#### 6. **Out of Memory**

**Check resource usage:**
```bash
sudo docker stats
```

**Increase limits in docker-compose.prod.yml:**
```yaml
deploy:
  resources:
    limits:
      memory: 8G  # Increase from 4G
```

**Or clean up:**
```bash
sudo docker system prune -a
```

---

#### 7. **Module Not Found**

**Error:** `ModuleNotFoundError: No module named 'xxx'`

**Rebuild without cache:**
```bash
sudo docker compose build --no-cache
```

**Verify requirements installed:**
```bash
sudo docker compose exec backend pip list
```

---

### Verification Commands

```bash
# Check all services are running
sudo docker compose ps

# Test backend health
curl http://localhost:8000/health

# Test Redis connection
sudo docker compose exec redis redis-cli -a password ping

# Check backend can reach Redis
sudo docker compose exec backend ping redis

# Verify environment variables
sudo docker compose exec backend env | grep -E "NEO4J|POSTGRES|REDIS"

# Check resource usage
sudo docker stats

# Test API endpoints
curl http://localhost:8000/docs
```

---

## Logs Management

### Viewing Logs

```bash
# All services, follow mode
sudo docker compose logs -f

# Specific service
sudo docker compose logs -f backend
sudo docker compose logs -f redis

# Last 100 lines
sudo docker compose logs --tail=100 backend

# Logs since timestamp
sudo docker compose logs --since 2024-01-01T00:00:00 backend

# Logs from last hour
sudo docker compose logs --since 1h backend
```

### Filtering Logs

```bash
# Show only errors
sudo docker compose logs backend | grep -i error

# Show errors and warnings
sudo docker compose logs backend | grep -iE "error|warning"

# Exclude health checks
sudo docker compose logs backend | grep -v healthcheck

# Search for specific session
sudo docker compose logs backend | grep "session_id=xyz"

# Real-time error monitoring
sudo docker compose logs -f backend | grep --color=always -i error
```

### Log Rotation

**Current configuration (production):**
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "100m"    # Max 100MB per file
    max-file: "10"      # Keep 10 files (1GB total)
```

**Check log disk usage:**
```bash
sudo docker system df
```

**Clean old logs:**
```bash
# Remove all stopped container logs
sudo docker container prune

# Or restart specific service
sudo docker compose restart backend
```

### Export Logs

```bash
# Export last 24 hours
sudo docker compose logs --since 24h backend > backend-logs-$(date +%Y%m%d).txt

# Export with timestamps
sudo docker compose logs -t backend > backend-logs.txt

# Export errors only
sudo docker compose logs backend | grep -i error > errors.txt
```

---

## Advanced Usage

### Custom Builds

```bash
# Build specific stage (for debugging)
sudo docker build -f Dockerfile --target builder -t esab-builder ../../

# Build with custom tag
sudo docker build -f Dockerfile -t esab-recommender:2.0.0 ../../

# Build with build arguments
sudo docker build --build-arg PYTHON_VERSION=3.11 -f Dockerfile ../../
```

### Multiple Environments

```bash
# Use custom environment file
sudo docker compose --env-file .env.staging up -d

# Override specific variables
BACKEND_PORT=9000 sudo docker compose up -d
```

### Resource Monitoring

```bash
# Real-time stats
sudo docker stats

# Specific container
sudo docker stats esab-backend-prod

# All containers (one-time snapshot)
sudo docker stats --no-stream
```

### Container Management

```bash
# Enter container shell
sudo docker compose exec backend bash

# Run command in container
sudo docker compose exec backend python --version

# Copy files to/from container
sudo docker cp local-file.txt esab-backend:/app/
sudo docker cp esab-backend:/app/logs/ ./local-logs/
```

### Network Debugging

```bash
# Inspect network
sudo docker network inspect esab-network

# Test connectivity between containers
sudo docker compose exec backend ping redis
sudo docker compose exec backend curl redis:6379

# View container IP
sudo docker inspect esab-backend | grep IPAddress
```

---

## Best Practices

### Security

1. ✅ **Use non-root user** (already configured)
2. ✅ **Change default passwords** in production
3. ✅ **Use Docker secrets** for sensitive data
4. ✅ **Enable TLS/SSL** with reverse proxy
5. ✅ **Scan images** for vulnerabilities
6. ✅ **Keep images updated** regularly
7. ✅ **Restrict network access** with firewall rules

### Performance

1. ✅ **Set resource limits** (CPU, memory)
2. ✅ **Use health checks** for auto-restart
3. ✅ **Enable Redis caching** for better performance
4. ✅ **Use multi-stage builds** for smaller images
5. ✅ **Optimize Dockerfile layers** for faster builds

### Operations

1. ✅ **Use specific version tags** (not `:latest` in prod)
2. ✅ **Implement log rotation** to prevent disk fill
3. ✅ **Set up monitoring** (Prometheus, Grafana)
4. ✅ **Regular backups** of volumes
5. ✅ **Document deployment** procedures
6. ✅ **Test in staging** before production
7. ✅ **Use CI/CD** for automated deployments

### Development

1. ✅ **Use hot reload** for faster development
2. ✅ **Mount source code** as volume
3. ✅ **Use development Dockerfile** (Dockerfile.dev)
4. ✅ **Enable debug logging** (DEBUG=True)
5. ✅ **Test with development environment** before committing

---

## Additional Resources

### Documentation in This Repository

- **[QUICK_START.md](./QUICK_START.md)** - 5-minute deployment guide
- **[PRODUCTION_DEPLOYMENT_GUIDE.md](./PRODUCTION_DEPLOYMENT_GUIDE.md)** - Comprehensive production guide
- **[CHANGES_COMPARISON.md](./CHANGES_COMPARISON.md)** - What changed and why
- **[FIX_PERMISSION_ERROR.md](./FIX_PERMISSION_ERROR.md)** - Fix uvicorn permission issues
- **[DOCKERFILE_DEV_ANALYSIS.md](./DOCKERFILE_DEV_ANALYSIS.md)** - Dev vs Prod comparison
- **[QUICK_FIX_COMMANDS.md](./QUICK_FIX_COMMANDS.md)** - Copy-paste command reference

### External Documentation

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [Neo4j Aura Documentation](https://neo4j.com/docs/aura/)
- [Azure PostgreSQL Documentation](https://docs.microsoft.com/azure/postgresql/)
- [Redis Documentation](https://redis.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### Useful Tools

- **RedisInsight**: http://localhost:8001 - Redis monitoring UI
- **Backend Docs**: http://localhost:8000/docs - Interactive API documentation
- **Neo4j Browser**: Access via Neo4j Aura dashboard
- **Docker Desktop**: GUI for managing containers (macOS/Windows)

---

## Support

### Getting Help

1. **Check this README** for common issues
2. **Review logs**: `sudo docker compose logs backend`
3. **Verify configuration**: Check `.env` file
4. **Test connectivity**: Use verification commands above
5. **Check GitHub issues**: Search for similar problems
6. **Consult team documentation**: See project main README

### Reporting Issues

When reporting issues, include:

1. Error message and full logs
2. Docker and Docker Compose versions
3. OS and version
4. Steps to reproduce
5. Configuration (without sensitive data)
6. Output of: `sudo docker compose ps` and `sudo docker stats`

---

## Quick Reference

### Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | http://localhost:8000 | Main application |
| API Documentation | http://localhost:8000/docs | Interactive API docs |
| Health Check | http://localhost:8000/health | Service status |
| RedisInsight | http://localhost:8001 | Redis monitoring |
| Neo4j Browser | Via Aura dashboard | Graph database UI |

### Common Ports

| Port | Service | Environment |
|------|---------|-------------|
| 8000 | Backend API | Both |
| 8001 | RedisInsight | Both |
| 6379 | Redis | Both (internal) |

### File Locations

| Path | Description |
|------|-------------|
| `src/backend/.env` | Environment variables |
| `deployment/docker/` | Docker configurations |
| `logs/` | Application logs (in container) |
| `/var/lib/docker/` | Docker data (host) |

---

**Last Updated**: 2024  
**Version**: 2.0  
**Docker Compose Version Required**: 2.0+

---

**🚀 Ready to deploy? Start with the [Quick Start](#quick-start) section above!**
