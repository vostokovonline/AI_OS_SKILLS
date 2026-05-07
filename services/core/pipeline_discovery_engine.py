from datetime import datetime
from typing import Optional
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal


class PipelineDiscoveryEngine:
    """Discovers pipelines from execution patterns in experiences."""

    MIN_FREQUENCY = 3
    MIN_SUCCESS_RATE = 0.5

    async def discover(self) -> list[dict]:
        """Main discovery method - finds pipeline candidates from experiences."""
        async with AsyncSessionLocal() as session:
            # Aggregate skill sequences by goal_id directly from experiences
            result = await session.execute(
                text("""
                    SELECT 
                        skill_sequence,
                        frequency,
                        avg_success_rate,
                        avg_duration_ms
                    FROM (
                        SELECT
                            jsonb_agg(skill_used ORDER BY created_at) AS skill_sequence,
                            COUNT(*) AS frequency,
                            AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) AS avg_success_rate,
                            AVG(duration_ms) AS avg_duration_ms
                        FROM experiences
                        WHERE goal_id IS NOT NULL
                        GROUP BY goal_id
                        HAVING COUNT(*) >= 1
                    ) AS goal_patterns
                    WHERE frequency >= :min_freq
                    ORDER BY frequency DESC
                """),
                {"min_freq": self.MIN_FREQUENCY}
            )
            rows = result.fetchall()
            patterns = [
                {
                    "skill_sequence": row[0] if isinstance(row[0], list) else [row[0]],
                    "frequency": row[1],
                    "avg_success_rate": row[2] or 0,
                    "avg_duration_ms": row[3] or 0,
                }
                for row in rows
            ]
            return self._extract_pipelines(patterns)

    async def _get_patterns(self, session: AsyncSession) -> list[dict]:
        """Fetch skill sequences from skill_patterns."""
        result = await session.execute(
            text("""
                SELECT 
                    skill_sequence,
                    frequency,
                    avg_success_rate,
                    avg_duration_ms
                FROM skill_patterns
                WHERE frequency >= :min_freq
                ORDER BY frequency DESC
            """),
            {"min_freq": self.MIN_FREQUENCY}
        )
        rows = result.fetchall()
        return [
            {
                "skill_sequence": row[0] if isinstance(row[0], list) else [row[0]],
                "frequency": row[1],
                "avg_success_rate": row[2] or 0,
                "avg_duration_ms": row[3] or 0,
            }
            for row in rows
        ]

    def _extract_pipelines(self, patterns: list[dict]) -> list[dict]:
        """Extract candidate pipelines from patterns."""
        pipelines = []
        
        for p in patterns:
            seq = p["skill_sequence"]
            if len(seq) >= 1:
                pipeline = {
                    "name": self._generate_pipeline_name(seq),
                    "steps": seq,
                    "frequency": p["frequency"],
                    "success_rate": p["avg_success_rate"],
                    "avg_duration_ms": p["avg_duration_ms"],
                    "type": "multi_skill" if len(seq) > 1 else "single_skill",
                }
                pipelines.append(pipeline)
        
        return pipelines

    def _generate_pipeline_name(self, steps: list[str]) -> str:
        """Generate pipeline name from steps."""
        if len(steps) == 1:
            return f"pipeline_{steps[0].replace('.', '_')}"
        return f"pipeline_{'_'.join(s.replace('.', '_') for s in steps[:3])}"

    async def register_pipelines(self, pipelines: list[dict]) -> int:
        """Register discovered pipelines as composite_skills."""
        registered = 0
        async with AsyncSessionLocal() as session:
            for p in pipelines:
                try:
                    result = await session.execute(
                        text("""
                            INSERT INTO composite_skills (
                                skill_id, version, component_skills, execution_strategy,
                                status, success_rate, avg_latency_ms, created_at
                            ) VALUES (
                                :skill_id, 1, :components, 'sequential',
                                'candidate', :success_rate, :latency, NOW()
                            )
                            ON CONFLICT (skill_id) DO UPDATE SET
                                success_rate = EXCLUDED.success_rate,
                                avg_latency_ms = EXCLUDED.avg_latency_ms,
                                component_skills = EXCLUDED.component_skills
                        """),
                        {
                            "skill_id": p["name"],
                            "components": json.dumps(p["steps"]),
                            "success_rate": float(p["success_rate"]),
                            "latency": float(p["avg_duration_ms"]),
                        }
                    )
                    registered += 1
                    print(f"✅ Registered pipeline: {p['name']}")
                except Exception as e:
                    print(f"❌ Failed to register {p['name']}: {e}")
                    print(f"   params: skill_id={p['name']}, components={json.dumps(p['steps'])}, success_rate={p['success_rate']}, latency={p['avg_duration_ms']}")
            await session.commit()
        return registered


async def run_discovery():
    """CLI entry point for pipeline discovery."""
    engine = PipelineDiscoveryEngine()
    print("🔍 Running Pipeline Discovery...")
    
    pipelines = await engine.discover()
    print(f"📊 Found {len(pipelines)} pipeline candidates")
    
    for p in pipelines:
        print(f"  - {p['name']}: {p['steps']} (freq={p['frequency']}, success={p['success_rate']:.2f})")
    
    if pipelines:
        registered = await engine.register_pipelines(pipelines)
        print(f"✅ Registered {registered} pipelines")
    
    return pipelines


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_discovery())
