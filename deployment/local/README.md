# Local Manual Deployment

Scripts for running ESAB Recommender V2 locally without Docker.

## Overview

This deployment method runs the backend and frontend directly on your local machine using native Python and HTTP servers. It's ideal for:

- **Development without Docker**
- **Debugging with full IDE integration**
- **Quick local testing**
- **Learning the application architecture**

**Ports**:
- Backend API: `8000`
- Frontend (optional): `3000`

---

## Prerequisites

### Required Software

- **Python 3.11+** (verify: `python3 --version`)
- **pip** (Python package manager)
- **Git** (for cloning repository)

### Required Services

You need to have these databases running locally or accessible remotely:

1. **Neo4j** - Port 7474 (HTTP), 7687 (Bolt)
   - [Neo4j Desktop](https://neo4j.com/download/) (easiest for development)
   - Or Neo4j Aura (cloud)

2. **PostgreSQL** - Port 5432
   ```bash
   # macOS
   brew install postgresql
   brew services start postgresql

   # Ubuntu/Debian
   sudo apt-get install postgresql
   sudo systemctl start postgresql

   # Windows
   # Download from https://www.postgresql.org/download/
   ```

3. **Redis** - Port 6379 (optional but recommended)
   ```bash
   # macOS
   brew install redis
   brew services start redis

   # Ubuntu/Debian
   sudo apt-get install redis-server
   sudo systemctl start redis

   # Windows
   # Use WSL or download from https://redis.io/download
   ```

### API Keys

- **OpenAI API Key** - Get from [OpenAI Platform](https://platform.openai.com/api-keys)

---

## Quick Start

### 1. Clone Repository (if not already done)

```bash
git clone <repository-url>
cd esab-recommender-v2
```

### 2. Setup Backend

```bash
# Navigate to backend directory
cd src/backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate     # Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Deactivate (we'll use the scripts to run)
deactivate
```

### 3. Configure Environment

```bash
# Copy environment template
cp deployment/env/.env.development.example src/backend/.env

# Edit configuration
nano src/backend/.env  # or use your preferred editor
```

**Minimal required configuration**:
```env
# OpenAI (required)
OPENAI_API_KEY=sk-proj-your-actual-key-here

# Neo4j (adjust if different)
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password

# PostgreSQL (adjust if different)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pconfig
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_postgres_password

# Redis (adjust if different)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password  # or empty if no password

# Application secrets
SECRET_KEY=dev-secret-key-for-local-dev
JWT_SECRET_KEY=dev-jwt-secret-for-local-dev
```

### 4. Initialize Databases

```bash
# Initialize Neo4j
cypher-shell -u neo4j -p your_password -f deployment/database/init/neo4j-init.cypher

# Initialize PostgreSQL
psql -U postgres -d pconfig -f deployment/database/init/postgres-init.sql

# Initialize Redis (optional)
cd deployment/database/init
chmod +x redis-init.sh
./redis-init.sh
cd ../../..
```

### 5. Start Services

```bash
# From project root
cd deployment/local
chmod +x start_servers.sh stop_servers.sh
./start_servers.sh
```

### 6. Verify

```bash
# Check health
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "databases": {
#     "neo4j": "connected",
#     "postgresql": "connected",
#     "redis": "connected"
#   }
# }
```

### 7. Access Application

**Backend API**:
- API Documentation: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- ReDoc: http://localhost:8000/redoc

**Static Test Interfaces** (served by backend):
- Main Configurator: http://localhost:8000/static/index.html
- Test Configurator: http://localhost:8000/static/test_configurator.html
- Parameter Extraction: http://localhost:8000/static/test_extraction.html

**Frontend** (optional separate server):
- Frontend UI: http://localhost:3000

---

## Usage

### Start Servers

```bash
# From deployment/local/
./start_servers.sh

# Or from project root
./deployment/local/start_servers.sh
```

**What it does**:
1. Kills any existing processes on ports 8000 and 3000
2. Starts backend (uvicorn with auto-reload)
3. Starts frontend (Python HTTP server)
4. Displays access URLs and log locations

### Stop Servers

```bash
# From deployment/local/
./stop_servers.sh

# Or from project root
./deployment/local/stop_servers.sh
```

**What it does**:
1. Stops backend on port 8000
2. Stops frontend on port 3000
3. Cleans up any remaining processes

### View Logs

**Real-time logs**:
```bash
# Backend logs (from project root)
tail -f backend.log

# Frontend logs
tail -f frontend.log

# Both logs simultaneously
tail -f backend.log frontend.log
```

**Search logs**:
```bash
# Find errors
grep -i error backend.log

# Find specific endpoint calls
grep "POST /api/v1/configurator" backend.log
```

---

## Development Workflow

### Making Code Changes

The backend runs with `--reload` flag, so it automatically restarts when you change Python files:

```bash
# 1. Edit code in src/backend/
nano src/backend/app/services/orchestrator/state_orchestrator.py

# 2. Save file
# Backend automatically reloads (watch the logs)

# 3. Test changes
curl -X POST http://localhost:8000/api/v1/configurator/message \
  -H "Content-Type: application/json" \
  -d '{"message": "test", "language": "en"}'
```

### Adding Dependencies

```bash
# 1. Activate virtual environment
cd src/backend
source venv/bin/activate

# 2. Install new package
pip install <package-name>

# 3. Update requirements
pip freeze > requirements.txt

# 4. Deactivate
deactivate

# 5. Restart servers
cd ../../deployment/local
./stop_servers.sh
./start_servers.sh
```

### Running Tests

```bash
# Activate virtual environment
cd src/backend
source venv/bin/activate

# Run tests
pytest

# Run with coverage
pytest --cov=app tests/

# Deactivate
deactivate
```

---

## Configuration

### Environment Variables

Edit `src/backend/.env` to customize:

```env
# Application
DEBUG=true                    # Enable debug mode
HOST=0.0.0.0                  # Listen on all interfaces
PORT=8000                     # Backend port

# Database connections
NEO4J_URI=bolt://localhost:7687
POSTGRES_HOST=localhost
REDIS_HOST=localhost

# Features
ENABLE_REDIS_CACHING=true    # Use Redis for sessions
ENABLE_LANGGRAPH=false       # Enable LangGraph workflow
ENABLE_MULTILINGUAL=true     # Enable multilingual support

# Logging
LOG_LEVEL=DEBUG              # DEBUG, INFO, WARNING, ERROR
```

See [deployment/env/README.md](../env/README.md) for full configuration options.

### Database Connection Strings

**Local databases** (default):
```env
NEO4J_URI=bolt://localhost:7687
POSTGRES_HOST=localhost
REDIS_HOST=localhost
```

**Remote databases** (production/staging):
```env
NEO4J_URI=bolt+s://xxxxx.databases.neo4j.io
POSTGRES_HOST=your-postgres.database.azure.com
REDIS_HOST=your-redis.redis.cache.windows.net
```

---

## Troubleshooting

### Backend Won't Start

**Check virtual environment**:
```bash
# Verify venv exists
ls -la src/backend/venv/

# If missing, recreate
cd src/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

**Check .env file**:
```bash
# Verify .env exists
ls -la src/backend/.env

# If missing
cp deployment/env/.env.development.example src/backend/.env
```

**Check dependencies**:
```bash
cd src/backend
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # macOS/Linux

# Or use stop script
./deployment/local/stop_servers.sh
```

### Database Connection Errors

**Neo4j**:
```bash
# Test connection
cypher-shell -a bolt://localhost:7687 -u neo4j -p password "RETURN 1;"

# Start Neo4j (if using Neo4j Desktop)
# Open Neo4j Desktop and start database

# Check port
netstat -an | grep 7687
```

**PostgreSQL**:
```bash
# Test connection
psql -h localhost -U postgres -d pconfig -c "SELECT 1;"

# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql   # macOS

# Check port
netstat -an | grep 5432
```

**Redis**:
```bash
# Test connection
redis-cli -h localhost -p 6379 PING

# Start Redis
sudo systemctl start redis  # Linux
brew services start redis   # macOS

# Check port
netstat -an | grep 6379
```

### Frontend Issues

**Static files not loading from backend**:
```bash
# Verify files exist
ls -la src/*.html

# Test endpoint
curl -I http://localhost:8000/static/index.html

# Should return 200 OK
```

**Separate frontend server not working**:
```bash
# Verify directory exists
ls -la src/frontend/

# Manually test
cd src/frontend
python3 -m http.server 3000
```

### OpenAI API Errors

```bash
# Verify API key in .env
grep OPENAI_API_KEY src/backend/.env

# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_KEY_HERE"

# If invalid, get new key from:
# https://platform.openai.com/api-keys
```

---

## Comparison with Other Deployment Methods

| Feature | Local Manual | Docker | Systemd |
|---------|-------------|--------|---------|
| **Setup Time** | Medium | Fast | Slow |
| **Best For** | Development | Development | Production |
| **Isolation** | None | Full | Partial |
| **Performance** | Native | Slight overhead | Native |
| **Debugging** | Easy | Medium | Hard |
| **Auto-reload** | Yes (--reload) | Yes (volume mount) | No |
| **Database Setup** | Manual | Automatic | Manual |
| **Portability** | Low | High | Medium |

---

## Scripts Reference

### start_servers.sh

**Location**: `deployment/local/start_servers.sh`

**What it does**:
1. Stops existing processes on ports 8000 and 3000
2. Starts backend with uvicorn (auto-reload enabled)
3. Starts frontend with Python HTTP server
4. Outputs access URLs and log locations

**Usage**:
```bash
./deployment/local/start_servers.sh
```

**Options** (edit script to customize):
- Workers: Default is 1 (for development). Change `--workers` flag for production.
- Host: Default is `0.0.0.0`. Change `--host` to restrict access.
- Port: Default is 8000. Change `--port` for different port.

### stop_servers.sh

**Location**: `deployment/local/stop_servers.sh`

**What it does**:
1. Finds processes on ports 8000 and 3000
2. Kills processes gracefully
3. Cleans up any remaining uvicorn/http.server processes

**Usage**:
```bash
./deployment/local/stop_servers.sh
```

---

## Advanced Usage

### Running in Production Mode

Edit `start_servers.sh` to remove `--reload`:

```bash
# Change this line:
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ...

# To this:
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 > ...
```

**Note**: For actual production, use [systemd deployment](../systemd/README.md) instead.

### Custom Ports

Edit `start_servers.sh`:

```bash
# Backend on port 9000
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload > ...

# Frontend on port 3001
nohup python3 -m http.server 3001 > ...
```

Also update `stop_servers.sh` to match the new ports.

### Background Execution

Scripts already use `nohup` and `&` for background execution. Logs are written to:
- `backend.log` (in project root)
- `frontend.log` (in project root)

### Monitoring

```bash
# Check if processes are running
ps aux | grep uvicorn
ps aux | grep "http.server"

# Check ports
netstat -an | grep -E "(8000|3000)"

# Monitor logs in real-time
tail -f backend.log frontend.log
```

---

## See Also

- **[Deployment Overview](../README.md)** - All deployment methods
- **[Docker Deployment](../docker/README.md)** - Containerized development
- **[Systemd Deployment](../systemd/README.md)** - Production Linux deployment
- **[Environment Configuration](../env/README.md)** - .env file setup
- **[Database Setup](../database/README.md)** - Database initialization
- **[Quick Start Guide](../../docs/deployment/quick-start.md)** - 5-minute setup
- **[Troubleshooting](../../docs/deployment/troubleshooting.md)** - Common issues

---

## Need Help?

1. **Check logs**: `tail -f backend.log`
2. **Verify databases**: Test each database connection
3. **Check environment**: Verify `.env` file is correct
4. **Review documentation**: See links above
5. **Common issues**: [Troubleshooting guide](../../docs/deployment/troubleshooting.md)
