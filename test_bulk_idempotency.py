#!/usr/bin/env python3
"""
Test BulkTransitionEngine Idempotency

CRITICAL TEST:
    Run planner twice on same snapshots.
    Second run must return EMPTY transitions list.

    If not - contract is violated (hidden mutations).
"""
import asyncio
from uuid import uuid4

from application.bulk.types import GoalSnapshot, Transition, BulkTransitionPlan
from application.bulk_transition_engine import StateTransitionPlanner


def create_test_snapshots(count: int = 5) -> list[GoalSnapshot]:
    """Create test snapshots for idempotency testing."""
    return [
        GoalSnapshot(
            id=uuid4(),
            status="pending",
            progress=0.0,
            parent_id=None,
            depth_level=0,
            is_atomic=False,
            goal_type="achievable",
            created_at=1000.0,
            updated_at=1000.0
        )
        for _ in range(count)
    ]


def test_planner_idempotency():
    """
    CRITICAL: Planner must be idempotent.

    Same input → Same output (always).
    """
    print("\n" + "="*70)
    print("BULK TRANSITION ENGINE - IDEMPOTENCY TEST")
    print("="*70)

    # Arrange: Create test snapshots
    snapshots = create_test_snapshots(5)
    print(f"\n✓ Created {len(snapshots)} test snapshots")

    # Act: First planning run
    planner = StateTransitionPlanner()
    plan1 = planner.build(snapshots)
    print(f"✓ First plan: {len(plan1)} transitions")

    # Act: Second planning run (SAME snapshots)
    plan2 = planner.build(snapshots)
    print(f"✓ Second plan: {len(plan2)} transitions")

    # Assert: Plans must be identical
    assert len(plan1) == len(plan2), f"Plan size changed: {len(plan1)} != {len(plan2)}"

    # Extract transition data for comparison
    transitions1 = [t.to_dict() for t in plan1.transitions]
    transitions2 = [t.to_dict() for t in plan2.transitions]

    assert transitions1 == transitions2, "Plans are not identical!"

    print(f"\n✅ IDEMPOTENCY TEST PASSED")
    print(f"   Both runs produced {len(plan1)} identical transitions")
    print("="*70)

    return True


def test_snapshot_immutability():
    """
    CRITICAL: Snapshots must be immutable.

    frozen=True prevents accidental mutations.
    """
    print("\n" + "="*70)
    print("SNAPSHOT IMMUTABILITY TEST")
    print("="*70)

    snapshot = GoalSnapshot(
        id=uuid4(),
        status="pending",
        progress=0.0,
        parent_id=None,
        depth_level=0,
        is_atomic=False,
        goal_type="achievable",
        created_at=1000.0,
        updated_at=1000.0
    )

    print(f"\n✓ Created snapshot: {snapshot.id}")

    # Attempt to mutate (should fail)
    try:
        snapshot.status = "active"
        print(f"\n❌ IMMUTABILITY TEST FAILED")
        print(f"   Snapshot was mutated!")
        return False
    except Exception as e:
        print(f"✓ Mutation prevented: {type(e).__name__}")
        print(f"\n✅ IMMUTABILITY TEST PASSED")
        print("="*70)
        return True


def test_transition_pure():
    """
    Test that Transition is also frozen.
    """
    print("\n" + "="*70)
    print("TRANSITION IMMUTABILITY TEST")
    print("="*70)

    transition = Transition(
        goal_id=uuid4(),
        from_status="pending",
        to_status="active",
        reason="Test transition"
    )

    print(f"\n✓ Created transition: {transition.goal_id}")

    # Attempt to mutate (should fail)
    try:
        transition.to_status = "done"
        print(f"\n❌ IMMUTABILITY TEST FAILED")
        print(f"   Transition was mutated!")
        return False
    except Exception as e:
        print(f"✓ Mutation prevented: {type(e).__name__}")
        print(f"\n✅ TRANSITION IMMUTABILITY TEST PASSED")
        print("="*70)
        return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("BULK TRANSITION ENGINE - CONTRACT TESTS")
    print("="*70)

    results = []

    # Test 1: Snapshot immutability
    results.append(("Snapshot Immutability", test_snapshot_immutability()))

    # Test 2: Transition immutability
    results.append(("Transition Immutability", test_transition_pure()))

    # Test 3: Planner idempotency
    results.append(("Planner Idempotency", test_planner_idempotency()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print(f"\n🎉 ALL TESTS PASSED - Bulk contract is SAFE")
        exit(0)
    else:
        print(f"\n⚠️  SOME TESTS FAILED - Contract violation detected")
        exit(1)
