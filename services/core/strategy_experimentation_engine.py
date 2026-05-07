"""
Strategy Experimentation Engine

Enables A/B testing of pipelines for capabilities.

Uses existing schema:
- capability_pipelines: pipeline_id, capability_name, skills, success_rate, is_active, lifecycle_state
- pipeline_executions: execution_id, pipeline_id, success, latency_ms
"""

from typing import Optional
import json
import random
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal

from logging_config import get_logger

logger = get_logger(__name__)


class StrategyExperimentationEngine:
    """
    Manages pipeline experimentation for capabilities.
    
    Implements exploration vs exploitation:
    - 10% random selection (exploration)
    - 90% best success_rate (exploitation)
    """

    EXPLORATION_RATE = 0.1
    MIN_EXECUTIONS_FOR_PROMOTION = 3

    async def select_pipeline(self, capability_name: str) -> Optional[dict]:
        """
        Select pipeline for capability using exploration/exploitation strategy.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        pipeline_id,
                        pipeline_name,
                        capability_name,
                        skills,
                        success_rate,
                        total_executions,
                        is_active,
                        lifecycle_state
                    FROM capability_pipelines
                    WHERE capability_name = :capability_name
                    ORDER BY 
                        CASE lifecycle_state
                            WHEN 'stable' THEN 1
                            WHEN 'experimental' THEN 2
                            ELSE 3
                        END,
                        success_rate DESC NULLS LAST
                """),
                {"capability_name": capability_name}
            )
            rows = result.fetchall()
            
            if not rows:
                logger.debug("no_pipelines_for_capability", capability_name=capability_name)
                return None
            
            pipelines = [
                {
                    "pipeline_id": row[0],
                    "pipeline_name": row[1],
                    "capability_name": row[2],
                    "skills": row[3],
                    "success_rate": row[4] or 0,
                    "total_executions": row[5] or 0,
                    "is_active": row[6] or False,
                    "lifecycle_state": row[7],
                }
                for row in rows
            ]
            
            # Exploration vs exploitation
            if random.random() < self.EXPLORATION_RATE:
                selected = random.choice(pipelines)
                logger.info(
                    "pipeline_selected_exploration",
                    capability_name=capability_name,
                    pipeline_id=str(selected["pipeline_id"]),
                    strategy="exploration"
                )
            else:
                # Exploitation: select best by success_rate
                stable = [p for p in pipelines if p["lifecycle_state"] == "stable"]
                if stable:
                    selected = stable[0]
                else:
                    selected = max(pipelines, key=lambda p: p["success_rate"] or 0)
                
                logger.info(
                    "pipeline_selected_exploitation",
                    capability_name=capability_name,
                    pipeline_id=str(selected["pipeline_id"]),
                    strategy="exploitation",
                    success_rate=selected["success_rate"]
                )
            
            return selected

    async def record_execution(
        self,
        pipeline_id: UUID,
        goal_id: Optional[UUID],
        success: bool,
        latency_ms: int,
        confidence: float = 1.0,
        artifacts_produced: int = 0,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record pipeline execution result and update stats.
        """
        async with AsyncSessionLocal() as session:
            # Insert execution record
            await session.execute(
                text("""
                    INSERT INTO pipeline_executions (
                        execution_id,
                        pipeline_id,
                        goal_id,
                        success,
                        latency_ms,
                        confidence,
                        artifacts_produced,
                        error_type,
                        error_message,
                        executed_at
                    ) VALUES (
                        gen_random_uuid(),
                        :pipeline_id,
                        :goal_id,
                        :success,
                        :latency_ms,
                        :confidence,
                        :artifacts_produced,
                        :error_type,
                        :error_message,
                        NOW()
                    )
                """),
                {
                    "pipeline_id": pipeline_id,
                    "goal_id": goal_id,
                    "success": success,
                    "latency_ms": latency_ms,
                    "confidence": confidence,
                    "artifacts_produced": artifacts_produced,
                    "error_type": error_type,
                    "error_message": error_message,
                }
            )
            
            # Update pipeline stats
            await session.execute(
                text("""
                    UPDATE capability_pipelines
                    SET 
                        total_executions = COALESCE(total_executions, 0) + 1,
                        successful_executions = COALESCE(successful_executions, 0) + :success_add,
                        success_rate = CASE 
                            WHEN COALESCE(total_executions, 0) + 1 = 0 THEN 0
                            ELSE (COALESCE(successful_executions, 0) + :success_add)::float / (COALESCE(total_executions, 0) + 1)
                        END,
                        avg_latency_ms = CASE 
                            WHEN COALESCE(total_executions, 0) = 0 THEN :latency_ms
                            ELSE (COALESCE(avg_latency_ms, 0) * COALESCE(total_executions, 0) + :latency_ms) / (COALESCE(total_executions, 0) + 1)
                        END,
                        last_used_at = NOW(),
                        updated_at = NOW()
                    WHERE pipeline_id = :pipeline_id
                """),
                {
                    "pipeline_id": pipeline_id,
                    "success_add": 1 if success else 0,
                    "latency_ms": latency_ms,
                }
            )
            
            await session.commit()
            
            logger.info(
                "pipeline_execution_recorded",
                pipeline_id=str(pipeline_id),
                success=success,
                latency_ms=latency_ms
            )
            
            # Check for auto-promotion
            await self._check_promotion(session, pipeline_id)

    async def _check_promotion(self, session: AsyncSession, pipeline_id: UUID) -> None:
        """
        Check if a pipeline should be promoted to stable.
        """
        result = await session.execute(
            text("""
                SELECT success_rate, total_executions, lifecycle_state
                FROM capability_pipelines
                WHERE pipeline_id = :pipeline_id
            """),
            {"pipeline_id": pipeline_id}
        )
        row = result.fetchone()
        
        if not row:
            return
            
        success_rate, total_executions, lifecycle_state = row
        
        if (total_executions and total_executions >= self.MIN_EXECUTIONS_FOR_PROMOTION and 
            success_rate and success_rate >= 0.8 and 
            lifecycle_state == "experimental"):
            
            # Promote to stable
            await session.execute(
                text("""
                    UPDATE capability_pipelines
                    SET lifecycle_state = 'stable', updated_at = NOW()
                    WHERE pipeline_id = :pipeline_id
                """),
                {"pipeline_id": pipeline_id}
            )
            
            logger.info(
                "pipeline_promoted_to_stable",
                pipeline_id=str(pipeline_id),
                success_rate=success_rate
            )

    async def register_pipeline(
        self,
        capability_name: str,
        pipeline_name: str,
        skills: list,
        description: str = "",
        lifecycle_state: str = "experimental"
    ) -> UUID:
        """
        Register a new pipeline for a capability.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    INSERT INTO capability_pipelines (
                        pipeline_id,
                        pipeline_name,
                        capability_name,
                        skills,
                        description,
                        lifecycle_state,
                        created_at,
                        updated_at
                    ) VALUES (
                        gen_random_uuid(),
                        :pipeline_name,
                        :capability_name,
                        :skills,
                        :description,
                        :lifecycle_state,
                        NOW(),
                        NOW()
                    )
                    RETURNING pipeline_id
                """),
                {
                    "pipeline_name": pipeline_name,
                    "capability_name": capability_name,
                    "skills": json.dumps(skills),
                    "description": description,
                    "lifecycle_state": lifecycle_state,
                }
            )
            row = result.fetchone()
            await session.commit()
            
            logger.info(
                "pipeline_registered",
                capability_name=capability_name,
                pipeline_id=str(row[0]) if row else None
            )
            
            return row[0] if row else None


async def run_experimentation_demo():
    """Demo: show how experimentation works."""
    engine = StrategyExperimentationEngine()
    
    # Register our discovered capability pipeline
    cap_name = "cap_core_web_research_core_write_file_core_summarize_text"
    pipeline_name = "pipeline_research_and_summarize"
    skills = ["core.web_research", "core.write_file", "core.summarize_text"]
    
    pipeline_id = await engine.register_pipeline(
        capability_name=cap_name,
        pipeline_name=pipeline_name,
        skills=skills,
        description="Auto-generated from discovery",
        lifecycle_state="experimental"
    )
    print(f"📝 Registered pipeline: {pipeline_id}")
    
    # Simulate executions
    for i in range(5):
        success = random.choice([True, True, True, False])  # 75% success
        latency = random.randint(500, 1500)
        
        await engine.record_execution(
            pipeline_id=pipeline_id,
            goal_id=None,
            success=success,
            latency_ms=latency,
            confidence=0.9,
            artifacts_produced=1 if success else 0,
            error_message=None if success else "Test error"
        )
        
        print(f"  Execution {i+1}: {'✅' if success else '❌'} latency={latency}ms")
    
    # Check promotion
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT pipeline_name, success_rate, total_executions, lifecycle_state FROM capability_pipelines WHERE pipeline_id = :id"),
            {"id": pipeline_id}
        )
        row = result.fetchone()
        if row:
            print(f"\n📊 Pipeline stats:")
            print(f"   name: {row[0]}")
            print(f"   success_rate: {row[1]:.1%}" if row[1] else "   success_rate: N/A")
            print(f"   executions: {row[2]}")
            print(f"   state: {row[3]}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_experimentation_demo())
