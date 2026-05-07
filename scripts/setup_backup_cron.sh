#!/bin/bash
# OCCP Backup Cron Setup
# Schedules automated database backups

# Backup schedules
# - Every 6 hours: 0 */6 * * * (4 times per day)
# - Daily: 0 2 * * * (2 AM every day)
# - Weekly: 0 3 * * 0 (3 AM every Sunday)

OCCP_ROOT="${OCCP_ROOT:-/home/onor/ai_os_final}"
BACKUP_SCRIPT="${OCCP_ROOT}/scripts/backup_databases.sh"
PYTHON_BACKUP="${OCCP_ROOT}/scripts/backup_python.py"

# Check if backup script exists
if [ ! -f "$BACKUP_SCRIPT" ] && [ ! -f "$PYTHON_BACKUP" ]; then
    echo "Error: Backup script not found"
    exit 1
fi

# Use Python backup if shell script doesn't exist
if [ ! -f "$BACKUP_SCRIPT" ] && [ -f "$PYTHON_BACKUP" ]; then
    BACKUP_SCRIPT="python3 ${PYTHON_BACKUP}"
fi

# Install cron jobs
echo "Installing OCCP backup cron jobs..."
echo ""

# Hourly backup (for testing - every hour)
(crontab -l 2>/dev/null | grep -v "ocp.*backup"; echo "0 * * * * ${BACKUP_SCRIPT} > ${OCCP_ROOT}/ocp/backups/backup.log 2>&1") | crontab -

# Daily backup at 2 AM
# (crontab -l 2>/dev/null | grep -v "ocp.*backup"; echo "0 2 * * * ${BACKUP_SCRIPT} > ${OCCP_ROOT}/ocp/backups/backup.log 2>&1") | crontab -

# Weekly backup on Sunday at 3 AM
# (crontab -l 2>/dev/null | grep -v "ocp.*backup"; echo "0 3 * * 0 ${BACKUP_SCRIPT} > ${OCCP_ROOT}/ocp/backups/backup.log 2>&1") | crontab -

echo "✓ Cron jobs installed"
echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Backup logs: ${OCCP_ROOT}/ocp/backups/backup.log"
