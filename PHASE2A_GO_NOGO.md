# 🚦 Phase 2A Go/No-Go — 10% Rollout

**Date**: `__________` | **Owner**: `__________`

---

## ⚡ Pre-Rollout (2 min)

| Check | Expected | ✅/❌ |
|-------|----------|------|
| `docker-compose.yml` has `ENABLE_EXECUTION_V3: "true"` | ✅ | `⬜` |
| `EXECUTION_V3_PERCENTAGE: "10"` | ✅ | `⬜` |
| Scripts executable (`chmod +x *.sh`) | ✅ | `⬜` |
| Smoke test passed | ✅ | `⬜` |
| Rollback procedure ready | ✅ | `⬜` |

**Pre-Rollout Status**: `⬜ ALL CHECKED` → Proceed OR ❌ STOP

---

## 🚀 Deployment (3 min)

```bash
# 1. Enable flag
nano docker-compose.yml  # Add flags above

# 2. Deploy
./deploy.sh fast

# 3. Verify
docker exec ns_core printenv | grep EXECUTION_V3
# Expected: ENABLE_EXECUTION_V3=true, EXECUTION_V3_PERCENTAGE=10

# 4. Start monitoring
./check_v3_health.sh  # Run every 5 min for 2 hours
```

---

## 📊 Critical Metrics (First 48h)

| Metric | Check | Go | No-Go | Rollback |
|--------|-------|-----|-------|----------|
| **V3 Success Rate** | `check_v3_health.sh` | ≥85% | 70-85% | <70% |
| **Delta (V3 vs Legacy)** | `check_v3_health.sh` | <10% | 10-15% | >15% |
| **Stale Locks** | `check_v3_health.sh` | 0-2 | 3-5 | >5 |
| **Duplicates** | `check_v3_health.sh` | 0 | 0 | >0 |
| **Traffic %** | `monitor_v3_realtime.sh` | 8-12% | 5-8% or 12-15% | <5% or >15% |
| **System Status** | `docker ps` | Up | Up | Down |

**Status**: `⬜ ALL GREEN` → Continue OR ❌ ROLLBACK

---

## ⏰ Monitoring Schedule

| Time | Script | Interval |
|------|--------|----------|
| 0-2 hours | `check_v3_health.sh` | Every 5 min |
| 2-48 hours | `check_v3_health.sh` | Every 15 min |
| 0-48 hours | `monitor_v3_realtime.sh` | Every 30 min |
| Daily | `daily_summary_v3.sh` | Once per day |

---

## 🎯 Decision Point (48 Hours)

### Expand to 30% IF:
- [ ] All metrics green (48h baseline)
- [ ] Manual audit passed (first 30 goals)
- [ ] Success rate ≥85%
- [ ] Delta <10%
- [ ] No duplicates
- [ ] Team confident

**Go/No-Go**: `⬜ GO` → Set `EXECUTION_V3_PERCENTAGE: "30"` OR `⬜ NO-GO` → Stay at 10%

---

## 🚨 Immediate Rollback (If Any Red)

```bash
# 1. Disable flag (docker-compose.yml)
ENABLE_EXECUTION_V3: "false"

# 2. Deploy
./deploy.sh fast

# 3. WAIT 6 minutes (CRITICAL!)
sleep 360

# 4. Clear locks
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
UPDATE goals
SET execution_engine = NULL, execution_started_at = NULL
WHERE execution_engine = 'v3' AND status NOT IN ('done', 'incomplete');
"

# 5. Verify legacy processing
docker logs ns_core | grep delegating_to_v2
```

---

## ✅ Sign-Off

**Pre-Rollout**: `__________` | **Post-Rollout (48h)**: `__________`

**Status**: `⬜ GO-LIVE` OR ❌ `ABORTED`

---

**Quick Commands**:
```bash
./check_v3_health.sh          # Health check
./monitor_v3_realtime.sh      # Real-time stats
./daily_summary_v3.sh         # Daily summary
docker logs ns_core | grep v3 # V3 logs
```
