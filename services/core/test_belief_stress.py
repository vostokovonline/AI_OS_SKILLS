"""
BELIEF STATE STRESS TESTS
=========================

Tests for robustness under scale and noise.

1. 100+ conflicting propositions
2. Noise robustness (weak signals vs strong signals)
3. Degradation under partial information
4. Confidence stability under accumulation
5. Independence assumption check

Goal: Verify BeliefState model doesn't break under stress.
"""
import sys
sys.path.insert(0, '/app')

from uuid import uuid4
from autonomy.propositions import (
    Proposition, GoalPattern, MatchMode,
    reset_propositions, get_proposition_store
)
from autonomy.beliefs import (
    BeliefStateBuilder, get_belief_builder, reset_belief_builder
)

def test_1_massive_conflict():
    """
    Test 1: 100+ conflicting propositions
    
    Question: Does confidence remain stable under massive conflict?
    """
    print("=" * 70)
    print("TEST 1: MASSIVE CONFLICT (100+ signals)")
    print("=" * 70)
    
    reset_propositions()
    reset_belief_builder()
    store = get_proposition_store()
    
    api_id = "test_api"
    
    # 50 True signals (0.7 each)
    for i in range(50):
        p = Proposition(
            id=uuid4(), subject_type="api", subject_id=api_id,
            predicate="responds", value=True, confidence=0.7
        )
        store.add(p)
    
    # 50 False signals (0.6 each)
    for i in range(50):
        p = Proposition(
            id=uuid4(), subject_type="api", subject_id=api_id,
            predicate="responds", value=False, confidence=0.6
        )
        store.add(p)
    
    print(f"\nAdded 100 propositions:")
    print(f"  True:  50 × 0.7 = {50 * 0.7:.1f} support")
    print(f"  False: 50 × 0.6 = {50 * 0.6:.1f} support")
    
    builder = get_belief_builder()
    world_state = builder.build(store.get_all())
    
    belief = world_state.get("api", api_id, "responds")
    
    expected_true = 35.0 / (35.0 + 30.0)
    
    print(f"\nResults:")
    print(f"  P(True):  {belief.probability_true:.3f} (expected: {expected_true:.3f})")
    print(f"  P(False): {belief.probability_false:.3f}")
    print(f"  Uncertainty: {belief.uncertainty:.3f}")
    print(f"  is_conflicted: {belief.is_conflicted}")
    
    passed = abs(belief.probability_true - expected_true) < 0.01
    print(f"\n{'PASS' if passed else 'FAIL'}: P(True) ≈ {expected_true:.3f}")
    
    return passed


def test_2_noise_robustness():
    """
    Test 2: Noise robustness
    
    1 strong True (0.95) vs 20 weak False (0.1 each)
    
    Question: Does weak noise overwhelm strong signal?
    """
    print("\n" + "=" * 70)
    print("TEST 2: NOISE ROBUSTNESS (1 strong vs 20 weak)")
    print("=" * 70)
    
    reset_propositions()
    reset_belief_builder()
    store = get_proposition_store()
    
    api_id = "test_api"
    
    # 1 strong True
    p = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=True, confidence=0.95
    )
    store.add(p)
    
    # 20 weak False (noise)
    for i in range(20):
        p = Proposition(
            id=uuid4(), subject_type="api", subject_id=api_id,
            predicate="responds", value=False, confidence=0.1
        )
        store.add(p)
    
    print(f"\nAdded 21 propositions:")
    print(f"  True:  1 × 0.95 = 0.95 support")
    print(f"  False: 20 × 0.1 = 2.0 support")
    
    builder = get_belief_builder()
    world_state = builder.build(store.get_all())
    
    belief = world_state.get("api", api_id, "responds")
    
    # With noise threshold 0.1, weak signals should be filtered
    # Builder has min_support_threshold=0.1 by default
    
    print(f"\nResults:")
    print(f"  P(True):  {belief.probability_true:.3f}")
    print(f"  P(False): {belief.probability_false:.3f}")
    print(f"  Evidence count: {belief.total_evidence}")
    
    # CRITICAL: Weak noise (0.1) should be filtered
    # If not filtered, P(True) = 0.95 / 2.95 = 0.32 (BAD)
    # If filtered, P(True) = 0.95 / 0.95 = 1.0 (GOOD)
    
    passed = belief.probability_true > 0.8
    print(f"\n{'PASS' if passed else 'FAIL'}: Strong signal dominates (P(True) > 0.8)")
    
    if not passed:
        print("  WARNING: Noise overwhelms signal!")
        print("  → Consider increasing min_support_threshold")
    
    return passed


def test_3_partial_information():
    """
    Test 3: Degradation under partial information
    
    Progressive removal of evidence.
    
    Question: Does confidence degrade gracefully?
    """
    print("\n" + "=" * 70)
    print("TEST 3: PARTIAL INFORMATION DEGRADATION")
    print("=" * 70)
    
    results = []
    
    for evidence_count in [10, 5, 2, 1, 0]:
        reset_propositions()
        reset_belief_builder()
        store = get_proposition_store()
        
        api_id = "test_api"
        
        for i in range(evidence_count):
            p = Proposition(
                id=uuid4(), subject_type="api", subject_id=api_id,
                predicate="responds", value=True, confidence=0.8
            )
            store.add(p)
        
        builder = get_belief_builder()
        world_state = builder.build(store.get_all())
        
        belief = world_state.get("api", api_id, "responds")
        
        if belief:
            results.append((evidence_count, belief.confidence, belief.uncertainty))
        else:
            results.append((evidence_count, 0.0, 1.0))
    
    print(f"\nEvidence degradation:")
    print(f"  Evidence │ Confidence │ Uncertainty")
    print(f"  ─────────┼────────────┼────────────")
    for count, conf, unc in results:
        print(f"    {count:3d}    │   {conf:.3f}    │   {unc:.3f}")
    
    # Check: uncertainty should increase as evidence decreases
    uncertainties = [r[2] for r in results]
    is_monotonic = all(uncertainties[i] <= uncertainties[i+1] for i in range(len(uncertainties)-1))
    
    print(f"\n{'PASS' if is_monotonic else 'FAIL'}: Uncertainty increases with less evidence")
    
    return is_monotonic


def test_4_accumulation_stability():
    """
    Test 4: Confidence stability under accumulation
    
    Add more and more evidence for the SAME value.
    
    Question: Does confidence converge, not explode?
    """
    print("\n" + "=" * 70)
    print("TEST 4: ACCUMULATION STABILITY")
    print("=" * 70)
    
    results = []
    
    for count in [1, 5, 10, 20, 50, 100]:
        reset_propositions()
        reset_belief_builder()
        store = get_proposition_store()
        
        api_id = "test_api"
        
        for i in range(count):
            p = Proposition(
                id=uuid4(), subject_type="api", subject_id=api_id,
                predicate="responds", value=True, confidence=0.8
            )
            store.add(p)
        
        builder = get_belief_builder()
        world_state = builder.build(store.get_all())
        
        belief = world_state.get("api", api_id, "responds")
        results.append((count, belief.confidence, belief.uncertainty))
    
    print(f"\nAccumulation results:")
    print(f"  Count │ Confidence │ Uncertainty")
    print(f"  ──────┼────────────┼────────────")
    for count, conf, unc in results:
        print(f"   {count:3d}  │   {conf:.3f}    │   {unc:.3f}")
    
    # Check: confidence should converge to 1.0 (all same value)
    final_conf = results[-1][1]
    converged = final_conf > 0.99
    
    print(f"\n{'PASS' if converged else 'FAIL'}: Confidence converges to 1.0 with consistent evidence")
    
    return converged


def test_5_independence_check():
    """
    Test 5: Independence assumption
    
    Multiple independent predicates should not interfere.
    
    Question: Does BeliefState for (api, responds) affect (api, latency)?
    """
    print("\n" + "=" * 70)
    print("TEST 5: INDEPENDENCE CHECK")
    print("=" * 70)
    
    reset_propositions()
    reset_belief_builder()
    store = get_proposition_store()
    
    api_id = "test_api"
    
    # Conflicted responds
    p1 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=True, confidence=0.9
    )
    p2 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=False, confidence=0.85
    )
    
    # Stable latency
    p3 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="latency", value="50ms", confidence=0.95
    )
    
    store.add(p1)
    store.add(p2)
    store.add(p3)
    
    builder = get_belief_builder()
    world_state = builder.build(store.get_all())
    
    responds_belief = world_state.get("api", api_id, "responds")
    latency_belief = world_state.get("api", api_id, "latency")
    
    print(f"\nBelief states:")
    print(f"  responds: P(True)={responds_belief.probability_true:.3f}, unc={responds_belief.uncertainty:.3f}")
    print(f"  latency:  P(50ms)={latency_belief.probability('50ms'):.3f}, unc={latency_belief.uncertainty:.3f}")
    
    # Latency should be certain (0.0 uncertainty)
    # Responds should be uncertain (conflicted)
    independent = latency_belief.uncertainty < 0.01
    
    print(f"\n{'PASS' if independent else 'FAIL'}: Predicates are independent")
    
    return independent


if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# BELIEF STATE STRESS TESTS")
    print("#" * 70)
    
    results = []
    
    results.append(("Massive Conflict", test_1_massive_conflict()))
    results.append(("Noise Robustness", test_2_noise_robustness()))
    results.append(("Partial Information", test_3_partial_information()))
    results.append(("Accumulation Stability", test_4_accumulation_stability()))
    results.append(("Independence Check", test_5_independence_check()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:25s}: {status}")
    
    total_passed = sum(1 for _, p in results if p)
    print(f"\nPassed: {total_passed}/{len(results)}")
    
    if total_passed == len(results):
        print("\n✅ ALL STRESS TESTS PASSED - BeliefState is STABLE")
    else:
        print("\n⚠️  SOME TESTS FAILED - Review model")
