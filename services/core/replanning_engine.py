"""
Progress Monitor & Re-Planning Engine

Monitors goal execution and triggers re-planning when tasks fail or get stuck.

Flow:
    Monitor active goals
    → Detect failures/stuck
    → Trigger re-planning
    → Create new atomic tasks
    → Update DAG
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


class ProgressMonitor:
    """
    Monitors goal execution and detects issues.
    """

    STUCK_THRESHOLD_MINUTES = 30
    MAX_RETRIES = 3

    async def check_active_goals(self) -> dict:
        """Check all active goals for issues."""
        async with AsyncSessionLocal() as session:
            # Find stuck goals (active but no progress for N minutes)
            result = await session.execute(
                text(f"""
                    SELECT 
                        g.id,
                        g.title,
                        g.status,
                        g.progress,
                        g.updated_at,
                        g.execution_started_at,
                        EXTRACT(EPOCH FROM (NOW() - COALESCE(g.execution_started_at, g.updated_at))) / 60 as minutes_stuck
                    FROM goals g
                    WHERE g.status = 'active'
                    AND g.progress < 1.0
                    AND (
                        g.execution_started_at < NOW() - INTERVAL '{self.STUCK_THRESHOLD_MINUTES} minutes'
                        OR g.updated_at < NOW() - INTERVAL '{self.STUCK_THRESHOLD_MINUTES} minutes'
                    )
                    ORDER BY minutes_stuck DESC
                    LIMIT 20
                """)
            )
            stuck_goals = []
            for row in result.fetchall():
                stuck_goals.append({
                    "goal_id": str(row[0]),
                    "title": row[1],
                    "status": row[2],
                    "progress": float(row[3]) if row[3] else 0,
                    "minutes_stuck": row[5],
                })

            # Find failed goals
            result = await session.execute(
                text("""
                    SELECT id, title, status, execution_trace
                    FROM goals
                    WHERE status = 'failed'
                    AND updated_at > NOW() - INTERVAL '1 hour'
                    ORDER BY updated_at DESC
                    LIMIT 10
                """)
            )
            failed_goals = []
            for row in result.fetchall():
                failed_goals.append({
                    "goal_id": str(row[0]),
                    "title": row[1],
                    "status": row[2],
                })

            return {
                "stuck_goals": stuck_goals,
                "failed_goals": failed_goals,
                "total_stuck": len(stuck_goals),
                "total_failed": len(failed_goals),
            }


class RePlanner:
    """
    Re-plans failed or stuck goals.
    """

    async def replan_goal(self, goal_id: UUID) -> dict:
        """
        Re-plan a failed or stuck goal.
        
        Steps:
        1. Analyze why it failed
        2. Create new sub-tasks
        3. Update dependencies
        """
        async with AsyncSessionLocal() as session:
            # Get goal info
            result = await session.execute(
                text("""
                    SELECT id, title, description, parent_id
                    FROM goals
                    WHERE id = :goal_id
                """),
                {"goal_id": goal_id}
            )
            row = result.fetchone()
            
            if not row:
                return {"success": False, "reason": "Goal not found"}

            goal_title = row[1]
            goal_desc = row[2]
            parent_id = row[3]

            # Reset goal to pending for re-planning
            await session.execute(
                text("""
                    UPDATE goals
                    SET status = 'pending', progress = 0, updated_at = NOW()
                    WHERE id = :goal_id
                """),
                {"goal_id": goal_id}
            )
            
            # Create recovery tasks
            recovery_tasks = self._generate_recovery_tasks(goal_title, goal_desc)
            
            created_tasks = []
            for task_title in recovery_tasks:
                new_id = await session.execute(
                    text("""
                        INSERT INTO goals (id, title, status, parent_id, is_atomic, goal_type, created_at, updated_at)
                        VALUES (gen_random_uuid(), :title, 'pending', :parent_id, true, 'achievable', NOW(), NOW())
                        RETURNING id
                    """),
                    {"title": task_title, "parent_id": goal_id}
                )
                task_id = new_id.scalar()
                created_tasks.append(str(task_id))

            await session.commit()

            logger.info(
                "goal_replanned",
                original_goal=str(goal_id),
                new_tasks=len(created_tasks)
            )

            return {
                "success": True,
                "original_goal": str(goal_id),
                "new_tasks": created_tasks,
                "recovery_tasks": recovery_tasks,
            }

    def _generate_recovery_tasks(self, title: str, description: str) -> List[str]:
        """Generate recovery tasks based on goal type."""
        # Simple rule-based recovery tasks
        tasks = []
        
        if "research" in title.lower():
            tasks = [
                f"Research: {title}",
                f"Analyze findings for: {title}",
                f"Summarize research results",
            ]
        elif "deploy" in title.lower() or "kubernetes" in title.lower():
            tasks = [
                f"Debug deployment issue: {title}",
                f"Fix configuration for: {title}",
                f"Retry deployment: {title}",
            ]
        elif "build" in title.lower() or "create" in title.lower():
            tasks = [
                f"Debug build issue: {title}",
                f"Fix and rebuild: {title}",
            ]
        else:
            # Generic recovery
            tasks = [
                f"Analyze failure: {title}",
                f"Create fix plan for: {title}",
                f"Execute fix: {title}",
            ]

        return tasks


# Singleton instances
progress_monitor = ProgressMonitor()
re_planner = RePlanner()


async def run_progress_monitor():
    """Run progress monitoring and re-planning."""
    logger.info("progress_monitor_start")
    
    # Check for stuck/failed goals
    status = await progress_monitor.check_active_goals()
    
    logger.info(
        "progress_monitor_check",
        stuck=status["total_stuck"],
        failed=status["total_failed"]
    )

    # Re-plan failed goals
    replanned_count = 0
    for failed in status["failed_goals"]:
        try:
            result = await re_planner.replan_goal(UUID(failed["goal_id"]))
            if result.get("success"):
                replanned_count += 1
        except Exception as e:
            logger.error("replan_failed", goal_id=failed["goal_id"], error=str(e))

    logger.info(
        "progress_monitor_complete",
        stuck=status["total_stuck"],
        failed=status["total_failed"],
        replanned=replanned_count
    )

    return status


if __name__ == "__main__":
    import asyncio
    
    async def test():
        status = await progress_monitor.check_active_goals()
        print(f"📊 Status: {status['total_stuck']} stuck, {status['total_failed']} failed")
        
        if status["failed_goals"]:
            print(f"\n🔄 Re-planning {len(status['failed_goals'])} failed goals...")
            for failed in status["failed_goals"]:
                result = await re_planner.replan_goal(UUID(failed["goal_id"]))
                print(f"  {failed['title'][:40]}: {result}")
    
    asyncio.run(test())
