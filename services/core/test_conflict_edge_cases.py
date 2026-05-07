"""
Conflict Model Edge Cases - Pre-E2E Validation
===============================================

Experiment 1: Goal with 2 patterns (one intersects, one doesn't)
Experiment 2: Goal with 3 intersecting conflicts of different strength
"""
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

def experiment_1():
    """
    Experiment 1: Goal with 2 patterns
    - Pattern A: intersects with conflict
    - Pattern B: does NOT intersect
    
    Question: Does the goal suffer penalty?
    
    Expected: Only pattern A's conflict counts
    """
    print("=" * 70)
    print("EXPERIMENT 1: Multi-pattern Goal")
    print("=" * 70)
    
    reset_propositions()
    reset_conflict_detector()
    store = get_proposition_store()
    
    # World: ONE conflict on api
    api_id = str(uuid4())
    p1 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=True, confidence=0.9
    )
    p2 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=False, confidence=0.85
    )
    store.add(p1)
    store.add(p2)
    
    # Also: stable file
    file_id = str(uuid4())
    p3 = Proposition(
        id=uuid4(), subject_type="file", subject_id=file_id,
        predicate="exists", value=True, confidence=0.95
    )
    store.add(p3)
    
    print(f"\nWorld: 1 conflict (api:responds), 1 stable (file:exists)")
    
    detector = get_conflict_detector()
    report = detector.detect(store.get_all())
    
    print(f"Global penalty: {report.global_penalty:.3f}")
    
    # Goal with BOTH patterns
    pattern_api = GoalPattern(
        subject_type="api", predicate="responds",
        expected_value=None, match_mode=MatchMode.ANY
    )
    pattern_file = GoalPattern(
        subject_type="file", predicate="exists",
        expected_value=True, match_mode=MatchMode.ANY
    )
    
    patterns = [pattern_api, pattern_file]
    
    # Get intersecting conflicts
    intersecting = report.conflicts_for_patterns(patterns)
    localized_penalty = report.localized_penalty_for_patterns(patterns)
    
    print(f"\nGoal has 2 patterns:")
    print(f"  Pattern A: (api, responds) - INTERSECTS")
    print(f"  Pattern B: (file, exists) - NO INTERSECTION")
    print(f"\nIntersecting conflicts: {len(intersecting)}")
    print(f"Localized penalty: {localized_penalty:.3f}")
    
    # Test penalty
    conf, unc = 0.95, 0.05
    adj_conf, adj_unc = apply_conflict_penalty(conf, unc, report, patterns=patterns)
    
    print(f"\nPenalty application:")
    print(f"  Before: conf={conf:.2f}, unc={unc:.2f}")
    print(f"  After:  conf={adj_conf:.3f}, unc={adj_unc:.3f}")
    print(f"  Penalty: {conf - adj_conf:.3f}")
    
    # ANALYSIS
    print(f"\nANALYSIS:")
    if adj_conf < conf:
        print(f"  Goal penalized because ONE pattern intersects")
        print(f"  This means: goal is as weak as its weakest (conflicted) pattern")
    else:
        print(f"  Goal NOT penalized - both patterns must intersect?")
    
    return adj_conf < conf


def experiment_2():
    """
    Experiment 2: 3 conflicts of different strength
    
    Conflict A: score 0.8
    Conflict B: score 0.5
    Conflict C: score 0.3
    
    Question: Does max(conflict_score) dominate?
    
    Expected: penalty = max(0.8, 0.5, 0.3) = 0.8
    Alternative: penalty = weighted average?
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Multiple Conflicts, Different Strengths")
    print("=" * 70)
    
    reset_propositions()
    reset_conflict_detector()
    store = get_proposition_store()
    
    # Create 3 CONFLICTS on same predicate type, different subjects
    conflicts_data = [
        ("api_1", 0.8),   # Strong conflict
        ("api_2", 0.5),   # Medium conflict
        ("api_3", 0.3),   # Weak conflict
    ]
    
    for sid, base_conf in conflicts_data:
        p_true = Proposition(
            id=uuid4(), subject_type="api", subject_id=sid,
            predicate="responds", value=True, confidence=base_conf + 0.05
        )
        p_false = Proposition(
            id=uuid4(), subject_type="api", subject_id=sid,
            predicate="responds", value=False, confidence=base_conf
        )
        store.add(p_true)
        store.add(p_false)
    
    print(f"\nWorld: 3 conflicts")
    print(f"  api_1: True(0.85) vs False(0.80) -> score=0.80")
    print(f"  api_2: True(0.55) vs False(0.50) -> score=0.50")
    print(f"  api_3: True(0.35) vs False(0.30) -> score=0.30")
    
    detector = get_conflict_detector()
    report = detector.detect(store.get_all())
    
    print(f"\nDetected conflicts: {len(report.conflicts)}")
    for c in report.conflicts:
        print(f"  {c.subject_id}: score={c.conflict_score:.2f}")
    
    # Pattern matches ALL apis (wildcard)
    pattern_all = GoalPattern(
        subject_type="api", predicate="responds",
        expected_value=None, match_mode=MatchMode.ANY,
        subject_id_pattern="*"  # Match all
    )
    
    localized_penalty = report.localized_penalty_for_patterns([pattern_all])
    
    print(f"\nPattern: (api, responds, *)")
    print(f"Intersecting conflicts: {len(report.conflicts_for_patterns([pattern_all]))}")
    print(f"Localized penalty (max): {localized_penalty:.3f}")
    
    # Test penalty
    conf, unc = 0.95, 0.05
    adj_conf, adj_unc = apply_conflict_penalty(conf, unc, report, patterns=[pattern_all])
    
    print(f"\nPenalty application:")
    print(f"  Before: conf={conf:.2f}")
    print(f"  After:  conf={adj_conf:.3f}")
    print(f"  Reduction: {(conf - adj_conf):.3f} ({(conf - adj_conf)/conf*100:.1f}%)")
    
    # ANALYSIS
    print(f"\nANALYSIS:")
    print(f"  Current model: penalty = max(0.8, 0.5, 0.3) = 0.8")
    print(f"  Alternative: penalty = avg(0.8, 0.5, 0.3) = 0.53")
    print(f"  Alternative: penalty = weighted = ?")
    
    if abs(adj_conf - conf * (1 - 0.8)) < 0.01:
        print(f"\n  VERDICT: MAX dominates - one strong conflict = total penalty")
    
    return abs(adj_conf - conf * (1 - 0.8)) < 0.01


def experiment_3_dominance():
    """
    Experiment 3: Dominance Problem
    
    What if goal only partially cares about the conflicted proposition?
    
    Pattern: (api, *) - matches ALL predicates
    Conflicts: only on "responds" predicate
    
    Does goal suffer for OTHER predicates too?
    """
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Predicate Granularity")
    print("=" * 70)
    
    reset_propositions()
    reset_conflict_detector()
    store = get_proposition_store()
    
    # Conflict on api:responds
    api_id = "service_x"
    p1 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=True, confidence=0.9
    )
    p2 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="responds", value=False, confidence=0.85
    )
    store.add(p1)
    store.add(p2)
    
    # Stable proposition on api:latency
    p3 = Proposition(
        id=uuid4(), subject_type="api", subject_id=api_id,
        predicate="latency", value="50ms", confidence=0.95
    )
    store.add(p3)
    
    print(f"\nWorld:")
    print(f"  api:service_x:responds - CONFLICT (0.9 vs 0.85)")
    print(f"  api:service_x:latency - STABLE (0.95)")
    
    detector = get_conflict_detector()
    report = detector.detect(store.get_all())
    
    # Pattern ONLY matches "responds"
    pattern_responds = GoalPattern(
        subject_type="api", predicate="responds",
        expected_value=None, match_mode=MatchMode.ANY
    )
    
    # Pattern matches ALL predicates (if we had wildcard support)
    # For now, we test the specific case
    
    penalty_responds = report.localized_penalty_for_patterns([pattern_responds])
    
    print(f"\nPattern: (api, responds)")
    print(f"  Localized penalty: {penalty_responds:.3f}")
    
    # If goal had a second pattern for latency
    pattern_latency = GoalPattern(
        subject_type="api", predicate="latency",
        expected_value="50ms", match_mode=MatchMode.ANY
    )
    
    penalty_both = report.localized_penalty_for_patterns([pattern_responds, pattern_latency])
    
    print(f"\nPattern: (api, responds) + (api, latency)")
    print(f"  Localized penalty: {penalty_both:.3f}")
    print(f"  (conflict only affects 'responds', not 'latency')")
    
    print(f"\nANALYSIS:")
    if penalty_both == penalty_responds:
        print(f"  VERDICT: Penalty correctly scoped to intersecting predicate")
    else:
        print(f"  WARNING: Penalty leaked to non-conflicted predicate!")
    
    return penalty_both == penalty_responds


if __name__ == "__main__":
    print("\n" + "#" * 70)
    print("# CONFLICT MODEL EDGE CASES - PRE-E2E VALIDATION")
    print("#" * 70)
    
    r1 = experiment_1()
    r2 = experiment_2()
    r3 = experiment_3_dominance()
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Experiment 1 (multi-pattern):         {'PASS' if r1 else 'NEEDS REVIEW'}")
    print(f"Experiment 2 (multi-conflict):        {'PASS' if r2 else 'NEEDS REVIEW'}")
    print(f"Experiment 3 (predicate granularity): {'PASS' if r3 else 'NEEDS REVIEW'}")
    
    if r1 and r2 and r3:
        print("\nAll edge cases handled correctly. Ready for E2E.")
    else:
        print("\nSome edge cases need attention before E2E.")
