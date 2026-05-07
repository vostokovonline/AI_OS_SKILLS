"""
Capability Invention Engine

Converts discovered pipelines into capabilities.

Pipeline → Capability criteria:
- MIN_FREQUENCY >= 2
- MIN_SUCCESS_RATE >= 0.7
- MIN_STEPS >= 2

Usage:
    await capability_invention_engine.invent()
"""

from typing import Optional
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal

from logging_config import get_logger

logger = get_logger(__name__)


class CapabilityInventionEngine:
    """Converts pipelines into capabilities."""

    MIN_FREQUENCY = 2
    MIN_SUCCESS_RATE = 0.7
    MIN_STEPS = 2

    async def invent(self) -> list[dict]:
        """Main invention method - promotes pipelines to capabilities."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        skill_id,
                        component_skills,
                        success_rate,
                        avg_latency_ms
                    FROM composite_skills
                    WHERE status = 'candidate'
                """)
            )
            rows = result.fetchall()
            
            capabilities_created = []
            
            for row in rows:
                skill_id = row[0]
                component_skills = row[1]
                success_rate = row[2]
                avg_latency_ms = row[3]
                
                # Check criteria
                steps = component_skills if isinstance(component_skills, list) else []
                step_count = len(steps)
                
                if step_count < self.MIN_STEPS:
                    logger.debug(
                        "capability_criteria_not_met_steps",
                        skill_id=skill_id,
                        steps=step_count,
                        required=self.MIN_STEPS
                    )
                    continue
                    
                if success_rate < self.MIN_SUCCESS_RATE:
                    logger.debug(
                        "capability_criteria_not_met_success",
                        skill_id=skill_id,
                        success_rate=success_rate,
                        required=self.MIN_SUCCESS_RATE
                    )
                    continue
                
                # Create capability
                capability_id = f"cap_{skill_id.replace('pipeline_', '')}"
                description = self._generate_description(skill_id, steps)
                
                try:
                    await session.execute(
                        text("""
                            INSERT INTO capabilities (
                                capability_id,
                                source_pipeline,
                                description,
                                status,
                                success_rate,
                                avg_latency_ms,
                                created_at
                            ) VALUES (
                                :capability_id,
                                :source_pipeline,
                                :description,
                                'candidate',
                                :success_rate,
                                :latency_ms,
                                NOW()
                            )
                            ON CONFLICT (capability_id) DO UPDATE SET
                                success_rate = EXCLUDED.success_rate,
                                avg_latency_ms = EXCLUDED.avg_latency_ms
                        """),
                        {
                            "capability_id": capability_id,
                            "source_pipeline": skill_id,
                            "description": description,
                            "success_rate": float(success_rate),
                            "latency_ms": float(avg_latency_ms) if avg_latency_ms else 0,
                        }
                    )
                    
                    capabilities_created.append({
                        "capability_id": capability_id,
                        "source_pipeline": skill_id,
                        "steps": steps,
                        "success_rate": success_rate,
                    })
                    
                    logger.info(
                        "capability_invented",
                        capability_id=capability_id,
                        pipeline=skill_id,
                        steps=step_count,
                        success_rate=success_rate
                    )
                    
                except Exception as e:
                    logger.error(
                        "capability_creation_failed",
                        error=str(e),
                        pipeline=skill_id
                    )
            
            await session.commit()
            return capabilities_created

    def _generate_description(self, pipeline_id: str, steps: list[str]) -> str:
        """Generate human-readable description for capability."""
        if not steps:
            return "Auto-generated capability"
        
        # Map skill IDs to action verbs
        action_map = {
            "web_research": "research topics on the web",
            "write_file": "write results to files",
            "summarize_text": "summarize information",
            "file_read": "read files",
            "file_list": "list files",
            "file_search": "search files",
            "run_command": "execute commands",
            "echo": "echo text",
            "analyze_text": "analyze text",
            "create_directory": "create directories",
        }
        
        actions = []
        for step in steps:
            skill_name = step.split(".")[-1] if "." in step else step
            action = action_map.get(skill_name, f"execute {skill_name}")
            actions.append(action)
        
        if len(actions) == 1:
            return f"Ability to {actions[0]}."
        
        return " and ".join([", ".join(actions[:-1]), actions[-1]]).capitalize() + "."


async def run_capability_invention():
    """CLI entry point for capability invention."""
    engine = CapabilityInventionEngine()
    print("🎯 Running Capability Invention...")
    
    capabilities = await engine.invent()
    print(f"✅ Created {len(capabilities)} capabilities:")
    
    for cap in capabilities:
        print(f"  - {cap['capability_id']}")
        print(f"    pipeline: {cap['source_pipeline']}")
        print(f"    success: {cap['success_rate']:.0%}")
    
    return capabilities


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_capability_invention())
