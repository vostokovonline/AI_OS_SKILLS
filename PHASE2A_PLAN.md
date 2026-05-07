# Phase 2A Rollout Plan - 10% Traffic

**Date**: 2026-03-03
**Status**: Ready to execute
**Confidence**: 100% (architecture verified)

---

## 🎯 Objective

Safely roll out Execution V3 to 10% of atomic goals while collecting baseline metrics.

**Success Criteria**:
- No duplicate goal execution
- No increase in p95 latency > 20%
- No decrease in success rate > 5%
- Clean rollback if needed

---

## 📋 Pre-Rollout Checklist

### 1. Architecture Verification
- [x] V3 accepts uow, not db_session
- [x] One UOW = One commit invariant
- [x] Lock lifecycle atomic (acquire → execute → cleanup)
- [x] Return contract enforced (None pre-lock, result/exception post-lock)
- [x] No dual session issues
- [x] System deployed and online

### 2. Monitoring Setup
- [ ] V3 metrics endpoint accessible
- [ ] Log aggregation configured
- [ ] Dashboard queries prepared
- [ ] Alert thresholds defined
- [ ] Rollback procedure documented

### 3. Database Verification
```bash
# Check goals table has execution_engine column
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
\d goals
" | grep execution_engine
```

### 4. Feature Flags
```bash
# Verify V3 is disabled (safe default)
docker exec ns_core printenv | grep ENABLE_EXECUTION_V3
# Should return empty or "false"
```

---

## 🚀 Rollout Steps

### Step 1: Enable V3 (10% traffic)

**File**: `docker-compose.yml`

```yaml
services:
  ns_core:
    environment:
      ENABLE_EXECUTION_V3: "true"
      EXECUTION_V3_PERCENTAGE: "10"
      EXECUTION_V3_STALE_LOCK_TIMEOUT: "300"  # 5 minutes
      BASELINE_OBSERVATION_HOURS: "48"
```

**Apply**:
```bash
./deploy.sh fast
```

**Verify**:
```bash
docker exec ns_core printenv | grep EXECUTION_V3
# Expected:
# ENABLE_EXECUTION_V3=true
# EXECUTION_V3_PERCENTAGE=10
```

---

### Step 2: Immediate Verification (First 15 minutes)

Run these commands every 5 minutes for the first 15 minutes:

```bash
# 1. Check V3 is executing
docker logs ns_core --tail 100 | grep "execution_v3_start" | wc -l
# Expected: > 0 (increasing)

# 2. Check for errors
docker logs ns_core --tail 100 | grep "execution_v3_error" | wc -l
# Expected: 0

# 3. Check V3 completions
docker logs ns_core --tail 100 | grep "execution_v3_complete" | wc -l
# Expected: > 0 (increasing)

# 4. Check lock acquisitions
docker logs ns_core --tail 100 | grep "lock_acquired" | wc -l
# Expected: > 0

# 5. Check lock cleanups
docker logs ns_core --tail 100 | grep "lock_cleaned" | wc -l
# Expected: Should match lock_acquisitions (minus active)
```

**If ANY error found**: Stop and investigate (see Rollback section)

---

### Step 3: First 30 Goals (Manual Audit)

For each of the first 30 V3 goals, verify:

```bash
# Get V3 goals
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    id,
    title,
    execution_engine,
    status,
    progress,
    created_at,
    updated_at,
    EXTRACT(EPOCH FROM (updated_at - created_at)) as duration_seconds
FROM goals
WHERE execution_engine = 'v3'
ORDER BY created_at DESC
LIMIT 30;
"
```

**For each goal**:
- [ ] Status is 'done' or 'incomplete' (not stuck in 'active')
- [ ] Progress is 0.0 to 1.0 (not NULL)
- [ ] Duration is reasonable (< 5 minutes for atomic goals)
- [ ] Artifacts registered (see below)
- [ ] No duplicate execution (same goal executed twice)

**Check artifacts**:
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    g.id as goal_id,
    g.title,
    COUNT(a.id) as artifact_count
FROM goals g
LEFT JOIN artifacts a ON g.id = a.goal_id
WHERE g.execution_engine = 'v3'
GROUP BY g.id, g.title
ORDER BY g.created_at DESC
LIMIT 30;
"
```

**Expected**:
- Each V3 goal has 0+ artifacts
- No goal has suspicious artifact count (> 10)

---

### Step 4: Baseline Collection (48 hours)

During the first 48 hours, collect metrics every hour:

```bash
#!/bin/bash
# collect_baseline.sh - Run every hour

TIMESTAMP=$(date +%s)
HOUR=$(( $(date +%H) ))

echo "=== Baseline Collection - Hour $HOUR ==="

# V3 vs Legacy comparison
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    execution_engine,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'done') as success,
    COUNT(*) FILTER (WHERE status = 'incomplete') as failed,
    COUNT(*) FILTER (WHERE status = 'active') as active,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as success_rate,
    ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as avg_duration_seconds
FROM goals
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND execution_engine IS NOT NULL
GROUP BY execution_engine
ORDER BY execution_engine;
" > /tmp/baseline_v3_vs_legacy_$TIMESTAMP.txt

# V3 percentage check
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE execution_engine = 'v3') / COUNT(*), 1) as v3_percentage,
    COUNT(*) as total_goals
FROM goals
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND execution_engine IS NOT NULL;
" >> /tmp/baseline_v3_vs_legacy_$TIMESTAMP.txt

# Stale locks check
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) as stale_locks
FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
" >> /tmp/baseline_v3_vs_legacy_$TIMESTAMP.txt

echo "Baseline collected: /tmp/baseline_v3_vs_legacy_$TIMESTAMP.txt"
```

**Schedule with cron**:
```bash
# Run every hour
crontab -e
# Add: 0 * * * * /home/onor/ai_os_final/collect_baseline.sh
```

---

## 📊 Metrics to Monitor

### Critical Metrics

| Metric | Source | Good | Warning | Critical | Action |
|--------|--------|------|---------|----------|--------|
| **V3 Percentage** | DB query | 8-12% | 5-8% or 12-15% | <5% or >15% | Check hash logic |
| **V3 Success Rate** | DB query | >90% | 70-90% | <70% | Investigate failures |
| **Legacy Success Rate** | DB query | >90% | 70-90% | <70% | System degraded |
| **V3 Avg Duration** | DB query | <120s | 120-300s | >300s | Performance issue |
| **Legacy Avg Duration** | DB query | <120s | 120-300s | >300s | System degraded |
| **Stale Locks** | DB query | 0 | 1-5 | >5 | Worker instability |
| **V3 vs Legacy Success Delta** | Calculation | <5% | 5-10% | >10% | V3 degraded |

### Calculation Queries

```bash
# V3 vs Legacy Success Rate Delta
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
WITH metrics AS (
    SELECT
        execution_engine,
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE status = 'done') as success
    FROM goals
    WHERE created_at > NOW() - INTERVAL '1 hour'
      AND execution_engine IS NOT NULL
    GROUP BY execution_engine
)
SELECT
    ROUND(
        100.0 * (
            (SELECT CAST(success AS FLOAT) / NULLIF(total, 0) FROM metrics WHERE execution_engine = 'v3') -
            (SELECT CAST(success AS FLOAT) / NULLIF(total, 0) FROM metrics WHERE execution_engine = 'legacy')
        ),
        1
    ) as success_rate_delta_percent;
"
```

---

## 🚨 Alert Thresholds

### Immediate Rollback Triggers

If ANY of these occur, rollback immediately:

1. **Duplicate Execution Detected**
   ```bash
   # Check for same goal executed twice
   docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
   SELECT goal_id, COUNT(*) as executions
   FROM (
       SELECT id as goal_id FROM goals WHERE execution_engine = 'v3'
       UNION ALL
       SELECT goal_id FROM artifacts WHERE created_at > NOW() - INTERVAL '1 hour'
   ) dupes
   GROUP BY goal_id
   HAVING COUNT(*) > 1;
   "
   # If any result → ROLLBACK
   ```

2. **V3 Success Rate < 50%**
   ```bash
   docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
   SELECT
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as v3_success_rate
   FROM goals
   WHERE created_at > NOW() - INTERVAL '1 hour'
     AND execution_engine = 'v3';
   "
   # If < 50 → ROLLBACK
   ```

3. **Stale Locks > 10**
   ```bash
   docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
   SELECT COUNT(*) FROM goals
   WHERE execution_engine = 'v3'
     AND status NOT IN ('done', 'incomplete')
     AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
   "
   # If > 10 → ROLLBACK
   ```

4. **System Crash**
   ```bash
   docker ps --filter name=ns_core
   # If not "Up" → ROLLBACK
   ```

---

## 🔄 Rollback Procedure

### Immediate Rollback (Critical Issues)

**Step 1**: Disable flag
```bash
# Edit docker-compose.yml
environment:
  ENABLE_EXECUTION_V3: "false"  # Change to false

# Deploy
./deploy.sh fast
```

**Step 2**: WAIT for active V3 executions to complete
```bash
# CRITICAL: Do NOT skip this wait
sleep 360  # Wait 6 minutes (> STALE_LOCK_TIMEOUT of 300s)
```

**Step 3**: Verify no active V3 executions
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete');
"
# Should return 0
```

**Step 4**: Clear remaining V3 locks
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
UPDATE goals
SET execution_engine = NULL,
    execution_started_at = NULL
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete');
"
```

**Step 5**: Verify legacy is processing
```bash
docker logs ns_core --tail 50 | grep "delegating_to_v2"
# Should see entries
```

---

## 📈 Expansion Decision Matrix

### After 48 Hours, If All Green:

**Criteria for expansion to 30%**:
```bash
v3_success_rate > 85%  ✅
v3_vs_legacy_delta < 10%  ✅
stale_locks < 3  ✅
no_duplicates  ✅
warnings = []  ✅
manual_audit_passed  ✅
```

**If met**: Can expand to 30%

**Else**: Stay at 10% for another 24 hours

### Expansion Path (If Justified)

```
Day 1-2: 10% → Observe, collect baseline
Day 3-4: 10% → OR expand to 30% (if justified)
Day 5-7: 30% → Observe
Day 8+: 30% → OR expand to 50% (if justified)
Week 2: 50% → OR expand to 100% (if justified)
```

**NEVER skip percentages. NEVER jump 10% → 100%.**

---

## 🔍 Daily Log Template

```
DATE: YYYY-MM-DD
DAY: X of Phase 2A rollout

=== Morning Status ===
- V3 Percentage: X%
- V3 Success Rate: X%
- Legacy Success Rate: X%
- Delta: X%
- Stale Locks: X
- V3 Avg Duration: Xs
- Legacy Avg Duration: Xs

=== Anomalies Noted ===
- [Description]
- [Time]
- [Goal ID if applicable]

=== Manual Audit (First 30) ===
- Goals reviewed: X/30
- Quality issues: X
- Duplicate artifacts: X
- Output differences: X
- Stuck goals: X

=== Decisions Made ===
- [Action taken]
- [Rationale]

=== Tomorrow's Plan ===
- [What to monitor]
- [What to investigate]
- [Adjustments if any]
```

---

## 📝 Monitoring Scripts

### Real-time Monitoring (Every 30 min first 2 hours)

```bash
#!/bin/bash
# monitor_v3_realtime.sh

echo "=== V3 Real-time Monitoring ==="

# V3 execution count
echo "V3 Executions (last 30 min):"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND created_at > NOW() - INTERVAL '30 minutes';
"

# V3 success rate
echo "V3 Success Rate (last 30 min):"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as success_rate
FROM goals
WHERE execution_engine = 'v3'
  AND created_at > NOW() - INTERVAL '30 minutes';
"

# Stale locks
echo "Stale Locks:"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
"

# V3 percentage
echo "V3 Traffic Percentage:"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE execution_engine = 'v3') / COUNT(*), 1) as v3_percent
FROM goals
WHERE created_at > NOW() - INTERVAL '30 minutes'
  AND execution_engine IS NOT NULL;
"
```

### Daily Summary

```bash
#!/bin/bash
# daily_summary.sh

DATE=$(date +%Y-%m-%d)
echo "=== V3 Daily Summary - $DATE ==="

# Full day stats
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    execution_engine,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'done') as success,
    COUNT(*) FILTER (WHERE status = 'incomplete') as failed,
    COUNT(*) FILTER (WHERE status = 'active') as active,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as success_rate,
    ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as avg_duration_seconds,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as p50_duration,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as p95_duration
FROM goals
WHERE date(created_at) = CURRENT_DATE
  AND execution_engine IS NOT NULL
GROUP BY execution_engine
ORDER BY execution_engine;
"
```

---

## 🎯 Success Metrics (After 48h)

### Primary Indicators

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| V3 Traffic % | 8-12% | ___ | ___ |
| V3 Success Rate | >85% | ___ | ___ |
| V3 vs Legacy Delta | <10% | ___ | ___ |
| Stale Locks | <3 | ___ | ___ |
| Duplicate Executions | 0 | ___ | ___ |
| P95 Latency Increase | <20% | ___ | ___ |

### Go/No-Go Decision

**GO if**:
- All primary indicators in green
- Manual audit of first 30 passed
- No red flags in logs
- Team confident

**NO-GO if**:
- Any primary indicator red
- Duplicate execution detected
- Success rate delta > 15%
- Team not confident

---

## 📞 Escalation

### If Rollback Doesn't Fix Issues

1. Check system health:
```bash
curl http://localhost:8000/health
docker ps
```

2. Check database:
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "SELECT COUNT(*) FROM pg_stat_activity;"
```

3. Check for long-running queries:
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT pid, now() - query_start as duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;
"
```

4. Full system restart:
```bash
docker-compose restart core
```

---

## 📚 Documentation

- **Architecture**: `EXECUTION_V3_ARCHITECTURE_FIXED.md`
- **Rollback**: `EXECUTION_V3_ROLLBACK.md`
- **Operational Discipline**: `OPERATIONAL_DISCIPLINE.md`
- **Integration**: `EXECUTION_V3_INTEGRATION_COMPLETE.md`

---

**End of Phase 2A Rollout Plan**

Remember: Observation, not intervention. Let the system speak through metrics.
