#!/usr/bin/env bash
# ====================================================
# AUTO-REPAIR ORCHESTRATOR
# ====================================================

set -Eeuo pipefail
IFS=$'\n\t'

MAX_ATTEMPTS=3
ATTEMPT=1

log()  { echo -e "🔧 $*"; }
fail() { echo -e "❌ $*"; exit 1; }

while [[ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]]; do
  log "REPAIR ATTEMPT $ATTEMPT / $MAX_ATTEMPTS"

  if ./test.sh > test.log 2>&1; then
    log "✅ SYSTEM HEALTHY"
    exit 0
  fi

  log "❌ TEST FAILED — ANALYZING"

  docker ps -a > state_containers.log
  docker logs ns_core --since 5m > logs_core.log || true
  docker logs ns_core_worker --since 5m > logs_worker.log || true

  log "🧠 Asking Troubleshooter..."

  curl -sf -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d "{
      \"session_id\": \"repair_$ATTEMPT\",
      \"content\": \"SYSTEM FAILURE DETECTED.

TEST OUTPUT:
$(sed 's/"/\\"/g' test.log)

CORE LOGS:
$(sed 's/"/\\"/g' logs_core.log)

WORKER LOGS:
$(sed 's/"/\\"/g' logs_worker.log)

TASK:
1. Identify root cause
2. Propose minimal fix
3. Output ONLY bash commands to fix
\"
    }" > repair_plan.json || true

  log "📜 Repair plan received"
  cat repair_plan.json

  log "⚠️  APPLYING FIX (manual execution recommended at first)"

  # 🔒 v3.10: MANUAL APPLY
  # 🔓 v3.11: AUTO APPLY (eval)

  docker compose restart core core_worker
  sleep 5

  ((ATTEMPT++))
done

fail "🚨 AUTO-REPAIR FAILED AFTER $MAX_ATTEMPTS ATTEMPTS"
