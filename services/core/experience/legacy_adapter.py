"""
Legacy Experience Adapter - Adapts new Experience Engine to existing database schema.

Existing schema has different column names than our models.
This adapter bridges the gap.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from logging_config import get_logger

logger = get_logger(__name__)


class LegacyExperienceAdapter:
    """
    Adapter to record experiences using existing database schema.

    Existing experiences table:
    - experience_id (serial, PK)
    - goal_type (varchar)
    - goal_title (text)
    - skill_used (varchar)
    - success (boolean)
    - duration_ms (integer)
    - artifacts_produced (jsonb)
    - confidence (float)
    - execution_context (jsonb)
    - created_at (timestamp)

    Existing skill_stats table:
    - skill_id (varchar, PK)
    - skill_name (varchar)
    - total_executions (int)
    - success_count (int)
    - success_rate (float)
    - avg_latency_ms (float)
    - avg_confidence (float)
    - total_artifacts (int)
    - failure_count (int)
    - last_used (timestamp)
    - created_at (timestamp)
    - updated_at (timestamp)
    """

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
        Record experience using existing schema.
        """
        try:
            # Extract metadata
            metadata = extra_metadata or {}
            goal_title = metadata.get("goal_title", "")
            goal_type = metadata.get("goal_type", task_type)
            artifacts_produced = metadata.get("artifacts_produced", 0)

            # Insert into experiences table (existing schema)
            # Use CAST for JSONB columns (asyncpg/SQLAlchemy compatibility)
            query = text("""
                INSERT INTO experiences (
                    goal_id,
                    goal_type,
                    goal_title,
                    skill_used,
                    success,
                    duration_ms,
                    artifacts_produced,
                    confidence,
                    execution_context,
                    created_at
                ) VALUES (
                    :goal_id,
                    :goal_type,
                    :goal_title,
                    :skill_used,
                    :success,
                    :duration_ms,
                    CAST(:artifacts_produced AS jsonb),
                    :confidence,
                    CAST(:execution_context AS jsonb),
                    NOW()
                )
            """)

            await session.execute(query, {
                "goal_id": goal_id,
                "goal_type": goal_type,
                "goal_title": goal_title,
                "skill_used": skill_id,
                "success": success,
                "duration_ms": latency_ms,
                "artifacts_produced": json.dumps({"count": int(artifacts_produced)}),
                "confidence": confidence,
                "execution_context": json.dumps({
                    "error_type": error_type,
                    "error_message": error_message
                })
            })

            logger.info(
                "experience_recorded_legacy",
                goal_id=str(goal_id),
                task_type=task_type,
                skill_id=skill_id,
                success=success,
                confidence=f"{confidence:.2f}",
                latency_ms=latency_ms
            )

            # Update skill_stats with task_type for context-specific learning
            await self._update_skill_stats(
                session,
                skill_id,
                success,
                confidence,
                latency_ms,
                artifacts_produced,
                task_type
            )

        except Exception as e:
            logger.error(
                "experience_recording_failed",
                error=str(e),
                goal_id=str(goal_id)
            )
            raise

    async def _update_skill_stats(
        self,
        session: AsyncSession,
        skill_id: str,
        success: bool,
        confidence: float,
        latency_ms: int,
        artifacts_count: int,
        task_type: str = "general"
    ):
        """
        Update skill statistics using existing schema.

        Uses UPSERT pattern (INSERT ... ON CONFLICT)
        Now includes Q-LEARNING UPDATE: Q(s,a) ← Q(s,a) + α * (reward - Q(s,a))
        
        IMPORTANT: Always use "global" task_type for single bandit
        No fragmentation between task types - this is critical for learning to work!
        """
        # FORCE global task_type for single bandit
        task_type = "global"
        
        # Calculate reward from environment signal
        task_completion = 1.0 if success else 0.0
        latency_penalty = min(latency_ms / 10000, 0.5)  # 0-0.5 for slow execution
        reward = max(0, task_completion - latency_penalty)
        
        # Get current Q-value for update
        q_result = await session.execute(text("""
            SELECT q_value FROM skill_stats 
            WHERE skill_id = :skill_id AND task_type = :task_type
        """), {"skill_id": skill_id, "task_type": task_type})
        
        q_row = q_result.fetchone()
        current_q = q_row[0] if q_row and q_row[0] is not None else 0.5
        
        # Q-LEARNING UPDATE: α = 0.1
        alpha = 0.1
        new_q = current_q + alpha * (reward - current_q)
        new_q = max(0, min(1, new_q))
        
        logger.info("q_learning_update_legacy",
            skill_id=skill_id,
            current_q=round(current_q, 3),
            reward=round(reward, 3),
            new_q=round(new_q, 3),
            task_type=task_type
        )
        
        query = text("""
            INSERT INTO skill_stats (
                skill_id,
                skill_name,
                total_executions,
                success_count,
                failure_count,
                success_rate,
                avg_latency_ms,
                avg_confidence,
                total_artifacts,
                last_used,
                created_at,
                updated_at,
                task_type,
                q_value
            ) VALUES (
                :skill_id,
                :skill_name,
                1,
                :success_count,
                :failure_count,
                :success_rate,
                :avg_latency_ms,
                :avg_confidence,
                :total_artifacts,
                NOW(),
                NOW(),
                NOW(),
                :task_type,
                :new_q
            )
            ON CONFLICT (skill_id, task_type) DO UPDATE SET
                total_executions = skill_stats.total_executions + 1,
                success_count = skill_stats.success_count + :success_count,
                failure_count = skill_stats.failure_count + :failure_count,
                success_rate = (skill_stats.success_count + :success_count)::float / (skill_stats.total_executions + 1),
                avg_latency_ms = (skill_stats.avg_latency_ms * skill_stats.total_executions + :avg_latency_ms)::float / (skill_stats.total_executions + 1),
                avg_confidence = (skill_stats.avg_confidence * skill_stats.total_executions + :avg_confidence)::float / (skill_stats.total_executions + 1),
                total_artifacts = skill_stats.total_artifacts + :total_artifacts,
                q_value = :new_q,
                last_used = NOW(),
                updated_at = NOW()
            RETURNING
                skill_stats.skill_id,
                skill_stats.total_executions,
                skill_stats.success_rate,
                skill_stats.avg_latency_ms
        """)

        logger.error("Q_WRITE_ATTEMPT",
            skill_id=skill_id,
            task_type=task_type or "general",
            new_q=new_q
        )
        
        result = await session.execute(query, {
            "skill_id": skill_id,
            "skill_name": skill_id.split(".")[-1] if "." in skill_id else skill_id,
            "success_count": 1 if success else 0,
            "failure_count": 0 if success else 1,
            "success_rate": 1.0 if success else 0.0,
            "avg_latency_ms": latency_ms,
            "avg_confidence": confidence,
            "total_artifacts": artifacts_count,
            "task_type": task_type or "general",
            "new_q": new_q
        })

        row = result.fetchone()

        logger.info(
            "skill_stats_updated_legacy",
            skill_id=skill_id,
            total_executions=row[1] if row else 1,
            success_rate=f"{row[2]:.2%}" if row else "N/A",
            avg_latency_ms=f"{row[3]:.0f}" if row else f"{latency_ms}"
        )

    async def get_skill_stats(
        self,
        session: AsyncSession,
        skill_id: str
    ) -> Optional[dict]:
        """
        Get skill statistics from existing schema.
        """
        query = text("""
            SELECT
                skill_id,
                total_executions,
                success_count,
                success_rate,
                avg_latency_ms,
                avg_confidence
            FROM skill_stats
            WHERE skill_id = :skill_id
        """)

        result = await session.execute(query, {"skill_id": skill_id})
        row = result.fetchone()

        if not row:
            return None

        return {
            "skill_id": row[0],
            "total_executions": row[1],
            "success_count": row[2],
            "success_rate": float(row[3]),
            "avg_latency_ms": float(row[4]),
            "avg_confidence": float(row[5])
        }

    async def get_all_skill_stats(
        self,
        session: AsyncSession
    ) -> dict:
        """
        Get all skill statistics as dict.
        """
        query = text("""
            SELECT
                skill_id,
                total_executions,
                success_rate,
                avg_latency_ms
            FROM skill_stats
            WHERE total_executions > 0
        """)

        result = await session.execute(query)
        rows = result.fetchall()

        return {
            row[0]: {
                "total_executions": row[1],
                "success_rate": float(row[2]),
                "avg_latency_ms": float(row[3])
            }
            for row in rows
        }


# Singleton instance
legacy_experience_adapter = LegacyExperienceAdapter()
