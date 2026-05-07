#!/usr/bin/env bash
set -e

ROOT="/home/onor/ai_os_final"
CORE="$ROOT/services/core"
REPORT="/tmp/patch_cadence_$(date +%s).log"

log() { echo "$1" | tee -a "$REPORT"; }

log "PATCH cadence scheduler — $(date)"
log "---------------------------------"

FILE="$CORE/cadence.py"

cat > "$FILE" <<'EOF'
"""
CADENCE SCHEDULER FOR SYSTEMIC GOALS
"""
from datetime import datetime, timedelta

def should_run(goal: dict, last_run: datetime | None) -> bool:
    cadence = goal.get("policy", {}).get("cadence_days")
    if not cadence:
        return False

    if last_run is None:
        return True

    return datetime.utcnow() - last_run >= timedelta(days=cadence)
EOF

log "✔ cadence.py created"
log "DONE"
echo
cat "$REPORT"
