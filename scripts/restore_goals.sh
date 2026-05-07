#!/bin/bash
# Restore AI-OS goals from backup

set -e

BACKUP_DIR="/home/onor/ai_os_final/backups"

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lht "$BACKUP_DIR"/goals_backup_*.sql.gz 2>/dev/null | head -10
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will REPLACE the current database!"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "Restoring from: $BACKUP_FILE"

# Stop core service to prevent conflicts
docker-compose stop core

# Restore database
gunzip -c "$BACKUP_FILE" | docker exec -i ns_postgres psql -U ns_admin -d ns_core_db

# Start core service
docker-compose start core

echo "Restore completed. Please verify:"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "SELECT COUNT(*) FROM goals;"
