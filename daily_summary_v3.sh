#!/bin/bash
# V3 Daily Summary
# Run once per day (recommended: morning)

set -e

DATE=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)

echo "=== V3 Daily Summary - $DATE ==="
echo ""

# Full day comparison (yesterday)
echo "📊 Full Day Stats (Yesterday: $YESTERDAY)"
echo "========================================="
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    execution_engine,
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE status = 'done') as success,
    COUNT(*) FILTER (WHERE status = 'incomplete') as failed,
    COUNT(*) FILTER (WHERE status = 'active') as active,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / NULLIF(COUNT(*), 0), 1) as success_rate,
    ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as avg_duration_seconds,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as p50_duration,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM (updated_at - created_at))), 1) as p95_duration
FROM goals
WHERE date(created_at) = '$YESTERDAY'
  AND execution_engine IS NOT NULL
GROUP BY execution_engine
ORDER BY execution_engine;
"
echo ""

# Success rate delta
echo "📈 Success Rate Delta (V3 vs Legacy)"
echo "======================================"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
WITH metrics AS (
    SELECT
        execution_engine,
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE status = 'done') as success
    FROM goals
    WHERE date(created_at) = '$YESTERDAY'
      AND execution_engine IS NOT NULL
    GROUP BY execution_engine
)
SELECT
    ROUND(100.0 * (
        (SELECT CAST(success AS FLOAT) / NULLIF(total, 0) FROM metrics WHERE execution_engine = 'v3') -
        (SELECT CAST(success AS FLOAT) / NULLIF(total, 0) FROM metrics WHERE execution_engine = 'legacy')
    ), 1) as success_rate_delta_percent;
"
echo ""

# V3 traffic percentage
echo "🎯 V3 Traffic Percentage (Yesterday)"
echo "====================================="
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE execution_engine = 'v3') / NULLIF(COUNT(*), 0), 1) as v3_percent,
    COUNT(*) as total_goals
FROM goals
WHERE date(created_at) = '$YESTERDAY'
  AND execution_engine IS NOT NULL;
"
echo ""

# Stale locks peak
echo "⏰ Stale Locks Peak Count (Yesterday)"
echo "======================================"
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    COUNT(*) as stale_locks_count
FROM goals
WHERE date(created_at) = '$YESTERDAY'
  AND execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
"
echo ""

# Hourly breakdown (peak times)
echo "⏰ Hourly Execution Breakdown (Yesterday)"
echo "=========================================="
docker exec ns_postgres psql -U ns_admin -d ns_core_db -c "
SELECT
    EXTRACT(HOUR FROM created_at) as hour,
    execution_engine,
    COUNT(*) as count
FROM goals
WHERE date(created_at) = '$YESTERDAY'
  AND execution_engine IS NOT NULL
GROUP BY hour, execution_engine
ORDER BY hour, execution_engine;
"
echo ""

# First 30 V3 goals (for manual audit)
echo "🔍 First 30 V3 Goals (Yesterday)"
echo "================================="
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
WHERE date(created_at) = '$YESTERDAY'
  AND execution_engine = 'v3'
ORDER BY created_at
LIMIT 30;
"
echo ""

echo "=== Daily Summary Complete ==="
echo ""
echo "📝 Log file: /tmp/v3_daily_summary_$DATE.txt"
