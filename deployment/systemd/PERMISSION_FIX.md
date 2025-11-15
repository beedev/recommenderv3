# Permission Error Fix - Quick Reference

## Issue
```
PermissionError: [Errno 13] Permission denied: '/home/Aynalinux/project/ayna-pod-recommender/logs/esab-recommender.log'
```

## Root Cause
The logs directory was created by `root` (during sudo deployment) but the application runs as user `Aynalinux`.

## Quick Fix

Run these commands on your server:

```bash
# Fix logs directory ownership
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender/logs

# Set correct permissions
chmod 755 /home/Aynalinux/project/ayna-pod-recommender/logs

# Also fix entire repository (recommended)
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender

# Restart service
sudo systemctl restart esab-recommender.service

# Verify it's running
sudo systemctl status esab-recommender.service
sudo lsof -i :8000
```

## Verification

Check that logs are being written:

```bash
# Check log file exists and has content
ls -la /home/Aynalinux/project/ayna-pod-recommender/logs/
tail -f /home/Aynalinux/project/ayna-pod-recommender/logs/esab-recommender.log
```

Expected output:
```
-rw-r--r-- 1 Aynalinux Aynalinux <size> <date> esab-recommender.log
```

## Prevention

The updated `deploy.sh` script now automatically sets correct ownership. Future deployments will not have this issue.

If you re-run deployment:
```bash
cd /home/Aynalinux/project/ayna-pod-recommender
sudo ./deployment/systemd/deploy.sh install
```

The script will now:
1. Create logs directory
2. Set ownership to `Aynalinux:Aynalinux`
3. Set permissions to `755`

## Understanding the Issue

**Systemd Service Configuration:**
```ini
[Service]
User=Aynalinux              ← Service runs as this user
Group=Aynalinux
ReadWritePaths=/home/Aynalinux/project/ayna-pod-recommender/logs  ← Only this path is writable
```

**Problem:**
- Deploy script runs as `root` (via sudo)
- Creates logs directory owned by `root:root`
- Application runs as `Aynalinux`
- Cannot write to `root`-owned directory

**Solution:**
- Explicitly set ownership to `Aynalinux:Aynalinux` after creating directory
- Updated deploy script does this automatically

## Related Errors

If you see any of these errors, use the same fix:

```
OSError: [Errno 13] Permission denied
PermissionError: [Errno 13]
FileNotFoundError: [Errno 2] No such file or directory: '/home/.../logs/...'
```

## Additional Tips

**Check ownership of any directory:**
```bash
ls -la /home/Aynalinux/project/ayna-pod-recommender/
```

Look for directories/files owned by `root` that the application needs to write to.

**Fix ownership recursively:**
```bash
# Fix entire project
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender

# Fix specific directories
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender/logs
sudo chown -R Aynalinux:Aynalinux /home/Aynalinux/project/ayna-pod-recommender/src/backend
```

**Check current permissions:**
```bash
# Show permissions for logs directory
ls -ld /home/Aynalinux/project/ayna-pod-recommender/logs

# Show permissions for log file
ls -l /home/Aynalinux/project/ayna-pod-recommender/logs/esab-recommender.log
```

## Expected Permissions

After fix, you should see:

```bash
$ ls -ld /home/Aynalinux/project/ayna-pod-recommender/logs
drwxr-xr-x 2 Aynalinux Aynalinux 4096 Nov  6 12:00 logs

$ ls -l /home/Aynalinux/project/ayna-pod-recommender/logs/
-rw-r--r-- 1 Aynalinux Aynalinux 12345 Nov  6 12:00 esab-recommender.log
```

Key points:
- ✅ Owner: `Aynalinux`
- ✅ Group: `Aynalinux`
- ✅ Directory permissions: `755` (rwxr-xr-x)
- ✅ File permissions: `644` (rw-r--r--)

---

**Issue Date**: 2025-11-06
**Fix**: Set correct ownership with `chown -R Aynalinux:Aynalinux`
**Prevention**: Updated deploy.sh automatically sets ownership
