#!/usr/bin/env bash
# ====================================================
# TECHNOCRATIC AI OS v3.9.1 — SYSTEM TEST (TRUTH ORACLE)
# ====================================================

set -Eeuo pipefail
IFS=$'\n\t'
trap 'echo "❌ TEST FAILED at line $LINENO"; exit 1' ERR

log()  { echo -e "🧪 $*"; }
fail() { echo -e "❌ $*"; exit 1; }
ok()   { echo -e "✅ $*"; }

log "STARTING SYSTEM TESTS..."

# ----------------------------------------------------
# 1. ENVIRONMENT CHECKS
# ----------------------------------------------------

command -v docker >/dev/null || fail "docker not installed"
command -v docker-compose >/dev/null || command -v docker >/dev/null || fail "docker compose not available"

[[ -f .env ]] || fail ".env missing"

ok "Environment OK"

# ----------------------------------------------------
# 2. CONTAINER STATUS
# ----------------------------------------------------

log "Checking running containers..."

REQUIRED_CONTAINERS=(
  ns_postgres
  ns_redis
  ns_minio
  ns_milvus
  ns_neo4j
  ns_litellm
  ns_core
  ns_core_worker
)

for c in "${REQUIRED_CONTAINERS[@]}"; do
  docker ps --format '{{.Names}}' | grep -q "^${c}$" || fail "Container not running: $c"
done

ok "All required containers running"

# ----------------------------------------------------
# 3. HEALTHCHECKS
# ----------------------------------------------------

log "Waiting for Core API..."

for i in {1..30}; do
  if curl -sf http://localhost:8000/docs >/dev/null; then
    ok "Core API is up"
    break
  fi
  sleep 2
  [[ "$i" == "30" ]] && fail "Core API not responding"
done

# ----------------------------------------------------
# 4. CHAT FLOW TEST
# ----------------------------------------------------

log "Testing /chat endpoint..."

SESSION_ID="test_$(date +%s)"

RESP=$(curl -sf -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"content\":\"Hello system, respond briefly.\"}")

echo "$RESP" | grep -q "Processing" || fail "/chat did not accept task"

ok "Chat task accepted"

# ----------------------------------------------------
# 5. CELERY DISPATCH CHECK
# ----------------------------------------------------

log "Waiting for Celery execution..."

sleep 5

LOGS=$(docker logs ns_core_worker --since 10s || true)
echo "$LOGS" | grep -E "Executing Graph|DONE|PAUSED" >/dev/null \
  || fail "Celery worker did not process task"

ok "Celery execution detected"

# ----------------------------------------------------
# 6. MEMORY SERVICE CHECK
# ----------------------------------------------------

log "Testing memory service..."

curl -sf -X POST http://localhost:8001/remember \
  -H "Content-Type: application/json" \
  -d '{"text":"test memory entry","metadata":{"source":"test"}}' \
  >/dev/null || fail "Memory service not accepting data"

ok "Memory service OK"

# ----------------------------------------------------
# FINAL
# ----------------------------------------------------

ok "🎉 ALL TESTS PASSED — SYSTEM IS OPERATIONAL"
