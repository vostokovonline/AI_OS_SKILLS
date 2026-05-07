#!/bin/bash
# V3 Health Check - Critical Rollback Triggers
# Run every 5 minutes for first 2 hours

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ROLLBACK_TRIGGERED=false

echo "=== V3 Health Check ==="
echo "Time: $(date)"
echo ""

# ===================================================================
# CRITICAL CHECK #1: Duplicate Execution
# ===================================================================
echo "🔍 Check #1: Duplicate Execution"
echo "=================================="

DUPLICATES=$(docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT COUNT(*) FROM (
    SELECT id as goal_id FROM goals WHERE execution_engine = 'v3' AND created_at > NOW() - INTERVAL '1 hour'
    INTERSECT
    SELECT goal_id FROM artifacts WHERE created_at > NOW() - INTERVAL '1 hour'
) dupes;
" 2>/dev/null || echo "0")

if [ "$DUPLICATES" -gt "0" ]; then
    echo -e "${RED}❌ CRITICAL: Potential duplicate executions detected: $DUPLICATES${NC}"
    echo -e "${RED}🚨 ACTION REQUIRED: ROLLBACK IMMEDIATELY${NC}"
    ROLLBACK_TRIGGERED=true
else
    echo -e "${GREEN}✅ No duplicate executions${NC}"
fi
echo ""

# ===================================================================
# CRITICAL CHECK #2: V3 Success Rate < 50%
# ===================================================================
echo "📊 Check #2: V3 Success Rate"
echo "=============================="

V3_SUCCESS=$(docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'done') / NULLIF(COUNT(*), 0), 1)
FROM goals
WHERE execution_engine = 'v3'
  AND created_at > NOW() - INTERVAL '1 hour';
" 2>/dev/null || echo "N/A")

if [ "$V3_SUCCESS" != "N/A" ]; then
    if (( $(echo "$V3_SUCCESS < 50" | bc -l) )); then
        echo -e "${RED}❌ CRITICAL: V3 success rate is $V3_SUCCESS% (threshold: 50%)${NC}"
        echo -e "${RED}🚨 ACTION REQUIRED: ROLLBACK IMMEDIATELY${NC}"
        ROLLBACK_TRIGGERED=true
    elif (( $(echo "$V3_SUCCESS < 70" | bc -l) )); then
        echo -e "${YELLOW}⚠️  WARNING: V3 success rate is $V3_SUCCESS% (below 70%)${NC}"
        echo -e "${YELLOW}⚠️  Monitor closely, prepare for rollback${NC}"
    else
        echo -e "${GREEN}✅ V3 success rate is $V3_SUCCESS% (healthy)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No V3 executions in last hour${NC}"
fi
echo ""

# ===================================================================
# CRITICAL CHECK #3: Stale Locks > 10
# ===================================================================
echo "⏰ Check #3: Stale Locks"
echo "========================"

STALE_LOCKS=$(docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
SELECT COUNT(*) FROM goals
WHERE execution_engine = 'v3'
  AND status NOT IN ('done', 'incomplete')
  AND EXTRACT(EPOCH FROM (NOW() - execution_started_at)) > 300;
" 2>/dev/null || echo "0")

if [ "$STALE_LOCKS" -gt "10" ]; then
    echo -e "${RED}❌ CRITICAL: Stale locks count is $STALE_LOCKS (threshold: 10)${NC}"
    echo -e "${RED}🚨 ACTION REQUIRED: ROLLBACK IMMEDIATELY${NC}"
    ROLLBACK_TRIGGERED=true
elif [ "$STALE_LOCKS" -gt "5" ]; then
    echo -e "${YELLOW}⚠️  WARNING: Stale locks count is $STALE_LOCKS (elevated)${NC}"
    echo -e "${YELLOW}⚠️  Monitor worker health${NC}"
else
    echo -e "${GREEN}✅ Stale locks count is $STALE_LOCKS (normal)${NC}"
fi
echo ""

# ===================================================================
# CRITICAL CHECK #4: System Crash
# ===================================================================
echo "💻 Check #4: System Status"
echo "=========================="

CORE_STATUS=$(docker ps --filter name=ns_core --format "{{.Status}}" | head -1)

if echo "$CORE_STATUS" | grep -q "Up"; then
    echo -e "${GREEN}✅ Core service is running${NC}"
else
    echo -e "${RED}❌ CRITICAL: Core service is not running${NC}"
    echo -e "${RED}🚨 ACTION REQUIRED: ROLLBACK IMMEDIATELY${NC}"
    ROLLBACK_TRIGGERED=true
fi
echo ""

# ===================================================================
# WARNING CHECK #1: V3 vs Legacy Success Delta > 10%
# ===================================================================
echo "📈 Check #5: V3 vs Legacy Delta"
echo "================================"

DELTA=$(docker exec ns_postgres psql -U ns_admin -d ns_core_db -t -c "
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
    ROUND(100.0 * (
        (SELECT CAST(success AS FLOAT) / NULLIF(total, 0) FROM metrics WHERE execution_engine = 'v3') -
        (SELECT CAST(success AS FLOAT) / NULLIF(total, 0) FROM metrics WHERE execution_engine = 'legacy')
    ), 1)
FROM metrics;
" 2>/dev/null || echo "N/A")

if [ "$DELTA" != "N/A" ]; then
    DELTA_ABS=$(echo "$DELTA" | tr -d '-')
    if (( $(echo "$DELTA_ABS > 15" | bc -l) )); then
        echo -e "${RED}❌ CRITICAL: Success rate delta is ${DELTA}% (threshold: 15%)${NC}"
        echo -e "${RED}🚨 ACTION REQUIRED: ROLLBACK IMMEDIATELY${NC}"
        ROLLBACK_TRIGGERED=true
    elif (( $(echo "$DELTA_ABS > 10" | bc -l) )); then
        echo -e "${YELLOW}⚠️  WARNING: Success rate delta is ${DELTA}% (elevated)${NC}"
        echo -e "${YELLOW}⚠️  Monitor closely${NC}"
    else
        echo -e "${GREEN}✅ Success rate delta is ${DELTA}% (acceptable)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Cannot calculate delta (insufficient data)${NC}"
fi
echo ""

# ===================================================================
# SUMMARY
# ===================================================================
echo "================================"
echo "=== Health Check Summary ==="
echo "================================"

if [ "$ROLLBACK_TRIGGERED" = true ]; then
    echo -e "${RED}🚨🚨🚨 ROLLBACK TRIGGERED 🚨🚨🚨${NC}"
    echo ""
    echo "Critical issues detected. Execute rollback:"
    echo ""
    echo "1. Disable flag:"
    echo "   docker-compose.yml: ENABLE_EXECUTION_V3=false"
    echo ""
    echo "2. Deploy:"
    echo "   ./deploy.sh fast"
    echo ""
    echo "3. Wait 6 minutes:"
    echo "   sleep 360"
    echo ""
    echo "4. Clear locks:"
    echo "   docker exec ns_postgres psql -U ns_admin -d ns_core_db -c \""
    echo "   UPDATE goals"
    echo "   SET execution_engine = NULL, execution_started_at = NULL"
    echo "   WHERE execution_engine = 'v3' AND status NOT IN ('done', 'incomplete');\""
    echo ""
    echo "See EXECUTION_V3_ROLLBACK.md for details."
    exit 1
else
    echo -e "${GREEN}✅ All checks passed${NC}"
    echo ""
    echo "System is healthy. Continue monitoring."
    exit 0
fi
