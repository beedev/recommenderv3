#!/bin/bash
################################################################################
# PostgreSQL Backup Script for ESAB Welding Equipment Configurator
#
# Description: Creates compressed PostgreSQL backups with rotation
# Usage: ./backup-postgres.sh
# Cron: 0 3 * * * /opt/esab-recommender/scripts/backup-postgres.sh
################################################################################

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup/postgresql}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DB_NAME="${DB_NAME:-pconfig}"
DB_USER="${DB_USER:-postgres}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
LOG_FILE="${LOG_FILE:-/var/log/esab-backup-postgres.log}"
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

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

if [ ! -d "$BACKUP_DIR" ]; then
    send_alert "PostgreSQL Backup Failed" \
        "Backup directory does not exist and could not be created: $BACKUP_DIR"
    exit 1
fi

log "Starting PostgreSQL backup for database: $DB_NAME"

# Generate backup filename with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/pconfig_$TIMESTAMP.dump"

# Create compressed backup using custom format (-Fc)
log "Creating backup: $BACKUP_FILE"
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -Fc -f "$BACKUP_FILE" "$DB_NAME" 2>&1 | tee -a "$LOG_FILE"

# Check if backup was successful
if [ ${PIPESTATUS[0]} -eq 0 ] && [ -f "$BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup successful: $BACKUP_FILE (Size: $BACKUP_SIZE)"

    # Verify backup integrity
    log "Verifying backup integrity..."
    pg_restore --list "$BACKUP_FILE" > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        log "Backup integrity verified"
    else
        send_alert "PostgreSQL Backup Verification Failed" \
            "Backup file created but failed integrity check: $BACKUP_FILE"
        exit 1
    fi

    # Delete old backups (older than retention period)
    log "Removing backups older than $RETENTION_DAYS days..."
    DELETED_COUNT=$(find "$BACKUP_DIR" -name "pconfig_*.dump" -mtime +$RETENTION_DAYS -delete -print | wc -l)

    if [ "$DELETED_COUNT" -gt 0 ]; then
        log "Deleted $DELETED_COUNT old backup(s)"
    else
        log "No old backups to delete"
    fi

    # List current backups
    log "Current backups:"
    ls -lh "$BACKUP_DIR"/pconfig_*.dump 2>/dev/null | tee -a "$LOG_FILE"

    log "PostgreSQL backup completed successfully"
    exit 0
else
    send_alert "PostgreSQL Backup Failed" \
        "Failed to create backup: $BACKUP_FILE\nCheck log: $LOG_FILE"
    exit 1
fi
