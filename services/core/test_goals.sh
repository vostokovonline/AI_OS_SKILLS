#!/bin/bash
# AI_OS Goals Test Suite
# Tests Goal Ontology v3.0 and database structure

echo "🧪 AI_OS Goals Test Suite"
echo "============================================================"
echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================================"

# Database connection
DB_HOST="ns_postgres"
DB_USER="ns_admin"
DB_NAME="ns_core_db"

# Function to execute SQL and get result
execute_sql() {
    docker exec -i ns_postgres psql -U "$DB_USER" -d "$DB_NAME" -t -c "$1"
}

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Test function
run_test() {
    local test_name="$1"
    local sql_query="$2"
    local expected="$3"

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    result=$(execute_sql "$sql_query" | tr -d ' ')

    if [ "$result" = "$expected" ]; then
        echo "✅ $test_name: PASS"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ $test_name: FAIL (got: $result, expected: $expected)"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

echo ""
echo "=== Testing Database Structure ==="

# Test 1: Goals table exists
run_test "Goals table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'goals'" \
    "1"

# Test 2: Artifacts table exists
run_test "Artifacts table exists" \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'artifacts'" \
    "1"

echo ""
echo "=== Testing Goal Ontology v3.0 Columns ==="

# Test 3: goal_type column exists
run_test "goal_type column exists" \
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'goals' AND column_name = 'goal_type'" \
    "1"

# Test 4: depth_level column exists
run_test "depth_level column exists" \
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'goals' AND column_name = 'depth_level'" \
    "1"

# Test 5: is_atomic column exists
run_test "is_atomic column exists" \
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'goals' AND column_name = 'is_atomic'" \
    "1"

# Test 6: domains column exists
run_test "domains column exists" \
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'goals' AND column_name = 'domains'" \
    "1"

# Test 7: completion_criteria column exists
run_test "completion_criteria column exists" \
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'goals' AND column_name = 'completion_criteria'" \
    "1"

# Test 8: goal_contract column exists
run_test "goal_contract column exists" \
    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'goals' AND column_name = 'goal_contract'" \
    "1"

echo ""
echo "=== Testing Test Goals Data ==="

# Test 9: Goals were created
goal_count=$(execute_sql "SELECT COUNT(*) FROM goals")
echo "✅ Total goals created: $goal_count"

# Test 10: Goal types distribution
echo ""
echo "Goal Types Distribution:"
execute_sql "
SELECT
    goal_type,
    COUNT(*) as count
FROM goals
GROUP BY goal_type
ORDER BY goal_type;
" | while read line; do
    if [ -n "$line" ]; then
        echo "  $line"
    fi
done

# Test 11: Depth levels distribution
echo ""
echo "Depth Levels Distribution:"
execute_sql "
SELECT
    'L' || depth_level as level,
    COUNT(*) as count
FROM goals
GROUP BY depth_level
ORDER BY depth_level;
" | while read line; do
    if [ -n "$line" ]; then
        echo "  $line"
    fi
done

# Test 12: Atomic goals count
atomic_count=$(execute_sql "SELECT COUNT(*) FROM goals WHERE is_atomic = true")
echo ""
echo "✅ Atomic goals: $atomic_count"

# Test 13: Goals with parent_id
child_goals=$(execute_sql "SELECT COUNT(*) FROM goals WHERE parent_id IS NOT NULL")
echo "✅ Child goals (with parent): $child_goals"

echo ""
echo "=== Testing Goal Hierarchy ==="

# Test 14: All parent_ids reference existing goals
orphan_count=$(execute_sql "
SELECT COUNT(*)
FROM goals g
LEFT JOIN goals parent ON g.parent_id = parent.id
WHERE g.parent_id IS NOT NULL AND parent.id IS NULL
")

if [ "$orphan_count" = "0" ]; then
    echo "✅ All parents exist (no orphans)"
else
    echo "❌ Found $orphan_count orphan goals"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))
PASSED_TESTS=$((PASSED_TESTS + 1))

echo ""
echo "=== Testing Atomic Goals Requirements ==="

# Test 15: Atomic goals have completion_criteria
atomic_without_criteria=$(execute_sql "
SELECT COUNT(*)
FROM goals
WHERE is_atomic = true
  AND (completion_criteria IS NULL OR completion_criteria = '{}'::jsonb)
")

if [ "$atomic_without_criteria" = "0" ]; then
    echo "✅ All atomic goals have completion criteria"
    PASSED_TESTS=$((PASSED_TESTS + 1))
else
    echo "❌ $atomic_without_criteria atomic goals without completion criteria"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi
TOTAL_TESTS=$((TOTAL_TESTS + 1))

# Test 16: Atomic goals with artifact requirements
atomic_with_artifacts=$(execute_sql "
SELECT COUNT(*)
FROM goals
WHERE is_atomic = true
  AND completion_criteria IS NOT NULL
  AND completion_criteria ? 'artifacts_required'
")

echo "✅ Atomic goals with artifact requirements: $atomic_with_artifacts"

echo ""
echo "=== Testing Goal Contracts ==="

# Test 17: Goals with goal_contract
goals_with_contract=$(execute_sql "
SELECT COUNT(*)
FROM goals
WHERE goal_contract IS NOT NULL
")

echo "✅ Goals with contracts: $goals_with_contract"

echo ""
echo "=== Testing Artifact Layer ==="

# Test 18: Artifacts table structure
artifact_columns=$(execute_sql "
SELECT COUNT(*)
FROM information_schema.columns
WHERE table_name = 'artifacts'
  AND column_name IN ('type', 'goal_id', 'content_kind', 'content_location', 'verification_status')
")

echo "✅ Artifacts table has $artifact_columns/5 critical columns"

# Test 19: Artifacts registered
artifact_count=$(execute_sql "SELECT COUNT(*) FROM artifacts")
echo "✅ Artifacts registered: $artifact_count"

echo ""
echo "=== Sample Goals by Type ==="

for goal_type in meta achievable continuous directional exploratory; do
    echo ""
    echo "$goal_type goals:"
    execute_sql "
    SELECT
        '  L' || depth_level || ': ' || SUBSTRING(title, 1, 60)
    FROM goals
    WHERE goal_type = '$goal_type'
    ORDER BY depth_level, created_at
    LIMIT 3;
    "
done

echo ""
echo "============================================================"
echo "TEST SUMMARY"
echo "============================================================"
echo "Total Tests: $TOTAL_TESTS"
echo "✅ Passed: $PASSED_TESTS"
echo "❌ Failed: $FAILED_TESTS"

if [ $FAILED_TESTS -eq 0 ]; then
    echo ""
    echo "🎉 All tests passed!"
else
    echo ""
    echo "⚠️  $FAILED_TESTS test(s) failed"
fi

echo ""
echo "Finished at: $(date '+%Y-%m-%d %H:%M:%S')"
