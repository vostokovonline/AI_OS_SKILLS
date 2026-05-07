"""Test BeliefState layer - epistemic foundation."""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4
from autonomy.propositions import (
    Proposition, GoalPattern, MatchMode,
    reset_propositions, get_proposition_store
)
from autonomy.beliefs import (
    BeliefState, BeliefStateBuilder, WorldBeliefState,
    get_belief_builder, reset_belief_builder
)

print("=" * 70)
print("BELIEF STATE LAYER TEST")
print("=" * 70)

# Reset
reset_propositions()
reset_belief_builder()
store = get_proposition_store()

# Create world state with CONFLICT
api_id = str(uuid4())

# Propositions for api:responds
p1 = Proposition(
    id=uuid4(), subject_type="api", subject_id=api_id,
    predicate="responds", value=True, confidence=0.9
)
p2 = Proposition(
    id=uuid4(), subject_type="api", subject_id=api_id,
    predicate="responds", value=False, confidence=0.85
)
p3 = Proposition(
    id=uuid4(), subject_type="api", subject_id=api_id,
    predicate="responds", value=True, confidence=0.7
)

# Stable proposition
file_id = str(uuid4())
p4 = Proposition(
    id=uuid4(), subject_type="file", subject_id=file_id,
    predicate="exists", value=True, confidence=0.95
)

for p in [p1, p2, p3, p4]:
    store.add(p)

print(f"\nWorld State:")
print(f"  api:{api_id}:responds = True (0.9)")
print(f"  api:{api_id}:responds = True (0.7)")
print(f"  api:{api_id}:responds = False (0.85)")
print(f"  file:{file_id}:exists = True (0.95)")

# Build belief states
builder = get_belief_builder()
world_state = builder.build(store.get_all())

print(f"\n" + "=" * 70)
print("BELIEF STATE ANALYSIS")
print("=" * 70)

print(f"\nTotal belief states: {world_state.count}")
print(f"Conflicted keys: {len(world_state.conflicted_keys)}")

# Analyze api:responds
api_belief = world_state.get("api", api_id, "responds")
if api_belief:
    print(f"\n--- api:responds ---")
    print(f"  support_true:  {api_belief.support_true:.2f} (0.9 + 0.7)")
    print(f"  support_false: {api_belief.support_false:.2f}")
    print(f"  total_support: {api_belief.total_support:.2f}")
    print(f"  total_evidence: {api_belief.total_evidence}")
    print(f"\n  PROBABILITIES:")
    print(f"    P(True):  {api_belief.probability_true:.3f}")
    print(f"    P(False): {api_belief.probability_false:.3f}")
    print(f"\n  EPISTEMICS:")
    print(f"    is_conflicted: {api_belief.is_conflicted}")
    print(f"    conflict_intensity: {api_belief.conflict_intensity:.3f}")
    print(f"    uncertainty: {api_belief.uncertainty:.3f}")
    print(f"    confidence: {api_belief.confidence:.3f}")
    print(f"    dominant_value: {api_belief.dominant_value}")

# Analyze file:exists
file_belief = world_state.get("file", file_id, "exists")
if file_belief:
    print(f"\n--- file:exists ---")
    print(f"  support_true:  {file_belief.support_true:.2f}")
    print(f"  total_evidence: {file_belief.total_evidence}")
    print(f"  P(True): {file_belief.probability_true:.3f}")
    print(f"  uncertainty: {file_belief.uncertainty:.3f}")
    print(f"  confidence: {file_belief.confidence:.3f}")
    print(f"  is_conflicted: {file_belief.is_conflicted}")

print(f"\n" + "=" * 70)
print("PATTERN EVALUATION (Goal perspective)")
print("=" * 70)

# Goal A: cares about api:responds = True
pattern_api = GoalPattern(
    subject_type="api", predicate="responds",
    expected_value=True, match_mode=MatchMode.ANY
)

conf_a, unc_a = world_state.aggregate_confidence(pattern_api, expected_value=True)
print(f"\nGoal A: api:responds == True")
print(f"  confidence: {conf_a:.3f}")
print(f"  uncertainty: {unc_a:.3f}")
print(f"  VERDICT: {'UNCERTAIN (conflict)' if unc_a > 0.3 else 'CERTAIN'}")

# Goal B: cares about file:exists = True
pattern_file = GoalPattern(
    subject_type="file", predicate="exists",
    expected_value=True, match_mode=MatchMode.ANY
)

conf_b, unc_b = world_state.aggregate_confidence(pattern_file, expected_value=True)
print(f"\nGoal B: file:exists == True")
print(f"  confidence: {conf_b:.3f}")
print(f"  uncertainty: {unc_b:.3f}")
print(f"  VERDICT: {'UNCERTAIN (conflict)' if unc_b > 0.3 else 'CERTAIN'}")

print(f"\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

passed = True

# Test 1: api should be conflicted
if not api_belief.is_conflicted:
    print("FAIL: api should be conflicted")
    passed = False
else:
    print("PASS: api correctly marked as conflicted")

# Test 2: file should NOT be conflicted
if file_belief.is_conflicted:
    print("FAIL: file should NOT be conflicted")
    passed = False
else:
    print("PASS: file correctly NOT conflicted")

# Test 3: api uncertainty should be > 0.3
if api_belief.uncertainty < 0.3:
    print(f"FAIL: api uncertainty too low: {api_belief.uncertainty:.3f}")
    passed = False
else:
    print(f"PASS: api uncertainty correct: {api_belief.uncertainty:.3f}")

# Test 4: file uncertainty should be < 0.1
if file_belief.uncertainty > 0.1:
    print(f"FAIL: file uncertainty too high: {file_belief.uncertainty:.3f}")
    passed = False
else:
    print(f"PASS: file uncertainty correct: {file_belief.uncertainty:.3f}")

# Test 5: Goal A should see uncertainty
if unc_a < 0.3:
    print(f"FAIL: Goal A uncertainty too low: {unc_a:.3f}")
    passed = False
else:
    print(f"PASS: Goal A sees conflict uncertainty: {unc_a:.3f}")

# Test 6: Goal B should NOT see uncertainty
if unc_b > 0.1:
    print(f"FAIL: Goal B uncertainty too high: {unc_b:.3f}")
    passed = False
else:
    print(f"PASS: Goal B is certain: {unc_b:.3f}")

print()
if passed:
    print("=" * 70)
    print("ALL TESTS PASSED - Belief State Layer Working")
    print("=" * 70)
else:
    print("=" * 70)
    print("SOME TESTS FAILED")
    print("=" * 70)
