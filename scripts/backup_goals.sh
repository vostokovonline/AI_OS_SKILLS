#!/bin/bash
# Daily backup script for AI-OS goals and artifacts
# Runs every day at 3 AM

set -e

# Configuration
BACKUP_DIR="/home/onor/ai_os_final/backups"
DATE=$(date +%Y%m%d_%H%M%S)
TIMESTAMP=$(date -Iseconds)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "[$TIMESTAMP] Starting AI-OS backup..."

# Backup PostgreSQL database
BACKUP_FILE="$BACKUP_DIR/goals_backup_$DATE.sql.gz"
echo "[$TIMESTAMP] Backing up to: $BACKUP_FILE"

docker exec ns_postgres pg_dump -U ns_admin ns_core_db | gzip > "$BACKUP_FILE"

# Check backup size
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[$TIMESTAMP] Backup completed. Size: $BACKUP_SIZE"

# Backup goals specifically to JSON (for easy reading)
JSON_BACKUP="$BACKUP_DIR/goals_json_$DATE.json"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -A \
  -c "SELECT id, title, description, status, progress, parent_id, created_at, updated_at FROM goals;" \
  > "$JSON_BACKUP"

echo "[$TIMESTAMP] JSON backup created: $JSON_BACKUP"

# Clean up old backups (keep last 30 days)
find "$BACKUP_DIR" -name "goals_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "goals_json_*.json" -mtime +$RETENTION_DAYS -delete

REMOVED=$(find "$BACKUP_DIR" -name "*.sql.gz" | wc -l)
echo "[$TIMESTAMP] Backup completed. Total backups: $REMOVED"

# Log backup
echo "$TIMESTAMP | backup | $BACKUP_FILE | $BACKUP_SIZE" >> "$BACKUP_DIR/backup_log.txt"
