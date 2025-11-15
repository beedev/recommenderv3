#!/bin/bash

# RedisInsight Access Fix Script
# Run this on your Docker host to diagnose and fix RedisInsight access issues

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== RedisInsight Access Diagnostic & Fix ===${NC}\n"

# 1. Check if container is running
echo -e "${BLUE}[1/8] Checking if RedisInsight container exists and is running...${NC}"
if docker ps -a | grep -q esab-redisinsight-prod; then
    CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' esab-redisinsight-prod)
    echo -e "Container status: ${GREEN}${CONTAINER_STATUS}${NC}"
    
    if [ "$CONTAINER_STATUS" != "running" ]; then
        echo -e "${YELLOW}Container is not running. Starting it...${NC}"
        docker start esab-redisinsight-prod
        sleep 5
    fi
else
    echo -e "${RED}Container does not exist!${NC}"
    echo "Creating RedisInsight container..."
    cd ~/project/ayna-pod-recommender/deployment/docker
    docker-compose -f docker-compose.prod.yml up -d redisinsight
    sleep 10
fi

# 2. Check container logs
echo -e "\n${BLUE}[2/8] Checking container logs (last 20 lines)...${NC}"
docker logs esab-redisinsight-prod --tail 20

# 3. Check port bindings
echo -e "\n${BLUE}[3/8] Checking port bindings...${NC}"
docker port esab-redisinsight-prod || echo -e "${RED}No ports exposed${NC}"

# 4. Check if port is listening on host
echo -e "\n${BLUE}[4/8] Checking if port 8001 is listening on host...${NC}"
if netstat -tlnp 2>/dev/null | grep -q ':8001' || ss -tlnp 2>/dev/null | grep -q ':8001'; then
    echo -e "${GREEN}✓ Port 8001 is listening${NC}"
    netstat -tlnp 2>/dev/null | grep ':8001' || ss -tlnp 2>/dev/null | grep ':8001'
else
    echo -e "${RED}✗ Port 8001 is NOT listening on host${NC}"
fi

# 5. Test local connection
echo -e "\n${BLUE}[5/8] Testing connection from localhost...${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8001 > /tmp/http_code.txt 2>&1; then
    HTTP_CODE=$(cat /tmp/http_code.txt)
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "301" ]; then
        echo -e "${GREEN}✓ HTTP connection successful (Status: $HTTP_CODE)${NC}"
    else
        echo -e "${YELLOW}HTTP Status: $HTTP_CODE${NC}"
    fi
else
    echo -e "${RED}✗ Cannot connect to localhost:8001${NC}"
fi

# 6. Check if port is bound to 0.0.0.0 or 127.0.0.1
echo -e "\n${BLUE}[6/8] Checking port binding address...${NC}"
BINDING=$(docker inspect esab-redisinsight-prod | grep -A 5 '"Ports"' | grep '8001' || echo "Not found")
echo "$BINDING"

if echo "$BINDING" | grep -q '"HostIp": "127.0.0.1"'; then
    echo -e "${YELLOW}⚠ Port is bound to 127.0.0.1 only (localhost only)${NC}"
    echo "This means RedisInsight is only accessible from the Docker host, not from external IPs"
elif echo "$BINDING" | grep -q '"HostIp": "0.0.0.0"'; then
    echo -e "${GREEN}✓ Port is bound to 0.0.0.0 (accessible from network)${NC}"
else
    echo -e "${RED}Cannot determine port binding${NC}"
fi

# 7. Check firewall
echo -e "\n${BLUE}[7/8] Checking firewall rules...${NC}"
if command -v ufw &> /dev/null; then
    echo "UFW Status:"
    sudo ufw status | grep 8001 || echo -e "${YELLOW}Port 8001 not explicitly allowed in UFW${NC}"
    
    read -p "Do you want to allow port 8001 in UFW? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo ufw allow 8001/tcp
        echo -e "${GREEN}✓ Port 8001 allowed in UFW${NC}"
    fi
elif command -v firewall-cmd &> /dev/null; then
    echo "Firewalld Status:"
    sudo firewall-cmd --list-ports | grep 8001 || echo -e "${YELLOW}Port 8001 not in firewall rules${NC}"
    
    read -p "Do you want to allow port 8001 in firewall? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo firewall-cmd --permanent --add-port=8001/tcp
        sudo firewall-cmd --reload
        echo -e "${GREEN}✓ Port 8001 allowed in firewall${NC}"
    fi
else
    echo -e "${GREEN}No firewall detected (ufw/firewalld)${NC}"
fi

# 8. Check from inside container
echo -e "\n${BLUE}[8/8] Checking service inside container...${NC}"
docker exec esab-redisinsight-prod sh -c "wget -O- http://localhost:8001 2>&1 | head -5" || \
    echo -e "${YELLOW}Cannot test from inside container${NC}"

# Summary and recommendations
echo -e "\n${BLUE}=== Summary & Recommendations ===${NC}\n"

# Get server's public IP
PUBLIC_IP=$(curl -s ifconfig.me || curl -s icanhazip.com || echo "unknown")
PRIVATE_IP=$(hostname -I | awk '{print $1}' || echo "unknown")

echo -e "1. Container Status: ${GREEN}$(docker inspect -f '{{.State.Status}}' esab-redisinsight-prod)${NC}"
echo -e "2. Port Binding: $(docker port esab-redisinsight-prod 2>/dev/null | head -1 || echo 'Not bound')"
echo -e "3. Server Private IP: ${PRIVATE_IP}"
echo -e "4. Server Public IP: ${PUBLIC_IP}"
echo ""
echo -e "${GREEN}Try accessing RedisInsight at:${NC}"
echo -e "  • http://localhost:8001 (from the server itself)"
echo -e "  • http://${PRIVATE_IP}:8001 (from your local network)"
echo -e "  • http://${PUBLIC_IP}:8001 (from internet - if firewall allows)"
echo ""

# Offer to restart if needed
read -p "Do you want to restart the RedisInsight container? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Restarting RedisInsight..."
    cd ~/project/ayna-pod-recommender/deployment/docker
    docker-compose -f docker-compose.prod.yml restart redisinsight
    sleep 5
    echo -e "${GREEN}✓ RedisInsight restarted${NC}"
    echo "Please try accessing it now"
fi

echo -e "\n${BLUE}=== Additional Troubleshooting ===${NC}\n"
echo "If still not accessible:"
echo "1. Check if the port is bound to 127.0.0.1 instead of 0.0.0.0"
echo "   Solution: Update docker-compose.prod.yml ports to '0.0.0.0:8001:8001'"
echo ""
echo "2. Check cloud provider security groups (AWS, Azure, GCP)"
echo "   Solution: Allow inbound TCP port 8001"
echo ""
echo "3. View live logs:"
echo "   docker logs -f esab-redisinsight-prod"
echo ""
echo "4. Access via SSH tunnel:"
echo "   ssh -L 8001:localhost:8001 user@${PUBLIC_IP}"
echo "   Then open http://localhost:8001 in your browser"
