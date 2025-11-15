# ESAB Recommender V2 - Deployment

Production-ready deployment infrastructure for ESAB Recommender V2.

## Quick Links

### Getting Started
- **[📖 Full Deployment Documentation](../docs/deployment/README.md)** - Complete deployment guide
- **[⚡ Quick Start](../docs/deployment/quick-start.md)** - Get running in 5 minutes
- **[✅ Deployment Checklist](../docs/deployment/deployment-checklist.md)** - Pre-deployment verification

### Deployment Methods
- **[🐳 Docker](docker/README.md)** - Containerized deployment (recommended for development)
- **[💻 Local Manual](local/README.md)** - Manual local development without Docker
- **[🐧 Linux Systemd](systemd/README.md)** - Production deployment on Linux servers
- **[🗄️ Database Setup](database/README.md)** - Neo4j, PostgreSQL, and Redis

### Configuration
- **[⚙️ Environment Variables](env/README.md)** - .env configuration templates
- **[🌐 Frontend Configuration](../docs/deployment/frontend-config.md)** - Frontend deployment

### Operations
- **[🔧 Troubleshooting](../docs/deployment/troubleshooting.md)** - Common issues and solutions
- **[📚 Operations Runbook](../docs/operations/runbook.md)** - Day-to-day operations

---

## Directory Structure

```
deployment/
├── docker/                    # Docker & Docker Compose files
│   ├── Dockerfile             # Production multi-stage build
│   ├── Dockerfile.dev         # Development with hot reload
│   ├── docker-compose.yml     # Full development stack
│   ├── docker-compose.prod.yml # Production backend
│   ├── .dockerignore          # Docker build exclusions
│   └── README.md              # Docker deployment guide
│
├── local/                     # Manual local deployment
│   ├── start_servers.sh       # Start backend & frontend
│   ├── stop_servers.sh        # Stop all servers
│   └── README.md              # Local deployment guide
│
├── database/                  # Database management
│   ├── init/                  # Initialization scripts
│   │   ├── neo4j-init.cypher  # Neo4j schema & indexes
│   │   ├── postgres-init.sql  # PostgreSQL tables & views
│   │   └── redis-init.sh      # Redis configuration
│   ├── migrations/            # Schema migrations
│   │   └── README.md          # Migration procedures
│   ├── backups/               # Backup & restore scripts
│   │   ├── backup.sh          # Automated backup script
│   │   └── restore.sh         # Restore from backup
│   └── README.md              # Database documentation
│
├── systemd/                   # Linux systemd deployment
│   ├── deploy.sh              # Automated deployment script
│   ├── esab-recommender.service         # Backend service
│   ├── esab-recommender-frontend.service # Frontend service
│   ├── esab-recommender.target          # Combined target
│   └── README.md              # Systemd deployment guide
│
├── env/                       # Environment configuration
│   ├── .env.example           # Complete template
│   ├── .env.development.example # Development config
│   ├── .env.production.example  # Production config
│   └── README.md              # Environment guide
│
└── README.md                  # This file (overview)
```

---

## Quick Start

### Docker (Development)

```bash
# 1. Configure environment
cp deployment/env/.env.development.example src/backend/.env
# Edit and add OPENAI_API_KEY

# 2. Start all services
cd deployment/docker
docker-compose up -d

# 3. Verify
curl http://localhost:8000/health
```

**See**: [Docker deployment guide](docker/README.md)

### Local Manual (Development)

```bash
# 1. Setup backend
cd src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# 2. Configure environment
cp deployment/env/.env.development.example src/backend/.env
# Edit and add OPENAI_API_KEY

# 3. Start services (requires local Neo4j, PostgreSQL, Redis)
./deployment/local/start_servers.sh

# 4. Verify
curl http://localhost:8000/health
```

**See**: [Local deployment guide](local/README.md)

### Linux Systemd (Production)

```bash
# 1. Transfer files to server
rsync -avz ./ user@server:/tmp/esab-recommender/

# 2. Run deployment script
ssh user@server
cd /tmp/esab-recommender
sudo ./deployment/systemd/deploy.sh install

# 3. Configure environment
nano /home/azureuser/esab_recommender-bh/src/backend/.env

# 4. Start services
sudo systemctl start esab-recommender.target
```

**See**: [Linux systemd guide](systemd/README.md)

---

## System Requirements

### Development
- Docker & Docker Compose
- 4GB RAM minimum
- 10GB disk space

### Production
- Ubuntu 20.04+ or CentOS 8+
- Python 3.11+
- 8GB RAM (4GB minimum)
- 4 CPU cores (2 minimum)
- 50GB disk space

---

## Required Services

| Service | Development | Production |
|---------|-------------|------------|
| **Neo4j** | Docker container | Neo4j Aura or self-hosted |
| **PostgreSQL** | Docker container | Managed service or self-hosted |
| **Redis** | Docker container | Azure Cache or self-hosted |
| **OpenAI API** | API key required | API key required |

**See**: [Database setup guide](database/README.md)

---

## Environment Configuration

All deployment methods require environment variables:

```bash
# Copy appropriate template
cp deployment/env/.env.development.example src/backend/.env  # Development
cp deployment/env/.env.production.example src/backend/.env   # Production

# Edit and configure
nano src/backend/.env
```

**Required variables**:
- `OPENAI_API_KEY` - OpenAI API key
- `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` - Neo4j connection
- `POSTGRES_HOST`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - PostgreSQL config
- `REDIS_HOST`, `REDIS_PASSWORD` - Redis config
- `SECRET_KEY`, `JWT_SECRET_KEY` - Application secrets

**See**: [Environment configuration guide](env/README.md)

---

## Common Operations

### Start Services

**Docker**:
```bash
cd deployment/docker && docker-compose up -d
```

**Systemd**:
```bash
sudo systemctl start esab-recommender.target
```

### Stop Services

**Docker**:
```bash
docker-compose down
```

**Systemd**:
```bash
sudo systemctl stop esab-recommender.target
```

### View Logs

**Docker**:
```bash
docker-compose logs -f backend
```

**Systemd**:
```bash
tail -f /home/azureuser/esab_recommender-bh/logs/esab-recommender.log
```

### Health Check

```bash
curl http://localhost:8000/health
```

**See**: [Operations runbook](../docs/operations/runbook.md)

---

## Backup and Restore

### Run Backup

```bash
cd deployment/database/backups
./backup.sh
```

### Restore from Backup

```bash
# List available backups
./restore.sh

# Restore specific backup
./restore.sh 20250115_143022
```

**See**: [Database backup guide](database/README.md#backup--restore)

---

## Troubleshooting

For common issues and solutions, see:
- **[Troubleshooting Guide](../docs/deployment/troubleshooting.md)**
- **[Docker Issues](docker/README.md#troubleshooting)**
- **[Systemd Issues](systemd/README.md#troubleshooting)**
- **[Database Issues](database/README.md#troubleshooting)**

---

## Security

### Production Checklist

- [ ] Use strong passwords (20+ characters)
- [ ] Generate random SECRET_KEY and JWT_SECRET_KEY
- [ ] Enable firewall (ports 22, 80, 443 only)
- [ ] Use HTTPS with SSL/TLS certificates
- [ ] Run behind reverse proxy (Nginx)
- [ ] Disable debug mode (`DEBUG=false`)
- [ ] Setup log rotation
- [ ] Configure regular backups

**See**: [Deployment checklist](../docs/deployment/deployment-checklist.md)

---

## Support and Documentation

### Documentation

- **[Deployment Docs](../docs/deployment/)** - Complete deployment documentation
- **[Operations Docs](../docs/operations/)** - Operations and maintenance
- **[CLAUDE.md](../CLAUDE.md)** - Project architecture and development

### Component-Specific Guides

- **[Docker README](docker/README.md)** - Docker deployment details
- **[Systemd README](systemd/README.md)** - Linux systemd details
- **[Database README](database/README.md)** - Database setup and management
- **[Environment README](env/README.md)** - Environment configuration

### Getting Help

1. Check **[Troubleshooting Guide](../docs/deployment/troubleshooting.md)**
2. Review logs for errors
3. Verify environment configuration
4. Check database connectivity
5. Review **[Operations Runbook](../docs/operations/runbook.md)**

---

## Version Information

- **Application**: ESAB Recommender V2
- **Python**: 3.11+ (3.12+ supported)
- **FastAPI**: 0.104.1+
- **Neo4j**: 5.14+
- **PostgreSQL**: 12+
- **Redis**: 5.0+

---

## Next Steps

1. **Choose deployment method**:
   - Development: [Docker](docker/README.md)
   - Production: [Linux Systemd](systemd/README.md)

2. **Follow guides**:
   - [Quick Start](../docs/deployment/quick-start.md)
   - [Deployment Checklist](../docs/deployment/deployment-checklist.md)

3. **Configure databases**:
   - [Database Setup](database/README.md)
   - [Environment Configuration](env/README.md)

4. **Deploy and operate**:
   - [Operations Runbook](../docs/operations/runbook.md)
   - [Troubleshooting](../docs/deployment/troubleshooting.md)

---

**For detailed deployment documentation, see [docs/deployment/README.md](../docs/deployment/README.md)**
