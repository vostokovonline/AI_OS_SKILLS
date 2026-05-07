"""
🔴 CRITICAL FIX P2: Unblock Children of Exploratory Parents

PROBLEM: Exploratory goals have blocked atomic children.
ROOT CAUSE: Exploratory goals are for RESEARCH - outcome unknown.
SOLUTION: Children of exploratory goals should execute independently.

IMPACT: ~23 goals unblocked (+1% execution capacity)

RATIONALE:
- Exploratory goals are experiments - outcome unknown
- Children should run independently to explore possibilities
- Same logic as directional/meta goals (P0 fix)
"""

import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


async def fix_blocked_exploratory_children():
    """
    Unblock children of exploratory goals.

    These goals are experiments - they should NOT block their children.
    Children should execute independently.
    """

    async with AsyncSessionLocal() as session:
        # Count affected goals
        count_result = await session.execute(text("""
            SELECT COUNT(*)
            FROM goals g
            JOIN goals p ON g.parent_id = p.id
            WHERE g.status = 'blocked'
              AND p.goal_type = 'exploratory'
        """))

        count = count_result.scalar()
        logger.info(f"Found {count} blocked goals from exploratory parent goals")

        if count == 0:
            logger.info("No blocked exploratory children found - system is healthy")
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
              AND p.goal_type = 'exploratory'
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
                  AND p.goal_type = 'exploratory'
            )
        """))

        await session.commit()

        unblocked = result.rowcount
        logger.info(
            "exploratory_children_unblocked",
            unblocked=unblocked,
            message=f"Unblocked {unblocked} goals from exploratory parent goals"
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


async def check_remaining_blocked():
    """Check what blocked goals remain after all fixes."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT
                p.goal_type,
                p.title,
                COUNT(g.id) as blocked_children
            FROM goals g
            JOIN goals p ON g.parent_id = p.id
            WHERE g.status = 'blocked'
            GROUP BY p.goal_type, p.title
            ORDER BY blocked_children DESC
            LIMIT 10
        """))

        return [
            {
                "parent_type": row[0],
                "parent_title": row[1],
                "blocked_children": row[2]
            }
            for row in result.fetchall()
        ]


async def main():
    """Main execution."""
    print("=" * 70)
    print("🔴 CRITICAL FIX P2: Unblock Children of Exploratory Goals")
    print("=" * 70)
    print()

    # Get before state
    print("📊 BEFORE FIX:")
    before = await get_blocked_goals_summary()
    print(f"  Total atomic goals: {before['total_goals']}")
    print(f"  Blocked: {before['total_blocked']} ({before['total_blocked']/before['total_goals']*100:.1f}%)")
    print(f"  Active: {before['total_active']}")
    print(f"  Pending: {before['total_pending']}")
    print(f"  Done: {before['total_done']}")
    print()

    # Execute fix
    print("🔧 EXECUTING FIX...")
    unblocked = await fix_blocked_exploratory_children()
    print()

    # Get after state
    print("📊 AFTER FIX:")
    after = await get_blocked_goals_summary()
    print(f"  Total atomic goals: {after['total_goals']}")
    print(f"  Blocked: {after['total_blocked']} ({after['total_blocked']/after['total_goals']*100:.1f}%)")
    print(f"  Active: {after['total_active']}")
    print(f"  Pending: {after['total_pending']}")
    print(f"  Done: {after['total_done']}")
    print()

    # Check remaining blocked
    remaining = await check_remaining_blocked()
    if remaining:
        print("=" * 70)
        print("📋 REMAINING BLOCKED GOALS:")
        for item in remaining:
            print(f"  Parent: {item['parent_title'][:50]}")
            print(f"  Type: {item['parent_type']}")
            print(f"  Blocked children: {item['blocked_children']}")
            print()
    else:
        print("=" * 70)
        print("✅ ALL BLOCKED GOALS RESOLVED!")
        print("=" * 70)
        print()

    print("=" * 70)
    if unblocked > 0:
        print(f"✅ SUCCESS: Unblocked {unblocked} goals!")
        print(f"   These goals can now be executed by the scheduler.")
    else:
        print("ℹ️  INFO: No goals needed unblocking - system is healthy")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
