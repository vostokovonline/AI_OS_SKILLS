#!/usr/bin/env python3
"""
OCCP Automated Database Backup
Run via cron for scheduled backups
"""
import os
import gzip
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

def backup_databases():
    """Backup all OCCP databases"""
    occp_root = Path(os.environ.get("OCCP_ROOT", "/home/onor/ai_os_final"))
    backup_dir = occp_root / "ocp/backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    databases = {
        "registry": occp_root / "ocp/registry/registry.db",
        "cicd": occp_root / "ocp/cicd/cicd.db",
        "observability": occp_root / "ocp/observability/metrics.db",
        "federation": occp_root / "ocp/federation/federation.db",
        "mitigation": occp_root / "ocp/mitigation/mitigation.db",
        "proposal": occp_root / "ocp/proposal/proposal.db"
    }
    
    backup_count = 0
    total_size = 0
    
    for db_name, db_path in databases.items():
        if not db_path.exists():
            continue
        
        # Copy and compress
        backup_path = backup_dir / f"{db_name}.db"
        shutil.copy2(db_path, backup_path)
        
        compressed_path = backup_dir / f"{db_name}.db.gz"
        with open(backup_path, "rb") as f_in:
            with gzip.open(compressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        backup_path.unlink()
        
        total_size += compressed_path.stat().st_size
        backup_count += 1
    
    # Create checksums
    checksums = {}
    for backup_file in backup_dir.glob("*.db.gz"):
        sha256 = hashlib.sha256()
        with open(backup_file, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256.update(byte_block)
        checksums[backup_file.name] = sha256.hexdigest()
    
    checksums_path = backup_dir / "checksums.txt"
    with open(checksums_path, "w") as f:
        for filename, checksum in sorted(checksums.items()):
            f.write(f"{checksum}  {filename}\n")
    
    print(f"Backup completed: {backup_count} databases, {total_size} bytes")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(backup_databases())
