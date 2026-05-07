"""
🔴 CRITICAL FIX: Unblock Children of Ongoing Goals

PROBLEM: 1,082 atomic goals are blocked waiting for their parent to complete.
SOLUTION: Children of directional/meta/continuous goals should execute INDEPENDENTLY.

IMPACT: 188 goals immediately unblocked
"""

import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


async def fix_blocked_ongoing_children():
    """
    Unblock children of directional/meta/continuous goals.

    These goals are ongoing missions - they should NOT block their children.
    Children should execute independently.
    """

    async with AsyncSessionLocal() as session:
        # Count affected goals
        count_result = await session.execute(text("""
            SELECT COUNT(*)
            FROM goals g
            JOIN goals p ON g.parent_id = p.id
            WHERE g.status = 'blocked'
              AND p.goal_type IN ('directional', 'meta', 'continuous', 'strategic')
        """))

        count = count_result.scalar()
        logger.info(f"Found {count} blocked goals from ongoing parent goals")

        if count == 0:
            logger.info("No blocked ongoing children found - system is healthy")
            return 0

        # Get details before fix
        details_result = await session.execute(text("""
            SELECT
                p.goal_type,
                COUNT(*) as blocked_children,
                COUNT(DISTINCT p.id) as parent_count
            FROM goals g
            JOIN goals p ON g.parent_id = p.id
            WHERE g.status = 'blocked'
              AND p.goal_type IN ('directional', 'meta', 'continuous', 'strategic')
            GROUP BY p.goal_type
            ORDER BY blocked_children DESC
        """))

        logger.info("Blocked goals by parent type:")
        for row in details_result:
            goal_type, blocked_count, parent_count = row
            logger.info(f"  {goal_type}: {blocked_count} blocked children from {parent_count} parents")

        # Unblock them
        result = await session.execute(text("""
            UPDATE goals
            SET status = 'pending',
                updated_at = NOW()
            WHERE id IN (
                SELECT g.id
                FROM goals g
                JOIN goals p ON g.parent_id = p.id
                WHERE g.status = 'blocked'
                  AND p.goal_type IN ('directional', 'meta', 'continuous', 'strategic')
            )
        """))

        await session.commit()

        unblocked = result.rowcount
        logger.info(
            "ongoing_children_unblocked",
            unblocked=unblocked,
            message=f"Unblocked {unblocked} goals from ongoing parent goals"
        )

        return unblocked


async def get_blocked_goals_summary():
    """Get summary of blocked goals."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'blocked') as total_blocked,
                COUNT(*) FILTER (WHERE status = 'active') as total_active,
                COUNT(*) FILTER (WHERE status = 'pending') as total_pending,
                COUNT(*) FILTER (WHERE status = 'done') as total_done,
                COUNT(*) as total_goals
            FROM goals
            WHERE is_atomic = true
        """))

        row = result.fetchone()

        return {
            "total_blocked": row[0],
            "total_active": row[1],
            "total_pending": row[2],
            "total_done": row[3],
            "total_goals": row[4]
        }


async def main():
    """Main execution."""
    print("="*70)
    print("🔴 CRITICAL FIX: Unblock Children of Ongoing Goals")
    print("="*70)
    print()

    # Get before state
    print("📊 BEFORE FIX:")
    before = await get_blocked_goals_summary()
    print(f"  Total atomic goals: {before['total_goals']}")
    print(f"  Blocked: {before['total_blocked']}")
    print(f"  Active: {before['total_active']}")
    print(f"  Pending: {before['total_pending']}")
    print(f"  Done: {before['total_done']}")
    print()

    # Execute fix
    print("🔧 EXECUTING FIX...")
    unblocked = await fix_blocked_ongoing_children()
    print()

    # Get after state
    print("📊 AFTER FIX:")
    after = await get_blocked_goals_summary()
    print(f"  Total atomic goals: {after['total_goals']}")
    print(f"  Blocked: {after['total_blocked']}")
    print(f"  Active: {after['total_active']}")
    print(f"  Pending: {after['total_pending']}")
    print(f"  Done: {after['total_done']}")
    print()

    print("="*70)
    if unblocked > 0:
        print(f"✅ SUCCESS: Unblocked {unblocked} goals!")
        print(f"   These goals can now be executed by the scheduler.")
    else:
        print("ℹ️  INFO: No goals needed unblocking - system is healthy")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
