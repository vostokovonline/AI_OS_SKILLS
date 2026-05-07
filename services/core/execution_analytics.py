"""
Execution Analytics Module
==========================

Records goal executions, skill performance, and experiences for Phase 1.1.
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class ExecutionAnalytics:
    """Records execution data for analytics."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def record_execution(
        self,
        goal_id: str,
        goal_title: str,
        skill_id: str,
        execution_engine: str,
        status: str,
        duration_ms: int,
        confidence: float,
        artifacts_count: int,
        error_message: Optional[str] = None,
        execution_trace: Optional[Dict] = None
    ) -> int:
        """Record a goal execution."""
        result = await self.session.execute(
            text("""
                INSERT INTO goal_executions 
                (goal_id, goal_title, skill_id, execution_engine, status, 
                 duration_ms, confidence, artifacts_count, error_message, 
                 execution_trace, created_at)
                VALUES 
                (:goal_id, :goal_title, :skill_id, :execution_engine, :status,
                 :duration_ms, :confidence, :artifacts_count, :error_message,
                 :execution_trace, NOW())
                RETURNING execution_id
            """),
            {
                "goal_id": goal_id,
                "goal_title": goal_title,
                "skill_id": skill_id,
                "execution_engine": execution_engine,
                "status": status,
                "duration_ms": duration_ms,
                "confidence": confidence,
                "artifacts_count": artifacts_count,
                "error_message": error_message,
                "execution_trace": json.dumps(execution_trace) if execution_trace else None
            }
        )
        row = result.fetchone()
        await self.session.commit()
        return row[0] if row else None
    
    async def record_experience(
        self,
        goal_type: str,
        goal_title: str,
        skill_used: str,
        success: bool,
        duration_ms: int,
        artifacts: list,
        confidence: float,
        execution_context: Optional[Dict] = None
    ) -> int:
        """Record an experience for pattern detection."""
        result = await self.session.execute(
            text("""
                INSERT INTO experiences
                (goal_type, goal_title, skill_used, success, duration_ms,
                 artifacts_produced, confidence, execution_context, created_at)
                VALUES
                (:goal_type, :goal_title, :skill_used, :success, :duration_ms,
                 :artifacts, :confidence, :context, NOW())
                RETURNING experience_id
            """),
            {
                "goal_type": goal_type,
                "goal_title": goal_title,
                "skill_used": skill_used,
                "success": success,
                "duration_ms": duration_ms,
                "artifacts": json.dumps(artifacts),
                "confidence": confidence,
                "context": json.dumps(execution_context) if execution_context else None
            }
        )
        row = result.fetchone()
        await self.session.commit()
        return row[0] if row else None
    
    async def update_skill_stats(
        self,
        skill_id: str,
        skill_name: str,
        success: bool,
        duration_ms: int,
        confidence: float,
        artifacts_count: int
    ):
        """Update skill performance metrics."""
        await self.session.execute(
            text("""
                INSERT INTO skill_stats 
                (skill_id, skill_name, total_executions, success_count, 
                 avg_latency_ms, avg_confidence, total_artifacts, failure_count,
                 last_used, updated_at)
                VALUES 
                (:skill_id, :skill_name, 1, :success_count, :avg_latency,
                 :avg_confidence, :artifacts_count, :failure_count, NOW(), NOW())
                ON CONFLICT (skill_id) DO UPDATE SET
                    total_executions = skill_stats.total_executions + 1,
                    success_count = skill_stats.success_count + :success_count,
                    avg_latency_ms = (
                        (skill_stats.avg_latency_ms * skill_stats.total_executions + :avg_latency) 
                        / (skill_stats.total_executions + 1)
                    ),
                    avg_confidence = (
                        (skill_stats.avg_confidence * skill_stats.total_executions + :avg_confidence)
                        / (skill_stats.total_executions + 1)
                    ),
                    total_artifacts = skill_stats.total_artifacts + :artifacts_count,
                    failure_count = skill_stats.failure_count + :failure_count,
                    last_used = NOW(),
                    updated_at = NOW(),
                    success_rate = skill_stats.success_count::float / skill_stats.total_executions::float
            """),
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "success_count": 1 if success else 0,
                "failure_count": 0 if success else 1,
                "avg_latency": duration_ms,
                "avg_confidence": confidence,
                "artifacts_count": artifacts_count
            }
        )
        await self.session.commit()
    
    async def get_skill_stats(self, skill_id: str) -> Optional[Dict]:
        """Get skill performance stats."""
        result = await self.session.execute(
            text("""
                SELECT skill_id, skill_name, total_executions, success_rate,
                       avg_latency_ms, avg_confidence, last_used
                FROM skill_stats
                WHERE skill_id = :skill_id
            """),
            {"skill_id": skill_id}
        )
        row = result.fetchone()
        if row:
            return {
                "skill_id": row[0],
                "skill_name": row[1],
                "total_executions": row[2],
                "success_rate": float(row[3]) if row[3] else 0,
                "avg_latency_ms": float(row[4]) if row[4] else 0,
                "avg_confidence": float(row[5]) if row[5] else 0,
                "last_used": row[6]
            }
        return None
    
    async def get_skill_rankings(self) -> list:
        """Get skills ranked by success rate and usage."""
        result = await self.session.execute(
            text("""
                SELECT skill_id, skill_name, total_executions, success_rate,
                       avg_latency_ms
                FROM skill_stats
                WHERE total_executions >= 3
                ORDER BY success_rate DESC, total_executions DESC
                LIMIT 10
            """)
        )
        rows = result.fetchall()
        return [
            {
                "skill_id": r[0],
                "skill_name": r[1],
                "total_executions": r[2],
                "success_rate": float(r[3]) if r[3] else 0,
                "avg_latency_ms": float(r[4]) if r[4] else 0
            }
            for r in rows
        ]
    
    async def detect_patterns(self, goal_type: str = None) -> list:
        """Detect patterns from experiences."""
        query = """
            SELECT skill_used, 
                   COUNT(*) as total,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                   AVG(duration_ms) as avg_duration,
                   AVG(confidence) as avg_confidence
            FROM experiences
        """
        params = {}
        if goal_type:
            query += " WHERE goal_type = :goal_type"
            params["goal_type"] = goal_type
        
        query += " GROUP BY skill_used ORDER BY successes DESC"
        
        result = await self.session.execute(text(query), params)
        rows = result.fetchall()
        
        patterns = []
        for r in rows:
            success_rate = r[2] / r[1] if r[1] > 0 else 0
            patterns.append({
                "skill_used": r[0],
                "total_executions": r[1],
                "success_count": r[2],
                "success_rate": success_rate,
                "avg_duration_ms": float(r[3]) if r[3] else 0,
                "avg_confidence": float(r[4]) if r[4] else 0
            })
        
        return patterns


async def get_analytics(session: AsyncSession) -> ExecutionAnalytics:
    """Factory function for ExecutionAnalytics."""
    return ExecutionAnalytics(session)
