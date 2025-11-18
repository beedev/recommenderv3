#!/bin/bash
################################################################################
# Log Cleanup Script for ESAB Welding Equipment Configurator
#
# Description: Removes old log files and compresses recent logs
# Usage: ./cleanup-old-logs.sh
# Cron: 0 2 * * * /opt/esab-recommender/scripts/cleanup-old-logs.sh
################################################################################

# Configuration
LOG_DIR="${LOG_DIR:-/home/azureuser/esab_recommender-bh/logs}"
BACKUP_LOG_DIR="${BACKUP_LOG_DIR:-/var/log}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
COMPRESS_AGE_DAYS="${COMPRESS_AGE_DAYS:-7}"
LOG_FILE="${LOG_FILE:-/var/log/esab-cleanup.log}"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "Starting log cleanup process"

# Check if log directory exists
if [ ! -d "$LOG_DIR" ]; then
    log "Log directory does not exist: $LOG_DIR"
    log "Exiting without error"
    exit 0
fi

# 1. Delete old log files (older than retention period)
log "Removing log files older than $RETENTION_DAYS days from $LOG_DIR..."
DELETED_COUNT=$(find "$LOG_DIR" -name "*.log" -mtime +$RETENTION_DAYS -delete -print | wc -l)

if [ "$DELETED_COUNT" -gt 0 ]; then
    log "Deleted $DELETED_COUNT old log file(s)"
else
    log "No old log files to delete"
fi

# 2. Compress log files older than compress age (but newer than retention)
log "Compressing log files older than $COMPRESS_AGE_DAYS days..."

# Find uncompressed log files older than compress age
COMPRESS_FILES=$(find "$LOG_DIR" -name "*.log" -mtime +$COMPRESS_AGE_DAYS ! -name "*.gz")

if [ -n "$COMPRESS_FILES" ]; then
    COMPRESSED_COUNT=0

    while IFS= read -r file; do
        if [ -f "$file" ]; then
            log "Compressing: $file"
            gzip "$file"

            if [ $? -eq 0 ]; then
                ((COMPRESSED_COUNT++))
            else
                log "Failed to compress: $file"
            fi
        fi
    done <<< "$COMPRESS_FILES"

    log "Compressed $COMPRESSED_COUNT log file(s)"
else
    log "No log files to compress"
fi

# 3. Clean up backup log directory (if different from main log dir)
if [ "$BACKUP_LOG_DIR" != "$LOG_DIR" ] && [ -d "$BACKUP_LOG_DIR" ]; then
    log "Cleaning up backup log directory: $BACKUP_LOG_DIR..."

    # Delete old backup log files
    DELETED_BACKUP_COUNT=$(find "$BACKUP_LOG_DIR" -name "esab-*.log" -mtime +$RETENTION_DAYS -delete -print | wc -l)

    if [ "$DELETED_BACKUP_COUNT" -gt 0 ]; then
        log "Deleted $DELETED_BACKUP_COUNT old backup log file(s)"
    else
        log "No old backup log files to delete"
    fi
fi

# 4. Clean up systemd journal logs (keep last 30 days)
log "Cleaning up systemd journal logs (keeping last 30 days)..."
sudo journalctl --vacuum-time=30d 2>&1 | tee -a "$LOG_FILE"

# 5. Report disk usage
log "Disk usage after cleanup:"
df -h "$LOG_DIR" | tee -a "$LOG_FILE"

log "Log cleanup completed successfully"
exit 0
