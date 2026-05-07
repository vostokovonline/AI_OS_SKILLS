#!/bin/bash
# V3 Real-time Monitoring
# Run every 30 minutes for first 2 hours, then every 2 hours

set -e

echo "=== V3 Real-time Monitoring ==="
echo "Time: $(date)"
echo ""

# V3 execution count (last 30 min)
echo "📊 V3 Executions (last 30 min):"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND created_at > NOW() - INTERVAL '30 minutes';
" 2>/dev/null || echo "0"
echo ""

# V3 success rate (last 30 min)
echo "✅ V3 Success Rate (last 30 min):"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / NULLIF(COUNT(*), 0), 1) as success_rate
FROM goals
WHERE execution_engine = 'v3'
  AND created_at > NOW() - INTERVAL '30 minutes';
" 2>/dev/null || echo "N/A"
echo ""

# Legacy success rate (comparison)
echo "🔄 Legacy Success Rate (last 30 min):"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / NULLIF(COUNT(*), 0), 1) as success_rate
FROM goals
WHERE execution_engine = 'legacy'
  AND created_at > NOW() - INTERVAL '30 minutes';
" 2>/dev/null || echo "N/A"
echo ""

# Stale locks
echo "⏰ Stale Locks (> 5 min, not done):"
STALE_COUNT=$(docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
" 2>/dev/null || echo "0")

echo "$STALE_COUNT"

if [ "$STALE_COUNT" -gt "5" ]; then
    echo "⚠️  WARNING: Stale locks > 5"
fi
echo ""

# V3 traffic percentage
echo "🎯 V3 Traffic Percentage (last 30 min):"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE execution_engine = 'v3') / NULLIF(COUNT(*), 0), 1) as v3_percent
FROM goals
WHERE created_at > NOW() - INTERVAL '30 minutes'
  AND execution_engine IS NOT NULL;
" 2>/dev/null || echo "N/A"
echo ""

# Active V3 goals
echo "🔄 Active V3 Goals:"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status = 'active';
" 2>/dev/null || echo "0"
echo ""

# Recent errors (last 30 min)
echo "❌ Recent Errors (last 30 min):"
docker logs ns_core --since 30m 2>&1 | grep -i "execution_v3_error" | wc -l
echo ""

echo "=== Monitoring Complete ==="
