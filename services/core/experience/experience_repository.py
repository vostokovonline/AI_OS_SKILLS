"""
Experience Repository - Database operations for experiences and skill stats.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from experience.experience_models import Experience, SkillStats


class ExperienceRepository:
    """
    Database operations for Experience records.
    """

    async def save(self, session: AsyncSession, experience: Experience) -> Experience:
        """
        Save experience to database.
        """
        session.add(experience)
        await session.flush()
        return experience

    async def get_recent_experiences(
        self,
        session: AsyncSession,
        skill_id: str,
        task_type: str,
        limit: int = 10
    ) -> List[Experience]:
        """
        Get recent experiences for a skill+task combination.
        Used for computing recent performance metrics.
        """
        query = (
            select(Experience)
            .where(
                and_(
                    Experience.skill_id == skill_id,
                    Experience.task_type == task_type
                )
            )
            .order_by(Experience.created_at.desc())
            .limit(limit)
        )

        result = await session.execute(query)
        return result.scalars().all()

    async def get_expressions_by_goal(
        self,
        session: AsyncSession,
        goal_id: UUID
    ) -> List[Experience]:
        """
        Get all experiences for a specific goal.
        """
        query = (
            select(Experience)
            .where(Experience.goal_id == goal_id)
            .order_by(Experience.created_at.desc())
        )

        result = await session.execute(query)
        return result.scalars().all()

    async def get_stats_since(
        self,
        session: AsyncSession,
        since: timedelta
    ) -> dict:
        """
        Get aggregate statistics since a given time.
        """
        cutoff = datetime.utcnow() - since

        # Total experiences
        total_query = select(func.count(Experience.id)).where(Experience.created_at >= cutoff)
        total_result = await session.execute(total_query)
        total_count = total_result.scalar() or 0

        # Success rate
        success_query = (
            select(func.count(Experience.id))
            .where(
                and_(
                    Experience.created_at >= cutoff,
                    Experience.success == True
                )
            )
        )
        success_result = await session.execute(success_query)
        success_count = success_result.scalar() or 0

        success_rate = success_count / total_count if total_count > 0 else 0.0

        return {
            "total_experiences": total_count,
            "success_count": success_count,
            "success_rate": success_rate,
            "cutoff": cutoff
        }


class SkillStatsRepository:
    """
    Database operations for SkillStats records.
    """

    async def get(
        self,
        session: AsyncSession,
        skill_id: str,
        task_type: str
    ) -> Optional[SkillStats]:
        """
        Get stats for a specific skill+task combination.
        """
        query = (
            select(SkillStats)
            .where(
                and_(
                    SkillStats.skill_id == skill_id,
                    SkillStats.task_type == task_type
                )
            )
        )

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def save(self, session: AsyncSession, stats: SkillStats) -> SkillStats:
        """
        Save or update stats.
        Uses INSERT ... ON CONFLICT for upsert.
        """
        session.add(stats)
        await session.flush()
        return stats

    async def get_top_skills(
        self,
        session: AsyncSession,
        task_type: str,
        limit: int = 10
    ) -> List[SkillStats]:
        """
        Get top performing skills for a task type.
        Ordered by success_rate, then usage_count.
        """
        query = (
            select(SkillStats)
            .where(SkillStats.task_type == task_type)
            .where(SkillStats.usage_count >= 3)  # At least 3 uses
            .order_by(
                SkillStats.success_rate.desc(),
                SkillStats.usage_count.desc()
            )
            .limit(limit)
        )

        result = await session.execute(query)
        return result.scalars().all()

    async def get_all_skills(self, session: AsyncSession) -> List[SkillStats]:
        """
        Get all skill stats.
        """
        query = select(SkillStats).order_by(SkillStats.updated_at.desc())
        result = await session.execute(query)
        return result.scalars().all()

    async def get_underperforming_skills(
        self,
        session: AsyncSession,
        min_uses: int = 10,
        max_failure_rate: float = 0.3
    ) -> List[SkillStats]:
        """
        Get skills that are underperforming.
        Used for identifying skills that need improvement.
        """
        query = (
            select(SkillStats)
            .where(SkillStats.usage_count >= min_uses)
            .where(
                SkillStats.success_rate < (1.0 - max_failure_rate)
            )
            .order_by(SkillStats.success_rate.asc())
        )

        result = await session.execute(query)
        return result.scalars().all()
