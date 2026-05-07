# ⚡ Phase 2A Cheat Sheet — Commands Only

**Copy-Paste → Execute**

---

## 🟢 ENABLE 10% (Go-Live)

```bash
# 1. Edit docker-compose.yml
sed -i '/ENABLE_EXECUTION_V3/d' docker-compose.yml && \
sed -i '/ns_core:/a\      ENABLE_EXECUTION_V3: "true"\n      EXECUTION_V3_PERCENTAGE: "10"' docker-compose.yml

# 2. Deploy
./deploy.sh fast

# 3. Verify enabled
docker exec ns_core printenv | grep EXECUTION_V3
```

---

## 🟡 CHECK HEALTH (Every 5 min first 2h)

```bash
./check_v3_health.sh && echo "✅ HEALTHY" || echo "❌ ROLLBACK"
```

---

## 📊 REAL-TIME STATS (Every 30 min)

```bash
./monitor_v3_realtime.sh
```

---

## 🔴 ROLLBACK (Critical Issues)

```bash
# 1. Disable
sed -i 's/ENABLE_EXECUTION_V3: "true"/ENABLE_EXECUTION_V3: "false"/' docker-compose.yml
./deploy.sh fast

# 2. WAIT 6 MIN (CRITICAL!)
sleep 360

# 3. Clear locks
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
UPDATE goals SET execution_engine = NULL, execution_started_at = NULL
WHERE execution_engine = 'v3' AND status NOT IN ('done', 'incomplete');"

# 4. Verify legacy
docker logs ns_core --tail 20 | grep delegating_to_v2
```

---

## 📈 V3 vs Legacy (Last Hour)

```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT execution_engine,
       COUNT(*) as total,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as success_rate
FROM goals
WHERE created_at > NOW() - INTERVAL '1 hour'
  AND execution_engine IS NOT NULL
GROUP BY execution_engine;
"
```

---

## ⏰ STALE LOCKS

```bash
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
"
```

---

## 🔍 V3 LOGS (Last Hour)

```bash
docker logs ns_core --since 1h | grep execution_v3
```

---

## 📊 DAILY SUMMARY

```bash
./daily_summary_v3.sh
```

---

## 🎯 EXPAND TO 30% (After 48h If Green)

```bash
sed -i 's/EXECUTION_V3_PERCENTAGE: "10"/EXECUTION_V3_PERCENTAGE: "30"/' docker-compose.yml
./deploy.sh fast
docker exec ns_core printenv | grep PERCENTAGE
```

---

## ✅ STATUS CHECK (All Green?)

```bash
echo "=== V3 Status ===" && \
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / COUNT(*), 1) as v3_success
FROM goals WHERE execution_engine = 'v3' AND created_at > NOW() - INTERVAL '1 hour';
" && \
echo "=== Traffic % ===" && \
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE execution_engine = 'v3') / COUNT(*), 1) as v3_percent
FROM goals WHERE created_at > NOW() - INTERVAL '1 hour' AND execution_engine IS NOT NULL;
" && \
echo "=== Stale Locks ===" && \
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
"
```

---

**Decision Tree**:
- `check_v3_health.sh` exit 0 → ✅ Continue
- `check_v3_health.sh` exit 1 → ❌ Rollback

**Timeline**: 10% (48h) → Decision → 30% or Stay
