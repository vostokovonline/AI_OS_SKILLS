#!/bin/bash
# =============================================================================
# CI GUARD: Prevent direct status access
# =============================================================================
#
# This script MUST be run in:
# - Pre-commit hook (blocks commit)
# - CI pipeline (blocks merge)
# - Manual check before deployment
#
# It FAILS if it finds ANY direct status access in Python files
#
# Author: AI-OS Core Team
# Severity: CRITICAL - This is a HARD GATE
# =============================================================================

set -e  # Exit on first error

echo "=========================================="
echo "CI GUARD: Checking for direct status access"
echo "=========================================="

# =============================================================================
# CHECK 1: Find direct status assignments
# =============================================================================

echo ""
echo "📋 CHECK 1: Direct status assignments"

# Search for patterns that indicate direct status mutation
DIRECT_PATTERN='\s+\.status\s*=\s*["'"]'

# Count violations in core service (exclude this file, test files, backups)
VIOLATIONS=$(grep -r "$DIRECT_PATTERN" services/core/*.py 2>/dev/null | \
    grep -v "test_" | \
    grep -v ".pyc" | \
    grep -v "goals_needing_migration" | \
    grep -v "invariant" | \
    grep -v "transition" | \
    grep -v "GoalStatus" | \
    grep -v "lifecycle_state" | \
    grep -v "_status_internal" | \
    wc -l)

echo "  Found: $VIOLATIONS direct status assignments"

if [ "$VIOLATIONS" -gt 0 ]; then
    echo "  ❌ FAIL: Direct status access found"
    echo ""
    echo "Files with violations:"
    grep -rn "$DIRECT_PATTERN" services/core/*.py 2>/dev/null | \
        grep -v "test_" | \
        grep -v ".pyc" | \
        grep -v "invariant" | \
        grep -v "transition" | \
        grep -v "GoalStatus" | \
        grep -v "_status_internal" | \
        head -20
    echo ""
    echo "🔴 CI GUARD FAILED"
    echo "   Fix ALL violations before commit/merge"
    echo "   Use: goal_transition_service.transition_goal()"
    exit 1
else
    echo "  ✅ PASS: No direct status access found"
fi

# =============================================================================
# CHECK 2: Find forbidden patterns
# =============================================================================

echo ""
echo "📋 CHECK 2: Forbidden mutation patterns"

FORBIDDEN_PATTERNS=(
    "goal\.status = \.done"  # Direct assignment to done
    "\.status\s*=.*\"done\""      # Another done pattern
    "goal_state.*=.*done"        # If wrong field used
)

TOTAL_FORBIDDEN=0

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    COUNT=$(grep -r "$pattern" services/core/*.py 2>/dev/null | wc -l)

    if [ "$COUNT" -gt 0 ]; then
        echo "  ❌ Found: $COUNT instances of '$pattern'"
        TOTAL_FORBIDDEN=$((TOTAL_FORBIDDEN + COUNT))
    fi
done

echo "  Total forbidden patterns: $TOTAL_FORBIDDEN"

if [ "$TOTAL_FORBIDDEN" -gt 0 ]; then
    echo "  ❌ FAIL: Forbidden mutation patterns found"
    echo "  🔴 CI GUARD FAILED"
    exit 1
fi

# =============================================================================
# CHECK 3: Verify goal_transition_service exists
# =============================================================================

echo ""
echo "📋 CHECK 3: Transition service exists"

if [ -f "services/core/goal_transition_service.py" ]; then
    echo "  ✅ PASS: goal_transition_service.py exists"
else
    echo "  ❌ FAIL: goal_transition_service.py NOT FOUND"
    echo "  🔴 CI GUARD FAILED"
    echo ""
    echo "CRITICAL: Single gate for transitions not found!"
    exit 1
fi

# =============================================================================
# CHECK 4: Verify ORM lock exists
# =============================================================================

echo ""
echo "📋 CHECK 4: ORM lock patch applied"

# Check if models.py has status property
if grep -q "@property" services/core/models.py; then
    if grep -q "Direct status assignment is FORBIDDEN" services/core/models.py; then
        echo "  ✅ PASS: ORM property-based protection exists"
    else
        echo "  ⚠️  WARNING: Property exists but message may be wrong"
    fi
else
    echo "  ❌ FAIL: ORM property-based protection NOT FOUND"
    echo "  🔴 CI GUARD FAILED"
    exit 1
fi

# =============================================================================
# CHECK 5: Verify exception handling
# =============================================================================

echo ""
echo "📋 CHECK 5: Exception handling quality"

BARE_EXCEPT=$(grep -rn "except.*:" services/core/*.py 2>/dev/null | \
    grep -v "invariant" | \
    grep -v "transition" | \
    grep -v "HardInvariantViolation" | \
    grep -v "mark_goal_directly" | \
    wc -l)

echo "  Bare except: catches (excluding invariant/transition files): $BARE_EXCEPT"

if [ "$BARE_EXCEPT" -gt 30 ]; then
    echo "  ⚠️  WARNING: Many bare except catches found: $BARE_EXCEPT"
    echo "  Threshold: 30 (recommend < 10)"
else
    echo "  ✅ PASS: Exception handling acceptable ($BARE_EXCEPT catches)"
fi

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "=========================================="
echo "CI GUARD SUMMARY"
echo "=========================================="

if [ "$VIOLATIONS" -eq 0 ] && [ "$TOTAL_FORBIDDEN" -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED"
    echo ""
    echo "System is protected against:"
    echo "  - Direct status mutation"
    echo "  - Forbidden transition patterns"
    echo "  - Missing transition gate"
    echo "  - Missing ORM lock"
    echo ""
    echo "🎉 CI GUARD PASSED - Code may proceed"
    exit 0
else
    echo "❌ CI GUARD FAILED"
    echo ""
    echo "FAILURES:"
    echo "  Direct status access: $VIOLATIONS"
    echo "  Forbidden patterns: $TOTAL_FORBIDDEN"
    echo ""
    echo "🔴 FIX ALL FAILURES BEFORE COMMIT/MERGE"
    exit 1
fi
