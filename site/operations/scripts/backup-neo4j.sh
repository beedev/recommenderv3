#!/bin/bash
################################################################################
# Neo4j Backup Script for ESAB Welding Equipment Configurator
#
# Description: Creates Neo4j database backups with rotation (Community Edition)
# Usage: ./backup-neo4j.sh
# Cron: 0 3 * * * /opt/esab-recommender/scripts/backup-neo4j.sh
# Note: Requires Neo4j Community Edition (self-hosted). Not needed for Aura.
################################################################################

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup/neo4j}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
NEO4J_HOME="${NEO4J_HOME:-/var/lib/neo4j}"
NEO4J_SERVICE="${NEO4J_SERVICE:-neo4j}"
DB_NAME="${DB_NAME:-neo4j}"
LOG_FILE="${LOG_FILE:-/var/log/esab-backup-neo4j.log}"
ALERT_EMAIL="${ALERT_EMAIL:-admin@example.com}"
ENABLE_EMAIL_ALERTS="${ENABLE_EMAIL_ALERTS:-false}"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Function to send email alert
send_alert() {
    local subject="$1"
    local message="$2"

    if [ "$ENABLE_EMAIL_ALERTS" = "true" ]; then
        echo "$message" | mail -s "$subject" "$ALERT_EMAIL"
    fi

    log "ALERT: $subject - $message"
}

# Check if running on Neo4j Aura (cloud)
if [ ! -d "$NEO4J_HOME" ]; then
    log "Neo4j home directory not found. If using Neo4j Aura, backups are managed automatically."
    log "Exiting without error."
    exit 0
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

if [ ! -d "$BACKUP_DIR" ]; then
    send_alert "Neo4j Backup Failed" \
        "Backup directory does not exist and could not be created: $BACKUP_DIR"
    exit 1
fi

log "Starting Neo4j backup for database: $DB_NAME"

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/neo4j_$TIMESTAMP.dump"

# Check if Neo4j service is running
NEO4J_RUNNING=$(systemctl is-active "$NEO4J_SERVICE" 2>/dev/null)

if [ "$NEO4J_RUNNING" = "active" ]; then
    log "Stopping Neo4j service for consistent backup..."
    sudo systemctl stop "$NEO4J_SERVICE"

    if [ $? -ne 0 ]; then
        send_alert "Neo4j Backup Failed" \
            "Failed to stop Neo4j service"
        exit 1
    fi

    NEO4J_WAS_RUNNING=true
else
    log "Neo4j service is not running"
    NEO4J_WAS_RUNNING=false
fi

# Create backup using neo4j-admin
log "Creating backup: $BACKUP_FILE"
neo4j-admin database dump "$DB_NAME" --to="$BACKUP_FILE" 2>&1 | tee -a "$LOG_FILE"

BACKUP_STATUS=${PIPESTATUS[0]}

# Restart Neo4j if it was running
if [ "$NEO4J_WAS_RUNNING" = true ]; then
    log "Restarting Neo4j service..."
    sudo systemctl start "$NEO4J_SERVICE"

    if [ $? -ne 0 ]; then
        send_alert "Neo4j Restart Failed" \
            "Backup completed but failed to restart Neo4j service"
    fi
fi

# Check if backup was successful
if [ $BACKUP_STATUS -eq 0 ] && [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup successful: $BACKUP_FILE (Size: $BACKUP_SIZE)"

    # Delete old backups (older than retention period)
    log "Removing backups older than $RETENTION_DAYS days..."
    DELETED_COUNT=$(find "$BACKUP_DIR" -name "neo4j_*.dump" -mtime +$RETENTION_DAYS -delete -print | wc -l)

    if [ "$DELETED_COUNT" -gt 0 ]; then
        log "Deleted $DELETED_COUNT old backup(s)"
    else
        log "No old backups to delete"
    fi

    # List current backups
    log "Current backups:"
    ls -lh "$BACKUP_DIR"/neo4j_*.dump 2>/dev/null | tee -a "$LOG_FILE"

    log "Neo4j backup completed successfully"
    exit 0
else
    send_alert "Neo4j Backup Failed" \
        "Failed to create backup: $BACKUP_FILE\nCheck log: $LOG_FILE"
    exit 1
fi
