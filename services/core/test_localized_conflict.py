"""Test LOCALIZED conflict penalty."""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4
from autonomy.propositions import (
    Proposition, GoalPattern, MatchMode,
    reset_propositions, get_proposition_store
)
from autonomy.conflicts import (
    get_conflict_detector, apply_conflict_penalty, reset_conflict_detector
)

# Reset
reset_propositions()
reset_conflict_detector()
store = get_proposition_store()

print("=" * 70)
print("LOCALIZED CONFLICT PENALTY TEST")
print("=" * 70)

# Create CONFLICT in world state
api_id = str(uuid4())
p1 = Proposition(
    id=uuid4(),
    subject_type="api",
    subject_id=api_id,
    predicate="responds",
    value=True,
    confidence=0.9
)
p2 = Proposition(
    id=uuid4(),
    subject_type="api",
    subject_id=api_id,
    predicate="responds",
    value=False,
    confidence=0.85
)
store.add(p1)
store.add(p2)

# Also add unrelated proposition
file_id = str(uuid4())
p3 = Proposition(
    id=uuid4(),
    subject_type="file",
    subject_id=file_id,
    predicate="exists",
    value=True,
    confidence=0.95
)
store.add(p3)

print(f"\nWorld State:")
print(f"  api:{api_id}: responds=True (0.9)")
print(f"  api:{api_id}: responds=False (0.85)  <- CONFLICT")
print(f"  file:{file_id}: exists=True (0.95)")

# Detect conflicts
detector = get_conflict_detector()
all_props = store.get_all()
report = detector.detect(all_props)

print(f"\nConflict Detection:")
print(f"  Total conflicts: {len(report.conflicts)}")
print(f"  Global penalty (v1.0): {report.global_penalty:.3f}")

# Test patterns
print(f"\n" + "=" * 70)
print("PATTERN INTERSECTION TEST")
print("=" * 70)

# Pattern 1: INTERSECTS with conflict
pattern_api = GoalPattern(
    subject_type="api",
    predicate="responds",
    expected_value=None,  # Any value
    match_mode=MatchMode.ANY
)

# Pattern 2: DOES NOT intersect with conflict
pattern_file = GoalPattern(
    subject_type="file",
    predicate="exists",
    expected_value=True,
    match_mode=MatchMode.ANY
)

# Pattern 3: Same type but different predicate
pattern_api_health = GoalPattern(
    subject_type="api",
    predicate="healthy",  # Different predicate
    expected_value=True,
    match_mode=MatchMode.ANY
)

print(f"\nPattern 1 (api, responds):")
intersecting = report.conflicts_for_patterns([pattern_api])
print(f"  Intersecting conflicts: {len(intersecting)}")
localized_penalty = report.localized_penalty_for_patterns([pattern_api])
print(f"  Localized penalty: {localized_penalty:.3f}")

print(f"\nPattern 2 (file, exists):")
intersecting = report.conflicts_for_patterns([pattern_file])
print(f"  Intersecting conflicts: {len(intersecting)}")
localized_penalty = report.localized_penalty_for_patterns([pattern_file])
print(f"  Localized penalty: {localized_penalty:.3f}")

print(f"\nPattern 3 (api, healthy) - same type, different predicate:")
intersecting = report.conflicts_for_patterns([pattern_api_health])
print(f"  Intersecting conflicts: {len(intersecting)}")
localized_penalty = report.localized_penalty_for_patterns([pattern_api_health])
print(f"  Localized penalty: {localized_penalty:.3f}")

# Test penalty application
print(f"\n" + "=" * 70)
print("PENALTY APPLICATION TEST")
print("=" * 70)

test_confidence = 0.95
test_uncertainty = 0.05

print(f"\nInitial: confidence={test_confidence:.2f}, uncertainty={test_uncertainty:.2f}")

# Goal A: cares about api responds (INTERSECTS)
adj_conf_a, adj_unc_a = apply_conflict_penalty(
    test_confidence, test_uncertainty, report, patterns=[pattern_api]
)
print(f"\nGoal A (api, responds) - INTERSECTS:")
print(f"  Confidence: {test_confidence:.2f} -> {adj_conf_a:.3f}")
print(f"  Uncertainty: {test_uncertainty:.2f} -> {adj_unc_a:.3f}")
print(f"  Penalty applied: {(test_confidence - adj_conf_a):.3f}")

# Goal B: cares about file exists (DOES NOT INTERSECT)
adj_conf_b, adj_unc_b = apply_conflict_penalty(
    test_confidence, test_uncertainty, report, patterns=[pattern_file]
)
print(f"\nGoal B (file, exists) - NO INTERSECTION:")
print(f"  Confidence: {test_confidence:.2f} -> {adj_conf_b:.3f}")
print(f"  Uncertainty: {test_uncertainty:.2f} -> {adj_unc_b:.3f}")
print(f"  Penalty applied: {(test_confidence - adj_conf_b):.3f}")

# Goal C: no patterns (LEGACY global penalty)
adj_conf_c, adj_unc_c = apply_conflict_penalty(
    test_confidence, test_uncertainty, report, patterns=None
)
print(f"\nGoal C (no patterns) - GLOBAL FALLBACK:")
print(f"  Confidence: {test_confidence:.2f} -> {adj_conf_c:.3f}")
print(f"  Uncertainty: {test_uncertainty:.2f} -> {adj_unc_c:.3f}")
print(f"  Penalty applied: {(test_confidence - adj_conf_c):.3f}")

# Verification
print(f"\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

passed = True

# Goal A should be penalized
if adj_conf_a >= test_confidence:
    print("FAIL: Goal A not penalized (should be)")
    passed = False
else:
    print("PASS: Goal A penalized correctly")

# Goal B should NOT be penalized
if adj_conf_b < test_confidence:
    print("FAIL: Goal B penalized (should NOT be)")
    passed = False
else:
    print("PASS: Goal B not penalized (no intersection)")

# Goal C should have global penalty
if adj_conf_c >= test_confidence:
    print("FAIL: Goal C not penalized (global fallback)")
    passed = False
else:
    print("PASS: Goal C has global penalty (legacy)")

# Goal B should have same confidence as original
if abs(adj_conf_b - test_confidence) > 0.001:
    print(f"FAIL: Goal B confidence changed: {test_confidence} -> {adj_conf_b}")
    passed = False
else:
    print("PASS: Goal B confidence unchanged")

print()
if passed:
    print("=" * 70)
    print("ALL TESTS PASSED")
    print("=" * 70)
else:
    print("=" * 70)
    print("SOME TESTS FAILED")
    print("=" * 70)
