# RedisInsight Access Issue - Quick Fix Guide

## Problem
Cannot access RedisInsight on port 8001 from outside Docker

## Quick Diagnosis Commands

Run these on your server:

```bash
# 1. Check if container is running
docker ps | grep redisinsight

# 2. Check port mapping
docker port esab-redisinsight-prod

# 3. Check logs
docker logs esab-redisinsight-prod --tail 50

# 4. Test from localhost
curl http://localhost:8001

# 5. Check what's listening on port 8001
sudo netstat -tlnp | grep 8001
# OR
sudo ss -tlnp | grep 8001
```

---

## Common Issues & Solutions

### Issue 1: Container Not Running

**Check:**
```bash
docker ps -a | grep redisinsight
```

**Fix:**
```bash
cd ~/project/ayna-pod-recommender/deployment/docker
docker-compose -f docker-compose.prod.yml start redisinsight

# Or recreate it
docker-compose -f docker-compose.prod.yml up -d redisinsight
```

---

### Issue 2: Port Bound to 127.0.0.1 Only

**Check:**
```bash
docker inspect esab-redisinsight-prod | grep -A 10 '"Ports"'
```

If you see `"HostIp": "127.0.0.1"`, the port is only accessible from localhost.

**Fix:** Update `docker-compose.prod.yml`:

**Before:**
```yaml
redisinsight:
  ports:
    - "${REDISINSIGHT_PORT:-8001}:8001"
```

**After:**
```yaml
redisinsight:
  ports:
    - "0.0.0.0:8001:8001"  # Explicitly bind to all interfaces
```

Then restart:
```bash
docker-compose -f docker-compose.prod.yml down redisinsight
docker-compose -f docker-compose.prod.yml up -d redisinsight
```

---

### Issue 3: Firewall Blocking Port

**Check Ubuntu/UFW:**
```bash
sudo ufw status
```

**Fix:**
```bash
sudo ufw allow 8001/tcp
sudo ufw reload
```

**Check CentOS/RHEL/Firewalld:**
```bash
sudo firewall-cmd --list-ports
```

**Fix:**
```bash
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload
```

---

### Issue 4: Cloud Provider Security Group

If you're on AWS, Azure, or GCP, you need to allow inbound traffic on port 8001:

**AWS:**
- EC2 → Security Groups → Select your instance's security group
- Inbound rules → Add rule
- Type: Custom TCP, Port: 8001, Source: Your IP or 0.0.0.0/0

**Azure:**
- Virtual Machines → Networking → Add inbound port rule
- Port: 8001, Protocol: TCP

**GCP:**
- VPC Network → Firewall → Create firewall rule
- Targets: All instances, TCP: 8001, Source IP ranges: 0.0.0.0/0

---

### Issue 5: RedisInsight Service Not Starting

**Check logs:**
```bash
docker logs esab-redisinsight-prod
```

**Common fixes:**
```bash
# Clear data and restart
docker-compose -f docker-compose.prod.yml down redisinsight
docker volume rm esab-redisinsight-data-prod
docker-compose -f docker-compose.prod.yml up -d redisinsight

# Wait for startup
sleep 10
docker logs esab-redisinsight-prod
```

---

## Access Methods

### Method 1: Direct Access (requires firewall/security group configured)
```
http://YOUR_SERVER_IP:8001
```

### Method 2: SSH Tunnel (most secure)
From your local machine:
```bash
ssh -L 8001:localhost:8001 user@YOUR_SERVER_IP
```
Then open in browser: `http://localhost:8001`

### Method 3: Via Reverse Proxy (Nginx/Apache)
Set up a reverse proxy with SSL if you want HTTPS access.

---

## Verification Steps

After applying fixes:

```bash
# 1. Container is running
docker ps | grep redisinsight

# 2. Port is listening
sudo ss -tlnp | grep :8001

# 3. Can connect locally
curl -I http://localhost:8001

# 4. Test from your local machine
curl -I http://YOUR_SERVER_IP:8001
```

Expected response:
```
HTTP/1.1 200 OK
# or
HTTP/1.1 302 Found
```

---

## Connect RedisInsight to Your Redis

Once you can access RedisInsight:

1. Open http://YOUR_SERVER_IP:8001
2. Click "Add Redis Database"
3. Enter:
   - **Host:** `redis` (or `esab-redis-prod`)
   - **Port:** `6379`
   - **Database Alias:** `ESAB Redis`
   - **Password:** `esab_redis_prod_password`
4. Click "Add Redis Database"

---

## Security Considerations

If exposing port 8001 to the internet:

1. **Use strong passwords** for Redis
2. **Restrict IP access** in firewall (only your IP)
3. **Use SSH tunnel** instead of direct access
4. **Set up reverse proxy** with authentication and HTTPS
5. **Consider VPN** for secure access

---

## Troubleshooting Script

Download and run the automated diagnostic script:

```bash
cd ~/project/ayna-pod-recommender/deployment/docker
chmod +x fix_redisinsight_access.sh
./fix_redisinsight_access.sh
```

This will automatically:
- Check container status
- Verify port bindings
- Test connections
- Check firewall rules
- Provide recommendations

---

## Still Not Working?

Check these additional items:

1. **Docker daemon restart:**
   ```bash
   sudo systemctl restart docker
   docker-compose -f docker-compose.prod.yml up -d
   ```

2. **Check network connectivity:**
   ```bash
   docker network inspect esab-network-prod
   ```

3. **Verify RedisInsight image:**
   ```bash
   docker images | grep redisinsight
   docker pull redislabs/redisinsight:latest
   docker-compose -f docker-compose.prod.yml up -d redisinsight --force-recreate
   ```

4. **Check container health:**
   ```bash
   docker inspect esab-redisinsight-prod | grep -A 20 '"State"'
   ```

---

## Alternative: Use redis-cli Instead

If RedisInsight still doesn't work, you can use redis-cli directly:

```bash
# Enter Redis CLI
docker exec -it esab-redis-prod redis-cli -a esab_redis_prod_password

# Common commands:
> KEYS *                    # List all keys
> GET key_name             # Get value
> SCAN 0 MATCH session:*   # Find session keys
> TTL key_name             # Check expiry
> INFO                     # Server info
> QUIT                     # Exit
```
