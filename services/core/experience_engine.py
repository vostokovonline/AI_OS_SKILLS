"""
EXPERIENCE ENGINE - Learning layer for AI-OS
==============================================

Records execution experiences and enables adaptive skill selection.

Flow:
    Execution → Experience → SkillStats → Better Selection

Author: AI-OS System
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """Single execution experience."""
    goal_id: str
    goal_title: str
    goal_type: str
    skill_id: str
    skill_name: str
    success: bool
    duration_ms: int
    confidence: float
    artifacts_count: int
    error: Optional[str] = None
    capabilities_used: List[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.capabilities_used is None:
            self.capabilities_used = []


@dataclass
class SkillStats:
    """Aggregated skill statistics."""
    skill_id: str
    skill_name: str
    total_executions: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration_ms: int = 0
    total_confidence: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.success_count / self.total_executions
    
    @property
    def avg_duration_ms(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_duration_ms / self.total_executions
    
    @property
    def avg_confidence(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_confidence / self.total_executions


class ExperienceEngine:
    """
    Records experiences and maintains skill statistics.
    
    Usage:
        engine = ExperienceEngine()
        
        # After execution
        engine.record(
            goal_id="123",
            skill_id="core.web_research",
            success=True,
            duration_ms=1500,
            confidence=0.9
        )
        
        # Get best skill for task
        best = engine.get_best_skill("research")
    """
    
    def __init__(self):
        self._stats_cache: Dict[str, SkillStats] = {}
    
    async def record(
        self,
        session: AsyncSession,
        goal_id: str,
        goal_title: str,
        goal_type: str,
        skill_id: str,
        skill_name: str,
        success: bool,
        duration_ms: int,
        confidence: float,
        artifacts_count: int = 0,
        error: Optional[str] = None,
        capabilities_used: List[str] = None
    ) -> bool:
        """
        Record an execution experience.
        
        Args:
            session: Database session
            goal_id: Goal ID
            goal_title: Goal title
            goal_type: Type of goal
            skill_id: Skill ID used
            skill_name: Skill name
            success: Whether execution succeeded
            duration_ms: Execution duration
            confidence: Confidence score
            artifacts_count: Number of artifacts produced
            error: Error message if failed
            capabilities_used: List of capabilities used
            
        Returns:
            True if recorded successfully
        """
        try:
            # Record experience
            await session.execute(
                text("""
                    INSERT INTO experiences
                    (goal_id, goal_title, goal_type, skill_id, skill_name, 
                     success, duration_ms, confidence, artifacts_count, 
                     error, capabilities_used, created_at)
                    VALUES
                    (:goal_id, :goal_title, :goal_type, :skill_id, :skill_name,
                     :success, :duration_ms, :confidence, :artifacts_count,
                     :error, :caps, NOW())
                """),
                {
                    "goal_id": goal_id,
                    "goal_title": goal_title[:500],
                    "goal_type": goal_type,
                    "skill_id": skill_id,
                    "skill_name": skill_name,
                    "success": success,
                    "duration_ms": duration_ms,
                    "confidence": confidence,
                    "artifacts_count": artifacts_count,
                    "error": error[:500] if error else None,
                    "caps": capabilities_used
                }
            )
            
            # Update skill stats
            await self._update_skill_stats(
                session,
                skill_id=skill_id,
                skill_name=skill_name,
                success=success,
                duration_ms=duration_ms,
                confidence=confidence,
                artifacts_count=artifacts_count
            )
            
            await session.commit()
            
            logger.info(
                "experience_recorded",
                goal_id=goal_id,
                skill_id=skill_id,
                success=success
            )
            
            # Invalidate cache
            if skill_id in self._stats_cache:
                del self._stats_cache[skill_id]
            
            return True
            
        except Exception as e:
            logger.error("experience_record_failed", error=str(e))
            return False
    
    async def _update_skill_stats(
        self,
        session: AsyncSession,
        skill_id: str,
        skill_name: str,
        success: bool,
        duration_ms: int,
        confidence: float,
        artifacts_count: int
    ):
        """Update skill statistics."""
        await session.execute(
            text("""
                INSERT INTO skill_stats
                (skill_id, skill_name, total_executions, success_count, 
                 avg_latency_ms, avg_confidence, total_artifacts, failure_count,
                 last_used, updated_at)
                VALUES 
                (:skill_id, :skill_name, 1, :success_count, :duration_ms,
                 :confidence, :artifacts_count, :failure_count, NOW(), NOW())
                ON CONFLICT (skill_id) DO UPDATE SET
                    total_executions = skill_stats.total_executions + 1,
                    success_count = skill_stats.success_count + :success_count,
                    avg_latency_ms = (
                        (skill_stats.avg_latency_ms * skill_stats.total_executions + :duration_ms) 
                        / (skill_stats.total_executions + 1)
                    ),
                    avg_confidence = (
                        (skill_stats.avg_confidence * skill_stats.total_executions + :confidence)
                        / (skill_stats.total_executions + 1)
                    ),
                    total_artifacts = skill_stats.total_artifacts + :artifacts_count,
                    failure_count = skill_stats.failure_count + :failure_count,
                    last_used = NOW(),
                    updated_at = NOW(),
                    success_rate = skill_stats.success_count::float / NULLIF(skill_stats.total_executions, 0)::float
            """),
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "success_count": 1 if success else 0,
                "failure_count": 0 if success else 1,
                "duration_ms": duration_ms,
                "confidence": confidence,
                "artifacts_count": artifacts_count
            }
        )
    
    async def get_skill_stats(self, session: AsyncSession, skill_id: str) -> Optional[SkillStats]:
        """Get statistics for a skill."""
        # Check cache first
        if skill_id in self._stats_cache:
            return self._stats_cache[skill_id]
        
        try:
            result = await session.execute(
                text("""
                    SELECT skill_id, skill_name, total_executions, success_count,
                           failure_count, avg_latency_ms, avg_confidence
                    FROM skill_stats
                    WHERE skill_id = :skill_id
                """),
                {"skill_id": skill_id}
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            stats = SkillStats(
                skill_id=row[0],
                skill_name=row[1],
                total_executions=row[2],
                success_count=row[3],
                failure_count=row[4],
                total_duration_ms=int(row[5] * row[2]) if row[5] else 0,
                total_confidence=row[6] * row[2] if row[6] else 0.0
            )
            
            self._stats_cache[skill_id] = stats
            return stats
            
        except Exception as e:
            logger.error("get_skill_stats_failed", error=str(e))
            return None
    
    async def get_best_skill(
        self,
        session: AsyncSession,
        capability: str,
        min_confidence: float = 0.5
    ) -> Optional[str]:
        """
        Get the best skill for a capability based on history.
        
        Args:
            session: Database session
            capability: Required capability
            min_confidence: Minimum confidence threshold
            
        Returns:
            Best skill ID or None
        """
        try:
            # Find skills with this capability from experiences
            result = await session.execute(
                text("""
                    SELECT skill_id, 
                           COUNT(*) as executions,
                           SUM(CASE WHEN success THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
                           AVG(duration_ms) as avg_duration,
                           AVG(confidence) as avg_confidence
                    FROM experiences
                    WHERE :capability = ANY(capabilities_used)
                      AND success = true
                      AND confidence >= :min_conf
                    GROUP BY skill_id
                    ORDER BY success_rate DESC, avg_duration ASC
                    LIMIT 1
                """),
                {"capability": capability, "min_conf": min_confidence}
            )
            
            row = result.fetchone()
            if row:
                return row[0]
            
            return None
            
        except Exception as e:
            logger.error("get_best_skill_failed", error=str(e))
            return None
    
    async def get_skill_rankings(
        self,
        session: AsyncSession,
        limit: int = 10
    ) -> List[Dict]:
        """Get ranked list of skills by success rate."""
        try:
            result = await session.execute(
                text("""
                    SELECT skill_id, skill_name, total_executions, success_rate,
                           avg_latency_ms, avg_confidence
                    FROM skill_stats
                    WHERE total_executions >= 3
                    ORDER BY success_rate DESC, avg_latency_ms ASC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            
            rows = result.fetchall()
            return [
                {
                    "skill_id": r[0],
                    "skill_name": r[1],
                    "total_executions": r[2],
                    "success_rate": float(r[3]) if r[3] else 0,
                    "avg_latency_ms": float(r[4]) if r[4] else 0,
                    "avg_confidence": float(r[5]) if r[5] else 0
                }
                for r in rows
            ]
            
        except Exception as e:
            logger.error("get_skill_rankings_failed", error=str(e))
            return []
    
    async def detect_skill_gaps(
        self,
        session: AsyncSession,
        goal_types: List[str] = None
    ) -> List[Dict]:
        """
        Detect skill gaps - capabilities that frequently fail or timeout.
        
        Returns:
            List of gaps with suggestions
        """
        try:
            query = """
                SELECT skill_id, 
                       COUNT(*) as attempts,
                       SUM(CASE WHEN success THEN 1 ELSE 0 END)::float / COUNT(*) as success_rate,
                       AVG(duration_ms) as avg_duration
                FROM experiences
                WHERE 1=1
            """
            params = {}
            
            if goal_types:
                query += " AND goal_type = ANY(:goal_types)"
                params["goal_types"] = goal_types
            
            query += """
                GROUP BY skill_id
                HAVING COUNT(*) >= 3
                   AND (SUM(CASE WHEN success THEN 1 ELSE 0 END)::float / COUNT(*)) < 0.5
                ORDER BY attempts DESC
                LIMIT 10
            """
            
            result = await session.execute(text(query), params)
            rows = result.fetchall()
            
            gaps = []
            for r in rows:
                gaps.append({
                    "skill_id": r[0],
                    "attempts": r[1],
                    "success_rate": float(r[2]),
                    "avg_duration_ms": float(r[3]) if r[3] else 0,
                    "suggestion": "Consider auto-generating alternative skill"
                })
            
            return gaps
            
        except Exception as e:
            logger.error("detect_skill_gaps_failed", error=str(e))
            return []


# Global instance
_experience_engine = None


def get_experience_engine() -> ExperienceEngine:
    """Get global experience engine instance."""
    global _experience_engine
    if _experience_engine is None:
        _experience_engine = ExperienceEngine()
    return _experience_engine
