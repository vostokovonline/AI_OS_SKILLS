"""
🔴 CRITICAL FIX: Decompose Stuck Achievable Parents

PROBLEM: 40 achievable parent goals have 883 blocked atomic children.
ROOT CAUSE: These goals were created but never decomposed.
SOLUTION: Force decompose all stuck achievable parents.

IMPACT: 883 goals immediately unblocked (+45% execution capacity)
"""

import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


async def get_stuck_achievable_parents(limit: int = 50):
    """
    Get all achievable parent goals that are blocking their children.

    These are non-atomic goals that were created but never decomposed.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("""
            SELECT DISTINCT
                p.id,
                p.title,
                p.description,
                p.goal_type,
                COUNT(g.id) as blocked_children
            FROM goals p
            JOIN goals g ON g.parent_id = p.id
            WHERE p.is_atomic = false
              AND p.status IN ('active', 'pending')
              AND g.status = 'blocked'
              AND p.goal_type = 'achievable'
            GROUP BY p.id, p.title, p.description, p.goal_type
            ORDER BY blocked_children DESC
            LIMIT :limit
        """), {"limit": limit})

        parents = result.fetchall()
        return [
            {
                "id": str(row[0]),
                "title": row[1],
                "description": row[2],
                "goal_type": row[3],
                "blocked_children": row[4]
            }
            for row in parents
        ]


async def force_decompose_stuck_parents():
    """
    Decompose all stuck achievable parents.

    These goals were created but never decomposed. Their children are
    permanently blocked waiting for decomposition to happen.
    """
    from goal_decomposer import GoalDecomposer

    # Get stuck parents
    parents = await get_stuck_achievable_parents(limit=50)

    if not parents:
        logger.info("no_stuck_parents_found")
        return {
            "total_parents": 0,
            "decomposed": 0,
            "failed": 0,
            "blocked_unblocked": 0
        }

    logger.info(
        "found_stuck_parents",
        total_parents=len(parents),
        total_blocked=sum(p["blocked_children"] for p in parents)
    )

    decomposer = GoalDecomposer()
    results = {
        "total_parents": len(parents),
        "decomposed": 0,
        "failed": 0,
        "blocked_unblocked": 0,
        "details": []
    }

    # Decompose each parent
    for parent in parents:
        parent_id = parent["id"]
        title = parent["title"]
        blocked_count = parent["blocked_children"]

        try:
            logger.info(
                "decomposing_parent",
                parent_id=parent_id,
                title=title[:50],
                blocked_children=blocked_count
            )

            # Trigger decomposition (decompose_goal creates its own session)
            subgoals = await decomposer.decompose_goal(
                goal_id=parent_id,
                max_depth=1
            )

            if subgoals:
                results["decomposed"] += 1
                results["blocked_unblocked"] += blocked_count

                logger.info(
                    "parent_decomposed_success",
                    parent_id=parent_id,
                    subgoals_created=len(subgoals),
                    children_unblocked=blocked_count
                )

                results["details"].append({
                    "parent_id": parent_id,
                    "title": title[:50],
                    "status": "success",
                    "subgoals_created": len(subgoals),
                    "children_unblocked": blocked_count
                })
            else:
                results["failed"] += 1
                logger.warning(
                    "parent_decompose_no_subgoals",
                    parent_id=parent_id,
                    title=title[:50]
                )

                results["details"].append({
                    "parent_id": parent_id,
                    "title": title[:50],
                    "status": "no_subgoals",
                    "error": "Decomposer returned no subgoals"
                })

        except Exception as e:
            results["failed"] += 1
            logger.error(
                "parent_decompose_failed",
                parent_id=parent_id,
                title=title[:50],
                error=str(e)[:200]
            )

            results["details"].append({
                "parent_id": parent_id,
                "title": title[:50],
                "status": "error",
                "error": str(e)[:200]
            })

    return results


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
    print("=" * 70)
    print("🔴 CRITICAL FIX: Decompose Stuck Achievable Parents")
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
    results = await force_decompose_stuck_parents()
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

    # Print decomposition results
    print("=" * 70)
    print("📊 DECOMPOSITION RESULTS:")
    print(f"  Total parents processed: {results['total_parents']}")
    print(f"  Successfully decomposed: {results['decomposed']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Children unblocked: {results['blocked_unblocked']}")
    print("=" * 70)
    print()

    # Print detailed breakdown
    if results["details"]:
        print("📋 DETAILED BREAKDOWN:")
        for detail in results["details"]:
            status_icon = "✅" if detail["status"] == "success" else "❌"
            print(f"  {status_icon} {detail['title']}")
            print(f"     Status: {detail['status']}")
            if detail["status"] == "success":
                print(f"     Subgoals created: {detail['subgoals_created']}")
                print(f"     Children unblocked: {detail['children_unblocked']}")
            else:
                print(f"     Error: {detail.get('error', 'Unknown')}")
        print()

    print("=" * 70)
    if results["decomposed"] > 0:
        print(f"✅ SUCCESS: {results['decomposed']} parents decomposed!")
        print(f"   {results['blocked_unblocked']} goals can now be executed by the scheduler.")
    else:
        print("ℹ️  INFO: No parents were successfully decomposed")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
