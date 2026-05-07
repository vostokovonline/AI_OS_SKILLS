# Phase 2A Quick Reference

**Enable**: `docker-compose.yml` → `ENABLE_EXECUTION_V3: "true"`
**Deploy**: `./deploy.sh fast`
**Monitor**: `./check_v3_health.sh`

---

## 🚀 Quick Start

### Enable 10% Rollout
```bash
# 1. Edit docker-compose.yml
nano docker-compose.yml
# Add: ENABLE_EXECUTION_V3: "true"
#     EXECUTION_V3_PERCENTAGE: "10"

# 2. Deploy
./deploy.sh fast

# 3. Verify
docker exec ns_core printenv | grep EXECUTION_V3
```

### Monitor Health (Every 5 min first 2 hours)
```bash
./check_v3_health.sh
# Exit 0 = All good
# Exit 1 = Rollback needed
```

### Real-time Stats (Every 30 min)
```bash
./monitor_v3_realtime.sh
```

### Daily Summary
```bash
./daily_summary_v3.sh
```

---

## 🚨 Immediate Rollback

```bash
# 1. Disable flag
# Edit docker-compose.yml: ENABLE_EXECUTION_V3: "false"
./deploy.sh fast

# 2. WAIT 6 minutes (critical!)
sleep 360

# 3. Clear locks
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
UPDATE goals
SET execution_engine = NULL, execution_started_at = NULL
WHERE execution_engine = 'v3' AND status NOT IN ('done', 'incomplete');
"

# 4. Verify legacy processing
docker logs ns_core --tail 50 | grep delegating_to_v2
```

---

## 📊 Critical Metrics

| Metric | Check | Good | Bad | Action |
|--------|-------|------|-----|--------|
| **Duplicates** | `check_v3_health.sh` | 0 | >0 | Rollback |
| **V3 Success** | `check_v3_health.sh` | >70% | <50% | Rollback |
| **Stale Locks** | `check_v3_health.sh` | <5 | >10 | Rollback |
| **System** | `docker ps` | Up | Down | Rollback |
| **Delta** | `check_v3_health.sh` | <10% | >15% | Rollback |

---

## 🔍 Manual Queries

### V3 vs Legacy (Last hour)
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    execution_engine,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'done') as success,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as success_rate
FROM goals
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND execution_engine IS NOT NULL
GROUP BY execution_engine;
"
```

### First 30 V3 Goals
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT id, title, status, progress, created_at, updated_at
FROM goals
WHERE execution_engine = 'v3'
ORDER BY created_at DESC
LIMIT 30;
"
```

### Active V3 Locks
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT id, title, execution_started_at, status
FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
ORDER BY execution_started_at;
"
```

### Recent V3 Logs
```bash
docker logs ns_core --since 1h | grep "execution_v3"
```

---

## ⏰ Timeline

| Time | Action | Frequency |
|------|--------|-----------|
| 0-15 min | `check_v3_health.sh` | Every 5 min |
| 15-120 min | `check_v3_health.sh` | Every 15 min |
| 0-48h | `monitor_v3_realtime.sh` | Every 30 min |
| Daily | `daily_summary_v3.sh` | Once per day |
| 48h | Decision: expand to 30% or stay | - |

---

## ✅ Go/No-Go (After 48h)

### GO if:
- [ ] Success rate > 85%
- [ ] Delta < 10%
- [ ] Stale locks < 3
- [ ] No duplicates
- [ ] Manual audit passed

### NO-GO if:
- [ ] Any metric red
- [ ] Duplicates detected
- [ ] Team not confident
- [ ] < 48h baseline

---

## 📞 Emergency

### System not responding
```bash
docker-compose restart core
```

### Database issues
```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "SELECT 1;"
```

### Full logs
```bash
docker logs ns_core --tail 500 > ns_core_debug.log
```

---

## 📚 Docs

- **Plan**: `PHASE2A_PLAN.md`
- **Architecture**: `EXECUTION_V3_ARCHITECTURE_FIXED.md`
- **Rollback**: `EXECUTION_V3_ROLLBACK.md`
- **Operations**: `OPERATIONAL_DISCIPLINE.md`

---

**Remember**: Observation, not intervention. Let metrics speak.
