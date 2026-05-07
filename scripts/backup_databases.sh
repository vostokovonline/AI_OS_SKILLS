#!/bin/bash
# OCCP Database Backup Script
# Backs up all OCCP SQLite databases

set -e

# Configuration
OCCP_ROOT="${OCCP_ROOT:-/home/onor/ai_os_final}"
BACKUP_ROOT="${OCCP_ROOT}/ocp/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/${TIMESTAMP}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
log_info "Creating backup directory: ${BACKUP_DIR}"
mkdir -p "${BACKUP_DIR}"

# Database locations
declare -A DATABASES=(
    ["registry"]="${OCCP_ROOT}/ocp/registry/registry.db"
    ["cicd"]="${OCCP_ROOT}/ocp/cicd/cicd.db"
    ["observability"]="${OCCP_ROOT}/ocp/observability/metrics.db"
    ["federation"]="${OCCP_ROOT}/ocp/federation/federation.db"
    ["mitigation"]="${OCCP_ROOT}/ocp/mitigation/mitigation.db"
    ["proposal"]="${OCCP_ROOT}/ocp/proposal/proposal.db"
)

# Backup each database
BACKUP_COUNT=0
FAILED_COUNT=0

for db_name in "${!DATABASES[@]}"; do
    db_path="${DATABASES[$db_name]}"
    
    if [ ! -f "$db_path" ]; then
        log_warn "Database not found: ${db_name} at ${db_path}"
        continue
    fi
    
    log_info "Backing up ${db_name}..."
    
    # Backup using sqlite3
    if sqlite3 "$db_path" ".backup '${BACKUP_DIR}/${db_name}.db'" 2>/dev/null; then
        # Compress backup
        gzip "${BACKUP_DIR}/${db_name}.db"
        log_info "✓ Backed up ${db_name} (${db_name}.db.gz)"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    else
        log_error "Failed to backup ${db_name}"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
done

# Create backup manifest
cat > "${BACKUP_DIR}/manifest.txt" <<EOF
OCCP Database Backup
===================
Timestamp: ${TIMESTAMP}
Date: $(date)
Host: $(hostname)
Backup Count: ${BACKUP_COUNT}
Failed: ${FAILED_COUNT}

Databases Backed Up:
EOF

for db_name in "${!DATABASES[@]}"; do
    db_path="${DATABASES[$db_name]}"
    if [ -f "$db_path" ]; then
        size=$(du -h "$db_path" | cut -f1)
        echo "  - ${db_name}: ${size}" >> "${BACKUP_DIR}/manifest.txt"
    fi
done

log_info "Backup manifest created"

# Create checksums
log_info "Creating checksums..."
cd "${BACKUP_DIR}"
sha256sum *.db.gz > checksums.txt 2>/dev/null || true
cd - > /dev/null

# Summary
echo ""
echo "================================"
echo "Backup Summary"
echo "================================"
echo "Directory: ${BACKUP_DIR}"
echo "Databases backed up: ${BACKUP_COUNT}"
echo "Failed: ${FAILED_COUNT}"
echo "Timestamp: ${TIMESTAMP}"
echo ""

if [ ${FAILED_COUNT} -gt 0 ]; then
    log_error "Backup completed with errors"
    exit 1
else
    log_info "Backup completed successfully"
    exit 0
fi
