"""
Experience Engine - Core of Learning Loop

This is the orchestrator that turns executions into learning.

Architecture:
    Execution → Experience → SkillStats → Better Skill Selection

Usage:
    # After goal execution
    await experience_engine.record_experience(
        goal_id=goal.id,
        task_type="web_search",
        skill_id="web.search",
        success=True,
        confidence=0.95,
        latency_ms=1234,
        error_type=None
    )

This ONE call:
1. Records the experience
2. Updates skill statistics
3. Makes system smarter for next execution
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from experience.legacy_adapter import LegacyExperienceAdapter, legacy_experience_adapter

from logging_config import get_logger

logger = get_logger(__name__)


class ExperienceEngine:
    """
    Orchestrates experience recording and skill learning.

    This is the HEART of the self-improving system.

    Uses LegacyExperienceAdapter to work with existing database schema.
    """

    def __init__(self):
        self.adapter = legacy_experience_adapter

    async def record_experience(
        self,
        session: AsyncSession,
        goal_id: UUID,
        task_type: str,
        skill_id: str,
        success: bool,
        confidence: float,
        latency_ms: int,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        extra_metadata: Optional[dict] = None
    ):
        """
        Record a single execution experience.

        This is the LEARNING moment.

        After this call:
        - Experience is saved to database
        - Skill stats are updated
        - System becomes smarter

        Args:
            session: Database session
            goal_id: Goal that was executed
            task_type: Type of task (web_search, summarize, etc.)
            skill_id: Skill that was used
            success: Did execution succeed?
            confidence: Confidence score (0.0-1.0)
            latency_ms: Execution time in milliseconds
            error_type: Type of error (if failed)
            error_message: Error message (if failed)
            extra_metadata: Additional context

        Returns:
            None (result is logged)
        """

        # Use adapter to record with legacy schema
        await self.adapter.record_experience(
            session=session,
            goal_id=goal_id,
            task_type=task_type,
            skill_id=skill_id,
            success=success,
            confidence=confidence,
            latency_ms=latency_ms,
            error_type=error_type,
            error_message=error_message,
            extra_metadata=extra_metadata
        )


# Singleton instance
experience_engine = ExperienceEngine()
