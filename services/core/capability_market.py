"""
Capability Market Engine

Pipelines compete for goals based on market_score.
Higher score = more tasks = faster evolution.

Market Score Formula:
    market_score = success_rate * 0.5 + (1/latency) * 0.3 + usage_boost * 0.2
"""

import math
import random
import json
from typing import Optional
from uuid import UUID
from sqlalchemy import text
from database import AsyncSessionLocal

from logging_config import get_logger

logger = get_logger(__name__)


class CapabilityMarket:
    """
    Market where pipelines compete for goals.
    
    Best pipelines get more tasks → faster evolution.
    """

    WEIGHT_SUCCESS = 0.5
    WEIGHT_LATENCY = 0.3
    WEIGHT_USAGE = 0.2

    async def register_pipeline(self, capability: str, pipeline_id: UUID, skills: list) -> None:
        """Register new pipeline in market."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO capability_pipelines (
                        pipeline_id,
                        pipeline_name,
                        capability_name,
                        skills,
                        total_executions,
                        successful_executions,
                        success_rate,
                        avg_latency_ms,
                        lifecycle_state,
                        created_at
                    ) VALUES (
                        :pipeline_id,
                        :pipeline_name,
                        :capability,
                        :skills,
                        0, 0, 0.5, 1000,
                        'experimental',
                        NOW()
                    )
                    ON CONFLICT (pipeline_id) DO NOTHING
                """),
                {
                    "pipeline_id": pipeline_id,
                    "pipeline_name": f"pipeline_{capability}_{pipeline_id}",
                    "capability": capability,
                    "skills": json.dumps(skills),
                }
            )
            await session.commit()

    async def get_pipeline_for_goal(self, capability: str) -> Optional[dict]:
        """
        Select best pipeline for goal using market scoring.
        
        90% = exploitation (best score)
        10% = exploration (random for new variants)
        """
        async with AsyncSessionLocal() as session:
            # Get all pipelines for capability
            result = await session.execute(
                text("""
                    SELECT 
                        pipeline_id,
                        pipeline_name,
                        skills,
                        success_rate,
                        avg_latency_ms,
                        total_executions,
                        lifecycle_state
                    FROM capability_pipelines
                    WHERE capability_name = :capability
                """),
                {"capability": capability}
            )
            rows = result.fetchall()
            
            if not rows:
                return None

            pipelines = []
            for r in rows:
                pipelines.append({
                    "pipeline_id": r[0],
                    "pipeline_name": r[1],
                    "skills": r[2],
                    "success_rate": r[3] or 0.5,
                    "avg_latency_ms": r[4] or 1000,
                    "total_executions": r[5] or 0,
                    "lifecycle_state": r[6],
                })

            # Exploration vs exploitation
            if random.random() < 0.1:
                selected = random.choice(pipelines)
                logger.info(
                    "market_exploration",
                    capability=capability,
                    pipeline=selected["pipeline_name"]
                )
            else:
                # Score pipelines
                scored = []
                for p in pipelines:
                    score = self._calculate_market_score(p)
                    scored.append((p, score))

                # Sort by score
                scored.sort(key=lambda x: x[1], reverse=True)
                selected = scored[0][0]

                logger.info(
                    "market_exploitation",
                    capability=capability,
                    pipeline=selected["pipeline_name"],
                    score=scored[0][1]
                )

            return selected

    def _calculate_market_score(self, pipeline: dict) -> float:
        """Calculate market score for pipeline."""
        success = pipeline["success_rate"]
        latency = pipeline["avg_latency_ms"] or 1000
        executions = pipeline["total_executions"] or 0

        # Normalize latency (faster = better)
        latency_score = 1.0 / (latency / 1000.0)  # 1 second = score 1.0

        # Usage boost (more executions = more proven)
        usage_boost = min(math.log(executions + 1) / 10, 1.0)

        score = (
            success * self.WEIGHT_SUCCESS +
            latency_score * self.WEIGHT_LATENCY +
            usage_boost * self.WEIGHT_USAGE
        )

        return score

    async def record_execution(
        self,
        pipeline_id: UUID,
        success: bool,
        latency_ms: int,
        artifacts: int = 0
    ) -> None:
        """Record execution and update pipeline metrics."""
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    UPDATE capability_pipelines
                    SET 
                        total_executions = COALESCE(total_executions, 0) + 1,
                        successful_executions = COALESCE(successful_executions, 0) + :success_add,
                        success_rate = CASE
                            WHEN COALESCE(total_executions, 0) + 1 = 0 THEN 0.5
                            ELSE (COALESCE(successful_executions, 0) + :success_add)::float / (COALESCE(total_executions, 0) + 1)
                        END,
                        avg_latency_ms = CASE
                            WHEN COALESCE(total_executions, 0) = 0 THEN :latency
                            ELSE (COALESCE(avg_latency_ms, 1000) * COALESCE(total_executions, 0) + :latency) / (COALESCE(total_executions, 0) + 1)
                        END,
                        updated_at = NOW()
                    WHERE pipeline_id = :pipeline_id
                """),
                {
                    "pipeline_id": pipeline_id,
                    "success_add": 1 if success else 0,
                    "latency": latency_ms,
                }
            )
            await session.commit()

            # Check for promotion to stable
            await self._check_promotion(session, pipeline_id)

    async def _check_promotion(self, session, pipeline_id: UUID) -> None:
        """Promote experimental pipeline to stable if performing well."""
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

        success_rate, total_exec, state = row
        
        # Promote if 10+ executions and 80%+ success
        if total_exec and total_exec >= 10 and success_rate and success_rate >= 0.8 and state == "experimental":
            await session.execute(
                text("""
                    UPDATE capability_pipelines
                    SET lifecycle_state = 'stable', updated_at = NOW()
                    WHERE pipeline_id = :pipeline_id
                """),
                {"pipeline_id": pipeline_id}
            )
            logger.info("pipeline_promoted_to_stable", pipeline_id=str(pipeline_id))

    async def get_market_stats(self, capability: str = None) -> dict:
        """Get market statistics."""
        async with AsyncSessionLocal() as session:
            if capability:
                result = await session.execute(
                    text("""
                        SELECT 
                            pipeline_name,
                            success_rate,
                            avg_latency_ms,
                            total_executions,
                            lifecycle_state
                        FROM capability_pipelines
                        WHERE capability_name = :capability
                        ORDER BY success_rate DESC
                    """),
                    {"capability": capability}
                )
            else:
                result = await session.execute(
                    text("""
                        SELECT 
                            capability_name,
                            pipeline_name,
                            success_rate,
                            avg_latency_ms,
                            total_executions,
                            lifecycle_state
                        FROM capability_pipelines
                        ORDER BY success_rate DESC
                        LIMIT 20
                    """)
                )
            
            rows = result.fetchall()
            
            stats = {
                "total_pipelines": len(rows),
                "pipelines": []
            }
            
            for r in rows:
                stats["pipelines"].append({
                    "capability": r[0] if not capability else capability,
                    "pipeline": r[1],
                    "success_rate": r[2] or 0,
                    "latency_ms": r[3] or 0,
                    "executions": r[4] or 0,
                    "state": r[5] if len(r) > 5 else "unknown",
                })
            
            return stats


# Singleton
capability_market = CapabilityMarket()


async def demo():
    """Demo: show market in action."""
    print("🏆 Capability Market Demo\n")
    
    # Simulate pipeline registrations
    await capability_market.register_pipeline(
        "cap_research_topic",
        UUID("11111111-1111-1111-1111-111111111111"),
        ["web_research", "summarize_text"]
    )
    
    await capability_market.register_pipeline(
        "cap_research_topic", 
        UUID("22222222-2222-2222-2222-222222222222"),
        ["web_research", "analyze_text", "summarize_text"]
    )
    
    # Get pipeline for goal
    print("📋 Selecting pipeline for 'research AI trends'...")
    selected = await capability_market.get_pipeline_for_goal("cap_research_topic")
    
    if selected:
        print(f"   Selected: {selected['pipeline_name']}")
        print(f"   Skills: {selected['skills']}")
        print(f"   Score: {capability_market._calculate_market_score(selected):.2f}")
    
    # Simulate executions
    print("\n📈 Simulating 10 executions...")
    
    for i in range(10):
        success = random.choice([True, True, True, False])  # 75%
        latency = random.randint(500, 2000)
        
        await capability_market.record_execution(
            pipeline_id=selected["pipeline_id"],
            success=success,
            latency_ms=latency
        )
        
        print(f"   Exec {i+1}: {'✅' if success else '❌'} {latency}ms")
    
    # Market stats
    stats = await capability_market.get_market_stats("cap_research_topic")
    print(f"\n📊 Market Stats:")
    for p in stats["pipelines"]:
        print(f"   {p['pipeline']}: {p['success_rate']:.0%} success, {p['executions']} runs, {p['state']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())
