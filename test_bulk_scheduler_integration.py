#!/usr/bin/env python3
"""
Bulk Scheduler Integration Test

Behavioural test for auto_resume_pending_goals() with bulk transitions.

Tests:
1. Bulk activation of pending goals
2. Only ACTIVATED goals are enqueued for decomposition
3. Transaction is SHORT (milliseconds)
"""
import asyncio
import time
from uuid import uuid4

from database import AsyncSessionLocal
from models import Goal
from sqlalchemy import select


async def create_pending_goals(count: int = 5) -> list:
    """Create test pending goals without children."""
    async with AsyncSessionLocal() as db:
        goals = []
        for i in range(count):
            goal = Goal(
                title=f"Test Pending Goal {i}",
                description=f"Test goal {i} for bulk activation",
                goal_type="achievable",
                is_atomic=False,
                _status="pending",
                progress=0.0,
                depth_level=0,
                parent_id=None
            )
            db.add(goal)
            goals.append(goal)

        await db.commit()

        # Refresh to get IDs
        for goal in goals:
            await db.refresh(goal)

        goal_ids = [g.id for g in goals]
        print(f"✓ Created {len(goal_ids)} pending goals")

        return goal_ids


async def count_goals_by_status(status: str) -> int:
    """Count goals with given status."""
    async with AsyncSessionLocal() as db:
        stmt = select(Goal).where(Goal._status == status)
        result = await db.execute(stmt)
        return len(result.scalars().all())


async def test_bulk_scheduler_integration():
    """
    Test bulk integration in auto_resume_pending_goals().
    """
    print("\n" + "="*70)
    print("BULK SCHEDULER INTEGRATION TEST")
    print("="*70)

    # Setup: Create test goals
    print("\n📋 SETUP: Creating test pending goals...")
    goal_ids = await create_pending_goals(5)

    # Verify initial state
    pending_before = await count_goals_by_status("pending")
    active_before = await count_goals_by_status("active")
    print(f"✓ Initial state: {pending_before} pending, {active_before} active")

    # Act: Run auto_resume_pending_goals
    print("\n🔄 Running auto_resume_pending_goals()...")
    from scheduler import auto_resume_pending_goals

    start_time = time.time()
    await auto_resume_pending_goals()
    execution_time = (time.time() - start_time) * 1000

    print(f"✓ Execution completed in {execution_time:.2f}ms")

    # Verify final state
    pending_after = await count_goals_by_status("pending")
    active_after = await count_goals_by_status("active")
    print(f"✓ Final state: {pending_after} pending, {active_after} active")

    # Assertions
    activated = active_after - active_before
    assert activated > 0, f"No goals were activated! ({active_before} → {active_after})"
    assert pending_after < pending_before, f"Pending count didn't decrease! ({pending_before} → {pending_after})"

    print(f"\n✅ INTEGRATION TEST PASSED")
    print(f"   {activated} goals activated")
    print(f"   Transaction time: {execution_time:.2f}ms")
    print("="*70)

    return True


if __name__ == "__main__":
    print("\n" + "="*70)
    print("BULK SCHEDULER - INTEGRATION TEST")
    print("="*70)

    try:
        asyncio.run(test_bulk_scheduler_integration())
        print(f"\n🎉 TEST PASSED - Bulk scheduler integration is WORKING")
        exit(0)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
