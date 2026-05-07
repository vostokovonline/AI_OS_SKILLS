"""
Skill Stats Cache - In-Memory Cache for Skill Statistics

Problem: _get_skill_stats_from_db() returns {} because loop.is_running()
Solution: Load stats into memory and update periodically

Architecture:
    DB → SkillStatsCache → SkillSelector (every 30s)

This is the ONLY way skill stats can work in FastAPI/Celery.
"""

import asyncio
import time
from typing import Dict, Optional
from threading import Lock

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from logging_config import get_logger

logger = get_logger(__name__)


class SkillStatsCache:
    """
    Thread-safe in-memory cache for skill statistics.

    Updated periodically from database.
    Used by SkillSelector for real-time scoring.
    """

    def __init__(self, update_interval: int = 30):
        """
        Args:
            update_interval: Seconds between cache updates (default: 30s)
        """
        self._cache: Dict[str, dict] = {}
        self._lock = Lock()
        self._update_interval = update_interval
        self._last_update = 0
        self._is_updating = False

    async def get_stats(self, skill_id: str) -> Optional[dict]:
        """
        Get skill stats from cache.

        Returns None if skill not found or cache not initialized.
        """
        with self._lock:
            return self._cache.get(skill_id)

    async def get_all_stats(self) -> Dict[str, dict]:
        """
        Get all stats from cache.
        """
        with self._lock:
            return self._cache.copy()

    async def ensure_fresh(self):
        """
        Ensure cache is fresh.
        Updates if:
        - Never updated
        - Update interval passed
        """
        now = time.time()

        with self._lock:
            # Don't start multiple updates
            if self._is_updating:
                return

            # Check if update needed
            if self._last_update > 0 and (now - self._last_update) < self._update_interval:
                return

            # Start update
            self._is_updating = True

        try:
            # Load from DB (outside lock)
            stats = await self._load_from_db()

            # Update cache
            with self._lock:
                self._cache = stats
                self._last_update = now

                logger.info(
                    "skill_stats_cache_updated",
                    skills_count=len(stats),
                    cache_age_s=0
                )
        finally:
            with self._lock:
                self._is_updating = False

    async def _load_from_db(self) -> Dict[str, dict]:
        """
        Load skill stats from database.

        Uses existing skill_stats table schema.
        Now includes Q-values for proper RL-style learning.
        """
        stats = {}

        try:
            async with AsyncSessionLocal() as session:
                # Load stats with priority for 'global' task_type (single bandit mode)
                # Order by task_type DESC so 'global' comes first
                query = text("""
                    SELECT
                        skill_id,
                        total_executions,
                        success_count,
                        success_rate,
                        avg_latency_ms,
                        avg_confidence,
                        task_type,
                        q_value
                    FROM skill_stats
                    WHERE total_executions > 0
                    ORDER BY 
                        CASE WHEN task_type = 'global' THEN 0 ELSE 1 END,
                        skill_id
                """)

                result = await session.execute(query)
                rows = result.fetchall()

                for row in rows:
                    skill_id = row[0]
                    task_type = row[6] or 'general'
                    q_value = row[7] if row[7] is not None else float(row[3]) if row[3] else 0.5  # Default to success_rate
                    
                    # Store task_type specific data
                    key = f"{skill_id}:{task_type}"
                    
                    if skill_id not in stats:
                        stats[skill_id] = {
                            "skill_id": skill_id,
                            "total_executions": row[1],
                            "success_count": row[2],
                            "success_rate": float(row[3]) if row[3] else 0.0,
                            "avg_latency_ms": float(row[4]) if row[4] else 0.0,
                            "avg_confidence": float(row[5]) if row[5] else 0.0,
                            "q_value": q_value,  # Q-value for RL-style learning
                            "exploration_bonus": 1.0 / max(1, row[1]) ** 0.5,
                            "task_specific": {}
                        }
                    
                    # Store task-type specific stats
                    if task_type != 'general':
                        stats[skill_id]["task_specific"][task_type] = {
                            "total_executions": row[1],
                            "success_count": row[2],
                            "success_rate": float(row[3]) if row[3] else 0.0,
                            "avg_latency_ms": float(row[4]) if row[4] else 0.0
                        }

        except Exception as e:
            logger.error(
                "skill_stats_load_failed",
                error=str(e)
            )

        return stats

    def invalidate(self):
        """
        Force cache reload on next access.
        """
        with self._lock:
            self._last_update = 0


# Global singleton
skill_stats_cache = SkillStatsCache(update_interval=30)


async def get_skill_stats_sync() -> Dict[str, dict]:
    """
    Synchronous-friendly way to get skill stats.

    This is what SkillSelector should use.

    Auto-refreshes cache if needed.
    """
    await skill_stats_cache.ensure_fresh()
    return await skill_stats_cache.get_all_stats()
