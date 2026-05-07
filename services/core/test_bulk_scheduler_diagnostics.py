#!/usr/bin/env python3
"""
Bulk Scheduler Diagnostics Test

Debug where bulk activation fails.
"""
import asyncio
from uuid import uuid4

from database import AsyncSessionLocal
from models import Goal
from sqlalchemy import select, func


async def diagnose_pending_goals():
    """Diagnose why pending goals are not being activated."""
    print("\n" + "="*70)
    print("BULK SCHEDULER DIAGNOSTICS")
    print("="*70)

    async with AsyncSessionLocal() as db:
        # Check 1: Count ALL pending goals
        stmt_all_pending = select(Goal).where(Goal._status == 'pending')
        result = await db.execute(stmt_all_pending)
        all_pending = result.scalars().all()
        print(f"\n✓ Total pending goals in DB: {len(all_pending)}")

        # Check 2: Count pending goals without children (auto_resume criteria)
        subquery = select(func.count(Goal.id)).where(Goal.parent_id == Goal.id)
        stmt_candidates = select(Goal).where(
            Goal.is_atomic == False
        ).where(
            Goal._status == 'pending'
        ).where(
            subquery == 0
        )

        result = await db.execute(stmt_candidates)
        candidates = result.scalars().all()
        print(f"✓ Pending goals without children: {len(candidates)}")

        # Check 3: Show first 5 candidates
        print(f"\n📋 First 5 candidates:")
        for i, goal in enumerate(candidates[:5]):
            print(f"   {i+1}. {str(goal.id)[:8]} | {goal.title[:40]} | atomic={goal.is_atomic}")

        # Check 4: Test bulk load_snapshots
        if candidates:
            from infrastructure.uow import get_uow
            from application.bulk_transition_engine import bulk_transition_engine

            goal_ids = [g.id for g in candidates[:5]]

            print(f"\n🔄 Testing bulk.load_snapshots()...")
            async with get_uow() as uow:
                snapshots = bulk_transition_engine.load_snapshots(uow.session, goal_ids)
                print(f"✓ Loaded {len(snapshots)} snapshots")

                for i, snap in enumerate(snapshots):
                    print(f"   {i+1}. {str(snap.id)[:8]} | status={snap.status}")

            # Check 5: Test plan_from_snapshots
            print(f"\n🔄 Testing bulk.plan_from_snapshots()...")
            plan = bulk_transition_engine.plan_from_snapshots(snapshots)
            print(f"✓ Plan created: {len(plan)} transitions")

            for i, trans in enumerate(plan.transitions):
                print(f"   {i+1}. {str(trans.goal_id)[:8]} | {trans.from_status} → {trans.to_status}")

            # Check 6: Test apply_bulk_transitions
            print(f"\n🔄 Testing repo.apply_bulk_transitions()...")
            async with get_uow() as uow:
                result = await uow.goals.apply_bulk_transitions(
                    uow.session,
                    list(plan.transitions)
                )
                print(f"✓ Apply result:")
                print(f"   Total: {result['total']}")
                print(f"   Applied: {result['applied']}")
                print(f"   Skipped: {result['skipped']}")
                print(f"   Failed: {result['failed']}")

                # Show applied transitions
                for r in result['results'][:5]:
                    print(f"   - {r['status']}: {r.get('goal_id', '')[:8]}")

        else:
            print(f"\n⚠️ No candidates found - nothing to test")

    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(diagnose_pending_goals())
