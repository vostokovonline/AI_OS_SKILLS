"""
Capability Invention Engine

Auto-creates capabilities from stable pipelines.

Rule:
    if pipeline.usage_count > N and pipeline.success_rate > X
    → create capability

This closes the loop:
    experience → stable pipelines → new capabilities → planner uses them
"""

import json
from sqlalchemy import text
from database import AsyncSessionLocal

from logging_config import get_logger

logger = get_logger(__name__)


class CapabilityInventionEngine:
    """
    Automatically creates capabilities from proven pipelines.
    """

    # Thresholds for capability creation
    MIN_EXECUTIONS = 10
    MIN_SUCCESS_RATE = 0.75

    # Semantic name mapping (skill pattern → capability name)
    SKILL_TO_CAPABILITY = {
        ("web_research", "summarize_text", "write_file"): "cap_research_and_report",
        ("web_research", "write_file"): "cap_web_research_and_save",
        ("summarize_text", "write_file"): "cap_summarize_and_document",
        ("analyze_text", "summarize_text"): "cap_analyze_and_summarize",
        ("file_read", "analyze_text"): "cap_read_and_analyze",
        ("web_research", "summarize_text"): "cap_quick_research",
        ("echo",): "cap_simple_echo",
    }

    async def invent_from_pipelines(self) -> list[dict]:
        """
        Scan pipelines and create capabilities from stable ones.
        """
        async with AsyncSessionLocal() as session:
            # Get stable pipelines that meet thresholds
            result = await session.execute(
                text("""
                    SELECT 
                        pipeline_id,
                        pipeline_name,
                        skills,
                        success_rate,
                        total_executions,
                        capability_name
                    FROM capability_pipelines
                    WHERE lifecycle_state = 'stable'
                        AND total_executions >= :min_exec
                        AND success_rate >= :min_success
                        AND capability_name IS NULL
                """),
                {
                    "min_exec": self.MIN_EXECUTIONS,
                    "min_success": self.MIN_SUCCESS_RATE,
                }
            )
            rows = result.fetchall()

            new_capabilities = []

            for row in rows:
                pipeline_id, pipeline_name, skills, success_rate, total_executions, _ = row

                # Generate capability name from skills
                capability_id = self._generate_capability_name(skills)

                if not capability_id:
                    logger.debug(
                        "capability_name_unclear",
                        pipeline=pipeline_name,
                        skills=skills
                    )
                    continue

                # Register capability
                await session.execute(
                    text("""
                        INSERT INTO capability_registry (
                            capability_id,
                            display_name,
                            description,
                            keywords,
                            skills,
                            lifecycle_state,
                            created_at
                        ) VALUES (
                            :cap_id,
                            :display_name,
                            :description,
                            :keywords,
                            :skills,
                            'active',
                            NOW()
                        )
                        ON CONFLICT (capability_id) DO NOTHING
                    """),
                    {
                        "cap_id": capability_id,
                        "display_name": capability_id.replace("cap_", "").replace("_", " ").title(),
                        "description": f"Auto-generated capability from pipeline: {pipeline_name}",
                        "keywords": json.dumps(self._extract_keywords(skills)),
                        "skills": skills,
                    }
                )

                # Link pipeline to capability
                await session.execute(
                    text("""
                        UPDATE capability_pipelines
                        SET capability_name = :cap_name
                        WHERE pipeline_id = :pipeline_id
                    """),
                    {
                        "cap_name": capability_id,
                        "pipeline_id": pipeline_id,
                    }
                )

                new_capabilities.append({
                    "capability_id": capability_id,
                    "source_pipeline": pipeline_name,
                    "skills": skills,
                    "success_rate": success_rate,
                })

                logger.info(
                    "capability_invented",
                    capability=capability_id,
                    pipeline=pipeline_name,
                    success_rate=success_rate
                )

            await session.commit()
            return new_capabilities

    def _generate_capability_name(self, skills) -> str:
        """Generate semantic capability name from skill sequence."""
        if not skills:
            return None

        skills_tuple = tuple(skills)

        # Direct mapping
        if skills_tuple in self.SKILL_TO_CAPABILITY:
            return self.SKILL_TO_CAPABILITY[skills_tuple]

        # Partial match
        for pattern, cap in self.SKILL_TO_CAPABILITY.items():
            if all(s in skills_tuple for s in pattern):
                return f"{cap}_v2"

        # Generic fallback
        key_skills = [s.replace("core.", "") for s in skills[:2]]
        return f"cap_{'_'.join(key_skills)}"

    def _extract_keywords(self, skills) -> list[str]:
        """Extract keywords from skills for matching."""
        keywords = []
        for skill in skills:
            name = skill.replace("core.", "")
            keywords.extend(name.split("_"))
        return keywords


async def run_capability_invention():
    """Run capability invention."""
    engine = CapabilityInventionEngine()
    
    print("🔬 Running Capability Invention...")
    
    # For demo, lower thresholds
    original_min = engine.MIN_EXECUTIONS
    engine.MIN_EXECUTIONS = 3
    engine.MIN_SUCCESS_RATE = 0.7
    
    results = await engine.invent_from_pipelines()
    
    engine.MIN_EXECUTIONS = original_min
    
    if results:
        print(f"✅ Created {len(results)} capabilities:")
        for r in results:
            print(f"  - {r['capability_id']}")
            print(f"    from: {r['source_pipeline']}")
            print(f"    success: {r['success_rate']:.0%}")
    else:
        print("ℹ️ No pipelines meet thresholds yet")
        print(f"   (need >{original_min} executions, >{original_min*100}% success rate)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_capability_invention())
