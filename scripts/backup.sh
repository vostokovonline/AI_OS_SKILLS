#!/bin/bash
# Backup AI-OS data: PostgreSQL + Artifacts

BACKUP_DIR="/home/onor/ai_os_final/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "=== AI-OS Backup $DATE ==="

# 1. Backup PostgreSQL
echo "[1/3] Backing up PostgreSQL..."
docker exec ns_postgres pg_dump -U ns_admin ns_core_db > "$BACKUP_DIR/postgres_$DATE.sql"
echo "  → Saved: postgres_$DATE.sql ($(du -h "$BACKUP_DIR/postgres_$DATE.sql" | cut -f1))"

# 2. Backup Artifacts
echo "[2/3] Backing up artifacts..."
tar -czf "$BACKUP_DIR/artifacts_$DATE.tar.gz" -C /home/onor/ai_os_final/infra/artifacts .
echo "  → Saved: artifacts_$DATE.tar.gz"

# 3. Cleanup old backups (keep last 7)
echo "[3/3] Cleaning up old backups..."
find "$BACKUP_DIR" -name "postgres_*.sql" -mtime +7 -delete
find "$BACKUP_DIR" -name "artifacts_*.tar.gz" -mtime +7 -delete

echo "=== Backup Complete ==="
echo "Location: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5