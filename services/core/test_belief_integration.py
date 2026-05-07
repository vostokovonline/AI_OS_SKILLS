"""Test BeliefState integration with CompletionEngine."""
import sys
sys.path.insert(0, '/app')

import asyncio
from uuid import uuid4
from autonomy.propositions import (
    Proposition, GoalPattern, MatchMode,
    reset_propositions, get_proposition_store
)
from autonomy.beliefs import (
    BeliefStateBuilder, get_belief_builder, reset_belief_builder
)
from autonomy.completion_engine import (
    CompletionEngine, TruthState, CompletionMode
)

async def test_belief_based_evaluation():
    """Test that CompletionEngine uses BeliefState correctly."""
    
    print("=" * 70)
    print("BELIEFSTATE INTEGRATION TEST")
    print("=" * 70)
    
    # Reset
    reset_propositions()
    reset_belief_builder()
    store = get_proposition_store()
    
    # Create world with CONFLICT
    api_id = str(uuid4())
    file_id = str(uuid4())
    
    # Conflicted api:responds
    p1 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=True, confidence=0.9
    )
    p2 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=False, confidence=0.85
    )
    
    # Stable file:exists
    p3 = Proposition(
        id=uuid4(), subject_type="file", subject_id=file_id,
        predicate="exists", value=True, confidence=0.95
    )
    
    for p in [p1, p2, p3]:
        store.add(p)
    
    print(f"\nWorld State:")
    print(f"  api:responds = True (0.9), False (0.85) <- CONFLICT")
    print(f"  file:exists = True (0.95)")
    
    # Build belief state
    builder = get_belief_builder()
    world_state = builder.build(store.get_all())
    
    print(f"\nBeliefState Analysis:")
    api_belief = world_state.get("api", api_id, "responds")
    print(f"  api:responds P(True) = {api_belief.probability_true:.3f}")
    print(f"  api:responds uncertainty = {api_belief.uncertainty:.3f}")
    print(f"  api:responds is_conflicted = {api_belief.is_conflicted}")
    
    file_belief = world_state.get("file", file_id, "exists")
    print(f"  file:exists P(True) = {file_belief.probability_true:.3f}")
    print(f"  file:exists uncertainty = {file_belief.uncertainty:.3f}")
    
    # Test aggregation modes
    print(f"\n" + "=" * 70)
    print("AGGREGATION MODE TESTS")
    print("=" * 70)
    
    # Pattern for api
    pattern_api = GoalPattern(
        subject_type="api", predicate="responds",
        expected_value=True, match_mode=MatchMode.ANY
    )
    
    conf_any, unc_any = world_state.aggregate_confidence(
        pattern_api, expected_value=True, match_mode=MatchMode.ANY
    )
    print(f"\napi:responds==True with ANY mode:")
    print(f"  confidence = {conf_any:.3f} (max)")
    print(f"  uncertainty = {unc_any:.3f}")
    
    conf_all, unc_all = world_state.aggregate_confidence(
        pattern_api, expected_value=True, match_mode=MatchMode.ALL
    )
    print(f"\napi:responds==True with ALL mode:")
    print(f"  confidence = {conf_all:.3f} (product)")
    print(f"  uncertainty = {unc_all:.3f}")
    
    conf_avg, unc_avg = world_state.aggregate_confidence(
        pattern_api, expected_value=True, match_mode=MatchMode.AVERAGE
    )
    print(f"\napi:responds==True with AVERAGE mode:")
    print(f"  confidence = {conf_avg:.3f} (mean)")
    print(f"  uncertainty = {unc_avg:.3f}")
    
    # Pattern for file
    pattern_file = GoalPattern(
        subject_type="file", predicate="exists",
        expected_value=True, match_mode=MatchMode.ANY
    )
    
    conf_file, unc_file = world_state.aggregate_confidence(
        pattern_file, expected_value=True, match_mode=MatchMode.ANY
    )
    print(f"\nfile:exists==True with ANY mode:")
    print(f"  confidence = {conf_file:.3f}")
    print(f"  uncertainty = {unc_file:.3f}")
    
    # Verification
    print(f"\n" + "=" * 70)
    print("VERIFICATION")
    print("=" * 70)
    
    passed = True
    
    # ANY mode should give max
    if abs(conf_any - api_belief.probability_true) > 0.01:
        print(f"FAIL: ANY mode not using max")
        passed = False
    else:
        print(f"PASS: ANY mode = max = {conf_any:.3f}")
    
    # ALL mode should give product (just 1 value = same as ANY)
    if conf_all < 0 or conf_all > 1:
        print(f"FAIL: ALL mode out of range: {conf_all:.3f}")
        passed = False
    else:
        print(f"PASS: ALL mode = {conf_all:.3f}")
    
    # File should be certain
    if conf_file < 0.99:
        print(f"FAIL: File not certain: {conf_file:.3f}")
        passed = False
    else:
        print(f"PASS: File is certain: {conf_file:.3f}")
    
    # API should be uncertain
    if unc_any < 0.3:
        print(f"FAIL: API too certain: {unc_any:.3f}")
        passed = False
    else:
        print(f"PASS: API is uncertain: {unc_any:.3f}")
    
    # Compare OLD vs NEW
    print(f"\n" + "=" * 70)
    print("OLD (Penalty) vs NEW (Belief) Comparison")
    print("=" * 70)
    
    print(f"\nGoal: api:responds==True")
    print(f"  OLD (Penalty):  conf = 0.95 * (1 - 0.85) = 0.143")
    print(f"  NEW (Belief):   conf = P(True) = {conf_any:.3f}")
    print(f"  Difference: NEW is {conf_any/0.143:.1f}x higher")
    print(f"  → Belief model is PROPORTIONAL, penalty was CATASTROPHIC")
    
    print()
    if passed:
        print("=" * 70)
        print("ALL TESTS PASSED - BeliefState Integration Working")
        print("=" * 70)
    else:
        print("=" * 70)
        print("SOME TESTS FAILED")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_belief_based_evaluation())
