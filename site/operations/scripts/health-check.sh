#!/bin/bash
################################################################################
# Health Check Script for ESAB Welding Equipment Configurator
#
# Description: Monitors application health endpoint and component status
# Usage: ./health-check.sh [--email admin@example.com]
# Cron: */5 * * * * /opt/esab-recommender/scripts/health-check.sh
################################################################################

# Configuration
API_URL="${API_URL:-http://localhost:8000/health}"
ALERT_EMAIL="${ALERT_EMAIL:-admin@example.com}"
LOG_FILE="${LOG_FILE:-/var/log/esab-health-check.log}"
ENABLE_EMAIL_ALERTS="${ENABLE_EMAIL_ALERTS:-false}"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --email)
            ALERT_EMAIL="$2"
            ENABLE_EMAIL_ALERTS="true"
            shift 2
            ;;
        --url)
            API_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--email <email>] [--url <health_url>]"
            exit 1
            ;;
    esac
done

# Function to send email alert
send_alert() {
    local subject="$1"
    local message="$2"

    if [ "$ENABLE_EMAIL_ALERTS" = "true" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    fi

    # Always log
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ALERT: $subject - $message" >> "$LOG_FILE"
}

# Function to log success
log_success() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] OK: $message" >> "$LOG_FILE"
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed. Please install: sudo apt install jq"
    exit 1
fi

# Check health endpoint HTTP status
echo "Checking health endpoint: $API_URL"
response_code=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL")

if [ "$response_code" != "200" ]; then
    send_alert "ESAB Recommender Health Check Failed" \
        "Health endpoint returned HTTP $response_code (expected 200)\nURL: $API_URL"
    exit 1
fi

log_success "Health endpoint returned HTTP 200"

# Get health check JSON
health_json=$(curl -s "$API_URL")

if [ -z "$health_json" ]; then
    send_alert "ESAB Recommender Health Check Failed" \
        "Health endpoint returned empty response\nURL: $API_URL"
    exit 1
fi

# Check overall status
overall_status=$(echo "$health_json" | jq -r '.status')

if [ "$overall_status" != "healthy" ]; then
    send_alert "ESAB Recommender Health Check Failed" \
        "Overall status is $overall_status (expected healthy)\nURL: $API_URL"
    exit 1
fi

log_success "Overall status is healthy"

# Check individual components
neo4j_status=$(echo "$health_json" | jq -r '.components.neo4j.status')
postgres_status=$(echo "$health_json" | jq -r '.components.postgres.status')
redis_status=$(echo "$health_json" | jq -r '.components.redis.status')
openai_status=$(echo "$health_json" | jq -r '.components.openai.status')

# Check Neo4j
if [ "$neo4j_status" != "healthy" ]; then
    send_alert "ESAB Recommender - Neo4j Unhealthy" \
        "Neo4j status: $neo4j_status\nExpected: healthy\nURL: $API_URL"
else
    neo4j_response_time=$(echo "$health_json" | jq -r '.components.neo4j.response_time_ms')
    log_success "Neo4j is healthy (response time: ${neo4j_response_time}ms)"
fi

# Check PostgreSQL
if [ "$postgres_status" != "healthy" ]; then
    send_alert "ESAB Recommender - PostgreSQL Unhealthy" \
        "PostgreSQL status: $postgres_status\nExpected: healthy\nURL: $API_URL"
else
    postgres_response_time=$(echo "$health_json" | jq -r '.components.postgres.response_time_ms')
    log_success "PostgreSQL is healthy (response time: ${postgres_response_time}ms)"
fi

# Check Redis
if [ "$redis_status" != "healthy" ]; then
    send_alert "ESAB Recommender - Redis Unhealthy" \
        "Redis status: $redis_status\nExpected: healthy\nURL: $API_URL"
else
    redis_type=$(echo "$health_json" | jq -r '.components.redis.type')
    log_success "Redis is healthy (type: $redis_type)"
fi

# Check OpenAI
if [ "$openai_status" != "healthy" ]; then
    send_alert "ESAB Recommender - OpenAI Unhealthy" \
        "OpenAI status: $openai_status\nExpected: healthy\nURL: $API_URL"
else
    log_success "OpenAI is healthy"
fi

# All checks passed
log_success "All health checks passed successfully"
exit 0
