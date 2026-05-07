# Execution V3 - Rollback Plan

**Date**: 2026-03-03
**Severity**: CRITICAL - Use if system shows anomalies

---

## 🚨 Immediate Rollback

If you observe ANY of these:
- Escalation rate > 20% (indicates systemic issues)
- Success rate < 50% (system broken)
- Duplicate side effects reported (users)
- Goals stuck in "locked" state > 10 minutes
- Memory leaks or resource exhaustion

### Step 1: Disable V3 Immediately

```bash
# Edit .env.execution_v3
ENABLE_EXECUTION_V3=false

# Restart core service
docker-compose restart core
```

### Step 2: Verify Legacy Active

```bash
# Check health endpoint
curl http://localhost:8000/execution-v3/health | jq .

# Should show:
# "ENABLE_EXECUTION_V3": false
```

### Step 3: Clear Orphaned Locks (ONLY after safe waiting period)

**CRITICAL:** DO NOT clear locks immediately! If V3 is still executing, clearing locks
will cause legacy to pick up the same goal → DUPLICATE EXECUTION.

**SAFE SEQUENCE:**
1. Disable flag + restart
2. WAIT > STALE_LOCK_TIMEOUT (5 minutes)
3. Verify no active V3 executions
4. ONLY THEN clear locks

```bash
# Step 1: Disable V3
ENABLE_EXECUTION_V3=false
docker-compose restart core

# Step 2: WAIT for all V3 executions to complete or timeout
# DO NOT SKIP THIS WAIT
sleep 360  # Wait 6 minutes (> STALE_LOCK_TIMEOUT of 300s)

# Step 3: Verify no active V3 executions
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete');
"
# Should return 0

# Step 4: NOW safe to clear remaining V3 locks
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
UPDATE goals
SET execution_engine = NULL,
    execution_started_at = NULL
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete');
"
```

**WHY THIS ORDER:**
- Disabling flag stops NEW V3 executions
- Waiting 5+ minutes ensures ongoing V3 executions complete OR timeout
- Legacy will NOT pick up goals that are still locked (execution_engine IS NOT NULL)
- Clearing locks AFTER wait ensures no race condition

### Step 4: Monitor Recovery

```bash
# Check goals are being processed
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    COUNT(*) FILTER (WHERE status = 'done') as completed,
    COUNT(*) FILTER (WHERE status = 'active') as active,
    COUNT(*) FILTER (WHERE status = 'pending') as pending
FROM goals
WHERE created_at > NOW() - INTERVAL '1 hour';
"
```

---

## 📊 Post-Rollback Analysis

1. Collect logs:
```bash
docker logs ns_core --tail 1000 > rollback_ns_core.log
docker logs ns_core_worker --tail 1000 > rollback_worker.log
```

2. Check database for anomalies:
```bash
# Goals locked > 10 minutes (orphaned)
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT id, title, execution_engine, updated_at
FROM goals
WHERE execution_engine IS NOT NULL
  AND updated_at < NOW() - INTERVAL '10 minutes';
"
```

3. Check for duplicate artifacts:
```bash
# Multiple artifacts for same goal (potential duplicate execution)
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT goal_id, COUNT(*) as artifact_count
FROM artifacts
GROUP BY goal_id
HAVING COUNT(*) > 5
ORDER BY artifact_count DESC
LIMIT 10;
"
```

---

## 🔄 Re-deploy After Fix

Once root cause is identified and fixed:

1. Start with 1% rollout (conservative):
```bash
ENABLE_EXECUTION_V3=true
EXECUTION_V3_PERCENTAGE=1
docker-compose restart core
```

2. Monitor for 24 hours

3. If stable, expand to 5%

4. If stable, expand to 10%

---

## 📞 Escalation

If rollback doesn't resolve issues:

1. Check system health:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/llm/status
```

2. Check database connections:
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "SELECT COUNT(*) FROM pg_stat_activity;"
```

3. Check Redis:
```bash
docker exec ns_redis redis-cli ping
```

4. Check disk space:
```bash
df -h
```

---

## 🔍 Root Cause Analysis

After rollback, analyze:

1. **Logs**: Look for error patterns in `rollback_ns_core.log`
2. **Database**: Check for locked goals, duplicate artifacts
3. **Metrics**: Compare escalation_rate, success_rate to baseline
4. **Code**: Review recent changes to execution_v3.py
5. **Tests**: Run full test suite:
```bash
docker exec ns_core pytest /app/services/core/execution/ -v
```

---

**End of Rollback Plan**
