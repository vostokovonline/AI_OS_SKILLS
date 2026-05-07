# Execution V3 - Operational Discipline Guide

**Date**: 2026-03-03
**Phase**: 2A - 10% Rollout
**Mindset**: Observation, Not Intervention

---

## 🚨 Most Dangerous Moment: First 30 Real V3 Tasks

**Chaos-test was synthetic. Real production will find new edges.**

### Why First 30 Are Critical

| Aspect | Chaos Test | Real Production |
|--------|------------|-----------------|
| Task variety | 1 test goal | Real user tasks |
| LLM behavior | Mocked | Real API calls |
| Network | localhost | External services |
| Artifacts | None created | Real files/records |
| Edge cases | Controlled | Unknown unknowns |

### Manual Audit Checklist (First 30 V3 Goals)

For each of the first 30 V3 goals:

```bash
# 1. Get V3 goal details
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    id,
    title,
    execution_engine,
    status,
    created_at,
    updated_at,
    EXTRACT(EPOCH FROM (updated_at - created_at)) as duration_seconds
FROM goals
WHERE execution_engine = 'v3'
ORDER BY created_at DESC
LIMIT 5;
"

# 2. Compare output with similar legacy goal
# - Is result qualitatively similar?
# - Are artifacts created correctly?
# - No duplicate artifacts?

# 3. Check logs for anomalies
docker logs ns_core --tail 100 | grep <goal_id>

# 4. Verify no duplicate execution
# - Goal executed only once
# - Only one engine claimed it
# - Artifacts count reasonable
```

### Red Flags (Manual Review)

- ⚠️ Output significantly different from legacy
- ⚠️ Artifacts created but goal status = "incomplete"
- ⚠️ Same goal appears in both V3 and legacy logs
- ⚠️ LLM timeout/retry storms in logs
- ⚠️ Unexpected idempotency violations

**If ANY red flag:** STOP rollout, investigate, do NOT continue.

---

## 🧘 Operational Discipline: The Golden Rules

### Rule #1: Do Not Be a Hero

**Morning after rollout:**
- ☕ Coffee
- 📊 Enable 10%
- 👀 Observe for 2 hours
- 🚫 NO changes unless critical

**What NOT to do:**
- ❌ Do NOT tweak percentage based on 1 hour of data
- ❌ Do NOT hot-fix based on small anomalies
- ❌ Do NOT expand to 30% on day 1
- ❌ Do NOT "optimize" anything

### Rule #2: Metrics ≠ Quality

**Metrics will tell you:**
- System health (success rate, escalation rate)
- Performance (p50, p95)
- Volume (v3_percentage)

**Metrics will NOT tell you:**
- Output quality
- User satisfaction
- Edge cases
- Semantic correctness

**Therefore:** Manual audit of first 30 goals is MANDATORY.

### Rule #3: Decisions on Trends, Not Spikes

| Timeline | Action |
|----------|--------|
| 0-2 hours | OBSERVE ONLY (no matter what) |
| 2-24 hours | Collect data, note anomalies |
| 24-48 hours | Establish baseline |
| 48+ hours | Make data-driven decisions |

**If escalation_rate spikes at hour 3:**
- ❌ Do NOT rollback immediately
- ❌ Do NOT hot-fix
- ✅ Note the time/goal_id
- ✅ Investigate root cause
- ✅ Fix if systemic, ignore if one-off

### Rule #4: Rollback is NOT Failure

**Rollback triggers (IMMEDIATE):**
- Duplicate artifacts reported
- Success rate < 50%
- System crash
- User complaints about corruption

**Rollback is maturity when:**
- Done decisively
- Documented with root cause
- Followed by proper fix (not quick patch)

---

## 📊 Monitoring Dashboard (First 48 Hours)

### Every 30 Minutes (First 2 Hours)

```bash
# Check V3 health
curl -s http://localhost:8000/execution-v3/health | jq .

# Check metrics
curl -s http://localhost:8000/execution-v3/metrics | jq .

# Check for stuck locks
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
"
# Should be 0
```

### Every 2 Hours (First 24 Hours)

```bash
# Compare V3 vs Legacy (same time period)
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    execution_engine,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'done') as success,
    COUNT(*) FILTER (WHERE status = 'incomplete') as failed,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as success_rate
FROM goals
WHERE created_at > NOW() - INTERVAL '2 hours'
  AND execution_engine IS NOT NULL
GROUP BY execution_engine;
"

# Check for duplicate artifacts (same goal_id, multiple artifacts)
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT goal_id, COUNT(*) as artifact_count
FROM artifacts
WHERE goal_id IN (
    SELECT id FROM goals WHERE execution_engine = 'v3' LIMIT 30
)
GROUP BY goal_id
HAVING COUNT(*) > 5
ORDER BY artifact_count DESC
LIMIT 5;
"
```

### Every 6 Hours (First 48 Hours)

```bash
# Full V3 performance report
curl -s http://localhost:8000/execution-v3/metrics | jq .

# Baseline status
curl -s http://localhost:8000/execution-v3/baseline | jq .
```

---

## ⚠️ Thresholds and Actions

### Success Rate

| Value | Action | Rationale |
|-------|--------|-----------|
| >90% | ✅ Normal | System healthy |
| 70-90% | ⚠️ Monitor | Elevated failures, investigate |
| <70% | 🚨 Investigate | System degraded, find root cause |
| <50% | 🛑 Rollback | System broken, critical |

### Escalation Rate

| Value | Action | Rationale |
|-------|--------|-----------|
| <5% | ✅ Normal | Healthy escalation |
| 5-10% | ⚠️ Monitor | Elevated but acceptable |
| 10-20% | 🚨 Investigate | Too many failures |
| >20% | 🛑 Rollback | System not working |

### V3 Percentage

| Value | Action | Rationale |
|-------|--------|-----------|
| 8-12% | ✅ Normal | Correct 10% split |
| 5-8% or 12-15% | ⚠️ Monitor | Slight drift, check hash |
| <5% or >15% | 🚨 Investigate | Hash broken or wrong |
| >20% | 🛑 Rollback | Routing completely wrong |

### Stale Locks

| Value | Action | Rationale |
|-------|--------|-----------|
| 0 | ✅ Normal | No orphaned locks |
| 1-5 | ⚠️ Monitor | Some crashes, check worker health |
| >5 | 🚨 Investigate | Worker instability |
| >10 | 🛑 Rollback | Workers dying en masse |

---

## 🎯 Decision Matrix: To Expand or Not

### After 48 Hours, IF All Green:

```bash
# Criteria for expansion to 30%:
success_rate > 85%  ✅
escalation_rate < 10%  ✅
no_duplicate_artifacts  ✅
warnings = []  ✅
manual_audit_passed  ✅
```

**Then:** Consider expansion to 30%
**Else:** Stay at 10% for another 24 hours

### Expansion Path (IF justified)

```
Day 1: 10% → Observe
Day 2: 10% → Establish baseline
Day 3: 10% → OR expand to 30% (if justified)
Day 4-5: 30% → Observe
Day 6+: 30% → OR expand to 50% (if justified)
Week 2: 50% → OR expand to 100% (if justified)
```

**NEVER skip percentages. NEVER jump 10% → 100%.**

---

## 🛡️ Protection Against Future Drift

### Architectural Guarantees Already in Place

| Guarantee | Implementation | Protected From |
|-----------|----------------|-----------------|
| Timeout calculation | `execution_started_at` ONLY | Heartbeat drift |
| Crash recovery | Stale detection + re-acquire | Worker crashes |
| Duplicate prevention | Atomic lock + execution_engine marking | Race conditions |
| Metric purity | 24h filter | Test data pollution |
| Rollback safety | Wait period before lock clearing | Race conditions |

### Code Comments for Future Developers

```python
# CRITICAL: execution_started_at is ONLY set on lock acquisition.
# DO NOT update this field during execution.
# DO NOT use updated_at for timeout calculation (may be used for metadata/heartbeat).
# Timeout is calculated from execution_started_at to prevent drift.
```

---

## 📝 Daily Log Template (First Week)

```
DATE: YYYY-MM-DD
DAY: X of rollout

=== Morning Status ===
- V3 Percentage: X%
- Success Rate: X%
- Escalation Rate: X%
- Warnings: [count]

=== Anomalies Noted ===
- [Description]
- [Time]
- [Goal ID if applicable]

=== Manual Audit (First 30) ===
- Goals reviewed: X/30
- Quality issues: X
- Duplicate artifacts: X
- Output differences: X

=== Decisions Made ===
- [Action taken]
- [Rationale]

=== Tomorrow's Plan ===
- [What to monitor]
- [What to investigate]
```

---

## 🧠 Final Mindset

**You are NOT:**
- ❌ Trying to prove V3 is better
- ❌ Looking for reasons to expand faster
- ❌ Optimizing based on small data
- ❌ Being a hero who "fixed production"

**You ARE:**
- ✅ Observing system behavior
- ✅ Collecting clean data
- ✅ Protecting against failures
- ✅ Making data-driven decisions
- ✅ Ready to rollback if needed

**The goal is not successful rollout.**
**The goal is reliable system.**

Sometimes the most professional decision is:
*"This doesn't look right, I'm rolling back."*

---

**End of Operational Discipline Guide**

Remember: Chaos-test proved crash recovery works.
Real production will test everything else.
Stay calm. Observe. Don't hero.
