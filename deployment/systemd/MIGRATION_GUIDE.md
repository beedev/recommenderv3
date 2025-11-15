# Dynamic Path Detection Migration Guide

## What Changed?

The systemd deployment scripts have been updated to **automatically detect installation paths** instead of using hardcoded values. This allows the application to be deployed anywhere on your system without manual path configuration.

## Previous Behavior (Hardcoded Paths)

**Before**, the deployment scripts had hardcoded paths:
- Installation directory: `/home/azureuser/esab_recommender-bh/`
- User: `azureuser`
- Group: `azureuser`

This meant:
- ❌ Only worked if installed to exact path
- ❌ Only worked with `azureuser` user
- ❌ Required manual editing of service files to use different paths
- ❌ Error-prone when deploying to different environments

## New Behavior (Dynamic Detection)

**Now**, the deployment script automatically detects:
- ✅ Installation directory from script location
- ✅ Application user from current sudo user or logged-in user
- ✅ All paths are calculated dynamically at installation time
- ✅ No hardcoded paths - works anywhere on your system

## How It Works

### 1. Path Detection

When you run the script, it automatically detects:

```bash
cd /home/Aynalinux/project/ayna-pod-recommender
sudo ./deployment/systemd/deploy.sh install
```

The script will display:
```
=== Detected Configuration ===
Repository Root: /home/Aynalinux/project/ayna-pod-recommender
Installation Directory: /home/Aynalinux/project/ayna-pod-recommender
Application User: Aynalinux
Application Group: Aynalinux
Backend Directory: /home/Aynalinux/project/ayna-pod-recommender/src/backend
Log Directory: /home/Aynalinux/project/ayna-pod-recommender/logs
==============================
```

### 2. Service File Generation

Instead of copying static service files, the script now **generates** service files with your detected paths:

```bash
# Old approach (static file with hardcoded paths)
cp esab-recommender.service /etc/systemd/system/

# New approach (generated file with your paths)
generate_service_files()  # Creates files dynamically
cp /tmp/esab-recommender.service /etc/systemd/system/
```

### 3. Template Files

The service files in the repository (`esab-recommender.service` and `esab-recommender-frontend.service`) are now **templates** with placeholder paths:

```ini
# TEMPLATE FILE - DO NOT COPY DIRECTLY
User=<PLACEHOLDER_USER>
WorkingDirectory=<PLACEHOLDER_BACKEND_DIR>
```

**Important**: Never copy these template files directly to `/etc/systemd/system/`. Always use the deploy script.

## Migration for Existing Deployments

If you have an existing deployment with hardcoded paths, here's how to migrate:

### Option 1: Fresh Install (Recommended)

If your deployment is at a different path than before:

```bash
# 1. Stop existing services
sudo systemctl stop esab-recommender.target

# 2. Navigate to your repository
cd /home/Aynalinux/project/ayna-pod-recommender

# 3. Pull latest changes
git pull

# 4. Run deploy script (it will detect new paths)
sudo ./deployment/systemd/deploy.sh install

# 5. Verify detected configuration
# The script will show your actual paths

# 6. Start services
sudo systemctl start esab-recommender.target
```

### Option 2: Update Existing Deployment

If your deployment is already in the correct location:

```bash
# 1. Navigate to your repository
cd /home/Aynalinux/project/ayna-pod-recommender

# 2. Pull latest changes
git pull

# 3. Run update command (preserves .env)
sudo ./deployment/systemd/deploy.sh update

# The script will:
# - Detect your current installation directory
# - Regenerate service files with correct paths
# - Update dependencies
# - Restart services
```

### Option 3: Manual Regeneration

If you want to regenerate service files without full reinstall:

```bash
# 1. Stop services
sudo systemctl stop esab-recommender.target

# 2. Remove old service files
sudo rm /etc/systemd/system/esab-recommender.service
sudo rm /etc/systemd/system/esab-recommender-frontend.service

# 3. Navigate to repository
cd /home/Aynalinux/project/ayna-pod-recommender

# 4. Run install (will detect existing venv)
sudo ./deployment/systemd/deploy.sh install

# 5. Start services
sudo systemctl start esab-recommender.target
```

## Troubleshooting

### Issue: Service won't start after migration

**Problem**: Old service files still in `/etc/systemd/system/` with hardcoded paths

**Solution**:
```bash
# Check which service files are installed
ls -la /etc/systemd/system/esab-recommender*

# View content to check paths
cat /etc/systemd/system/esab-recommender.service | grep WorkingDirectory

# If paths are wrong, regenerate
sudo systemctl stop esab-recommender.target
sudo rm /etc/systemd/system/esab-recommender*.service
cd /path/to/your/repository
sudo ./deployment/systemd/deploy.sh install
```

### Issue: Logs directory not created

**Problem**: New dynamic path not recognized

**Solution**:
```bash
# Check detected configuration
cd /path/to/your/repository
sudo ./deployment/systemd/deploy.sh install

# Look for "Detected Configuration" output
# Verify log directory was created
ls -la logs/
```

### Issue: Application user mismatch

**Problem**: Script detects wrong user

**Solution**: The script uses `$SUDO_USER` (the user who ran sudo). If this is incorrect, you can override:

```bash
# Edit deploy.sh temporarily
nano deployment/systemd/deploy.sh

# Find this line:
APP_USER="${SUDO_USER:-$(whoami)}"

# Change to:
APP_USER="your-correct-username"

# Run deployment
sudo ./deployment/systemd/deploy.sh install
```

Or create a wrapper script:
```bash
#!/bin/bash
export SUDO_USER="your-correct-username"
sudo -E ./deployment/systemd/deploy.sh install
```

### Issue: Permission denied errors

**Problem**: User doesn't have access to detected directory

**Solution**:
```bash
# Verify ownership of repository
ls -la /path/to/your/repository

# Fix ownership if needed
sudo chown -R your-user:your-user /path/to/your/repository

# Run deployment again
cd /path/to/your/repository
sudo ./deployment/systemd/deploy.sh install
```

## Benefits of Dynamic Paths

1. **Flexibility**: Deploy to any directory (`/opt/`, `/home/`, `/srv/`, etc.)
2. **Multi-user**: Works with any Linux user, not just `azureuser`
3. **Multi-environment**: Same scripts work for dev, staging, production
4. **No manual editing**: No need to edit service files manually
5. **Consistent**: Eliminates path mismatch errors
6. **Portable**: Easy to move installations or migrate servers

## Verification

After migration, verify everything is working:

```bash
# 1. Check service files have correct paths
cat /etc/systemd/system/esab-recommender.service | grep WorkingDirectory
cat /etc/systemd/system/esab-recommender.service | grep ExecStart

# 2. Check services are running
sudo systemctl status esab-recommender.target
sudo systemctl status esab-recommender.service

# 3. Check logs directory exists
ls -la logs/

# 4. Check application responds
curl http://localhost:8000/health

# 5. Check logs are being written
tail -f logs/esab-recommender.log
```

## Need Help?

If you encounter issues after migration:

1. Check the troubleshooting section above
2. Review deployment logs: `sudo journalctl -u esab-recommender.service -n 100`
3. Verify path detection: Run `sudo ./deployment/systemd/deploy.sh install` and check "Detected Configuration" output
4. Check file permissions: `ls -la /path/to/your/repository`
5. Verify .env file exists: `ls -la src/backend/.env`

## Summary

**Key Takeaway**: Always use `sudo ./deployment/systemd/deploy.sh install` from within your repository. The script will automatically detect and configure everything correctly - no manual path configuration needed!

---

**Migration Date**: 2025-11-06
**Version**: 2.0+
**Breaking Change**: Yes - service template files now use placeholders instead of hardcoded paths
