# Quick Start Guide for Aynalinux Server Deployment

This guide provides exact commands for deploying to your server at `/home/Aynalinux/project/ayna-pod-recommender`.

## Current Situation

Your server:
- **Path**: `/home/Aynalinux/project/ayna-pod-recommender`
- **User**: `Aynalinux`
- **Issue**: Backend service not starting (port 8000 not listening)
- **Root Cause**: Hardcoded paths pointing to `/home/azureuser/esab_recommender-bh`

## Solution: Updated Deployment with Dynamic Paths

The deployment scripts have been updated to auto-detect paths. Follow these steps:

---

## Step 1: Update Repository on Server

SSH into your server and update the code:

```bash
ssh Aynalinux@Aynalinux

cd /home/Aynalinux/project/ayna-pod-recommender

# Pull latest changes (includes dynamic path detection)
git pull origin main
# Or if you copied files manually, ensure you have latest deploy.sh
```

---

## Step 2: Stop Existing Services

```bash
# Stop any running services
sudo systemctl stop esab-recommender.target
sudo systemctl stop esab-recommender.service
sudo systemctl stop esab-recommender-frontend.service

# Verify stopped
sudo systemctl status esab-recommender.service
```

---

## Step 3: Remove Old Service Files (Optional but Recommended)

This ensures no conflicts with hardcoded paths:

```bash
# Remove old service files
sudo rm -f /etc/systemd/system/esab-recommender.service
sudo rm -f /etc/systemd/system/esab-recommender-frontend.service
sudo rm -f /etc/systemd/system/esab-recommender.target

# Reload systemd
sudo systemctl daemon-reload
```

---

## Step 4: Run Deployment Script

The script will auto-detect your paths:

```bash
cd /home/Aynalinux/project/ayna-pod-recommender

# Make script executable
chmod +x deployment/systemd/deploy.sh

# Run installation (or reinstall)
sudo ./deployment/systemd/deploy.sh install
```

**Expected Output:**
```
=== Detected Configuration ===
Repository Root: /home/Aynalinux/project/ayna-pod-recommender
Installation Directory: /home/Aynalinux/project/ayna-pod-recommender
Application User: Aynalinux
Application Group: Aynalinux
Backend Directory: /home/Aynalinux/project/ayna-pod-recommender/src/backend
Log Directory: /home/Aynalinux/project/ayna-pod-recommender/logs
==============================

[INFO] User Aynalinux exists ✓
[INFO] Source directory exists ✓
[INFO] Creating log directory...
[INFO] Creating Python virtual environment...
...
```

The script will:
1. ✅ Detect your installation path automatically
2. ✅ Detect your username (Aynalinux)
3. ✅ Create logs directory if it doesn't exist
4. ✅ Create or reuse existing virtual environment
5. ✅ Install Python dependencies
6. ✅ Generate service files with YOUR paths (not hardcoded ones)
7. ✅ Install and enable systemd services

---

## Step 5: Configure Environment (if needed)

If `.env` file doesn't exist or needs updating:

```bash
# Check if .env exists
ls -la /home/Aynalinux/project/ayna-pod-recommender/src/backend/.env

# If missing, create from template
cp deployment/env/.env.production.example src/backend/.env

# Edit with your configuration
nano src/backend/.env
```

Required variables:
```ini
# OpenAI
OPENAI_API_KEY=sk-...

# Neo4j
NEO4J_URI=neo4j://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=pconfig
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-password
ENABLE_REDIS_CACHING=true

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here
```

---

## Step 6: Start Services

```bash
# Start both backend and frontend
sudo systemctl start esab-recommender.target

# Check status
sudo systemctl status esab-recommender.target
sudo systemctl status esab-recommender.service
sudo systemctl status esab-recommender-frontend.service
```

---

## Step 7: Verify Deployment

### Check if port 8000 is listening:

```bash
sudo lsof -i :8000
# Should show uvicorn process
```

### Check logs:

```bash
# View application logs
tail -f /home/Aynalinux/project/ayna-pod-recommender/logs/esab-recommender.log

# View error logs
tail -f /home/Aynalinux/project/ayna-pod-recommender/logs/esab-recommender-error.log

# View systemd journal
sudo journalctl -u esab-recommender.service -f
```

### Test health endpoint:

```bash
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "database": {
    "neo4j": "connected",
    "postgres": "connected",
    "redis": "connected"
  },
  "version": "2.0"
}
```

### Test API:

```bash
curl -X POST http://localhost:8000/api/v1/configurator/message \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I need a 500A MIG welder",
    "language": "en"
  }'
```

---

## Step 8: Enable Auto-Start on Boot

```bash
# Enable services to start on server boot
sudo systemctl enable esab-recommender.target
sudo systemctl enable esab-recommender.service
sudo systemctl enable esab-recommender-frontend.service
```

---

## Common Commands for Management

```bash
# View logs from deploy script
sudo ./deployment/systemd/deploy.sh logs

# Restart services
sudo systemctl restart esab-recommender.target

# Stop services
sudo systemctl stop esab-recommender.target

# Check status
sudo ./deployment/systemd/deploy.sh status

# View detailed status
sudo systemctl status esab-recommender.service -l --no-pager
```

---

## Troubleshooting

### Issue 1: Service shows "Started" but no logs

**Diagnosis:**
```bash
# Check if process is running
sudo lsof -i :8000

# Check for Python errors
sudo journalctl -u esab-recommender.service -n 100 --no-pager

# Check file permissions
ls -la /home/Aynalinux/project/ayna-pod-recommender/src/backend/
```

**Common causes:**
- Missing .env file
- Wrong file permissions
- Virtual environment missing or broken
- Missing Python dependencies

**Solution:**
```bash
# Verify venv exists and works
cd /home/Aynalinux/project/ayna-pod-recommender/src/backend
ls -la venv/bin/uvicorn
./venv/bin/python --version

# Verify .env exists
ls -la .env

# Try manual start to see errors
source venv/bin/activate
python -m app.main
deactivate
```

### Issue 2: Logs directory not created

**Solution:**
```bash
# Manually create logs directory
mkdir -p /home/Aynalinux/project/ayna-pod-recommender/logs

# Set permissions
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender/logs

# Restart service
sudo systemctl restart esab-recommender.service
```

### Issue 3: Permission denied errors

**Solution:**
```bash
# Fix ownership of entire directory
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender

# Make sure .env is readable by service
chmod 600 /home/Aynalinux/project/ayna-pod-recommender/src/backend/.env
```

### Issue 4: Database connection errors

**Check database services:**
```bash
# Check PostgreSQL
sudo systemctl status postgresql
psql -U postgres -d pconfig -c "SELECT 1;"

# Check Redis
sudo systemctl status redis
redis-cli ping

# Check Neo4j (if local)
sudo systemctl status neo4j
# Or check Neo4j Aura dashboard if using cloud
```

---

## Verification Checklist

After deployment, verify:

- [ ] Service files have correct paths:
  ```bash
  cat /etc/systemd/system/esab-recommender.service | grep "WorkingDirectory"
  # Should show: /home/Aynalinux/project/ayna-pod-recommender/src/backend
  ```

- [ ] Port 8000 is listening:
  ```bash
  sudo lsof -i :8000
  ```

- [ ] Logs directory exists and has files:
  ```bash
  ls -la /home/Aynalinux/project/ayna-pod-recommender/logs/
  ```

- [ ] Health endpoint responds:
  ```bash
  curl http://localhost:8000/health
  ```

- [ ] Services are enabled:
  ```bash
  systemctl is-enabled esab-recommender.service
  ```

---

## Success Indicators

You'll know it's working when:

1. ✅ `sudo lsof -i :8000` shows uvicorn process
2. ✅ `curl http://localhost:8000/health` returns JSON
3. ✅ Logs are being written to `logs/esab-recommender.log`
4. ✅ `sudo systemctl status esab-recommender.service` shows "active (running)"
5. ✅ No errors in `sudo journalctl -u esab-recommender.service -n 50`

---

## Next Steps After Successful Deployment

1. **Test the configurator**: Access http://your-server-ip:8000/docs
2. **Test frontend**: Access http://your-server-ip:3000/frontend/
3. **Monitor logs**: Keep `tail -f logs/esab-recommender.log` running in a separate terminal
4. **Set up monitoring**: Configure alerting for service failures
5. **Backup configuration**: Save your `.env` file securely

---

## Quick Reference: File Paths

Your deployment uses these paths:

| Component | Path |
|-----------|------|
| Repository Root | `/home/Aynalinux/project/ayna-pod-recommender` |
| Backend Code | `/home/Aynalinux/project/ayna-pod-recommender/src/backend` |
| Frontend Code | `/home/Aynalinux/project/ayna-pod-recommender/src/frontend` |
| Virtual Environment | `/home/Aynalinux/project/ayna-pod-recommender/src/backend/venv` |
| Environment Config | `/home/Aynalinux/project/ayna-pod-recommender/src/backend/.env` |
| Application Logs | `/home/Aynalinux/project/ayna-pod-recommender/logs/` |
| Systemd Services | `/etc/systemd/system/esab-recommender*.service` |

---

**Deployment Date**: 2025-11-06
**Server**: Aynalinux@Aynalinux
**Installation Path**: `/home/Aynalinux/project/ayna-pod-recommender`
**User**: `Aynalinux`
