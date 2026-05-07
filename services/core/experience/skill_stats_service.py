"""
Skill Stats Service - Aggregates experiences into skill statistics.

This is the "memory" of the system.
Every experience updates the stats.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from experience.experience_models import Experience, SkillStats
from experience.experience_repository import SkillStatsRepository, ExperienceRepository


class SkillStatsService:
    """
    Aggregates experiences into skill statistics.

    After every experience:
    1. Get or create stats record
    2. Update metrics
    3. Compute new aggregates
    4. Save
    """

    def __init__(self):
        self.stats_repo = SkillStatsRepository()
        self.exp_repo = ExperienceRepository()

    async def update_stats(
        self,
        session: AsyncSession,
        experience: Experience
    ) -> SkillStats:
        """
        Update skill stats based on new experience.

        This is the LEARNING moment.
        """
        # Get existing stats or create new
        stats = await self.stats_repo.get(
            session,
            experience.skill_id,
            experience.task_type
        )

        if not stats:
            stats = SkillStats(
                skill_id=experience.skill_id,
                task_type=experience.task_type,
                usage_count=0,
                success_count=0,
                first_used_at=datetime.utcnow()
            )

        # Update usage count
        stats.usage_count += 1

        # Update success count
        if experience.success:
            stats.success_count += 1

        # Update success rate
        stats.success_rate = stats.success_count / stats.usage_count

        # Update moving averages
        stats.avg_confidence = self._update_moving_avg(
            stats.avg_confidence,
            experience.confidence or 0.0,
            stats.usage_count
        )

        stats.avg_latency_ms = self._update_moving_avg(
            stats.avg_latency_ms,
            experience.latency_ms,
            stats.usage_count
        )

        # Update recent performance (last 10)
        await self._update_recent_metrics(session, stats, experience)

        # Update timestamp
        stats.last_used_at = datetime.utcnow()

        # Save
        await self.stats_repo.save(session, stats)

        return stats

    def _update_moving_avg(
        self,
        current_avg: float,
        new_value: float,
        count: int
    ) -> float:
        """
        Update moving average.

        Formula: new_avg = old_avg + (new_value - old_avg) / count
        """
        if count == 1:
            return new_value

        return current_avg + (new_value - current_avg) / count

    async def _update_recent_metrics(
        self,
        session: AsyncSession,
        stats: SkillStats,
        experience: Experience
    ):
        """
        Update recent performance metrics (last 10 executions).
        """
        recent_experiences = await self.exp_repo.get_recent_experiences(
            session,
            experience.skill_id,
            experience.task_type,
            limit=10
        )

        if recent_experiences:
            # Recent success rate
            recent_successes = sum(1 for e in recent_experiences if e.success)
            stats.recent_success_rate = recent_successes / len(recent_experiences)

            # Recent average latency
            recent_latencies = [e.latency_ms for e in recent_experiences]
            stats.recent_avg_latency = sum(recent_latencies) / len(recent_latencies)

    async def get_skill_performance(
        self,
        session: AsyncSession,
        skill_id: str,
        task_type: str
    ) -> Optional[dict]:
        """
        Get skill performance summary.
        """
        stats = await self.stats_repo.get(session, skill_id, task_type)

        if not stats:
            return None

        return {
            "skill_id": stats.skill_id,
            "task_type": stats.task_type,
            "usage_count": stats.usage_count,
            "success_count": stats.success_count,
            "success_rate": stats.success_rate,
            "avg_confidence": stats.avg_confidence,
            "avg_latency_ms": stats.avg_latency_ms,
            "recent_success_rate": stats.recent_success_rate,
            "recent_avg_latency": stats.recent_avg_latency,
            "composite_score": stats.compute_score(),
            "is_reliable": stats.is_reliable,
            "is_new": stats.is_new,
            "first_used_at": stats.first_used_at,
            "last_used_at": stats.last_used_at
        }

    async def get_top_skills_for_task(
        self,
        session: AsyncSession,
        task_type: str,
        limit: int = 10
    ) -> list:
        """
        Get top performing skills for a task.
        """
        stats_list = await self.stats_repo.get_top_skills(
            session,
            task_type,
            limit
        )

        return [
            {
                "skill_id": s.skill_id,
                "task_type": s.task_type,
                "success_rate": s.success_rate,
                "usage_count": s.usage_count,
                "avg_latency_ms": s.avg_latency_ms,
                "composite_score": s.compute_score()
            }
            for s in stats_list
        ]
