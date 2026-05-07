"""
Failure Analysis Engine

Analyzes execution failures to identify patterns and drive pipeline improvement.

Flow:
    Execution fails → Record failure → Analyze patterns → Suggest improvements
    
Key queries:
    - Which skills fail most?
    - What error types are common?
    - Which pipelines have highest failure rate?
    - What mutations could fix failures?
"""

from typing import Optional
import json
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from database import AsyncSessionLocal

from logging_config import get_logger

logger = get_logger(__name__)


class FailureAnalysisEngine:
    """
    Analyzes failures to drive pipeline improvement.
    """

    async def record_failure(
        self,
        goal_id: Optional[UUID],
        pipeline_id: Optional[UUID],
        capability_name: Optional[str],
        failed_skill: str,
        error_type: Optional[str],
        error_message: Optional[str],
        context: Optional[dict] = None
    ) -> UUID:
        """
        Record a failure for analysis.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    INSERT INTO execution_failures (
                        goal_id,
                        pipeline_id,
                        capability_name,
                        failed_skill,
                        error_type,
                        error_message,
                        context,
                        created_at
                    ) VALUES (
                        :goal_id,
                        :pipeline_id,
                        :capability_name,
                        :failed_skill,
                        :error_type,
                        :error_message,
                        :context,
                        NOW()
                    )
                    RETURNING id
                """),
                {
                    "goal_id": goal_id,
                    "pipeline_id": pipeline_id,
                    "capability_name": capability_name,
                    "failed_skill": failed_skill,
                    "error_type": error_type,
                    "error_message": error_message,
                    "context": json.dumps(context) if context else None,
                }
            )
            row = result.fetchone()
            await session.commit()
            
            logger.info(
                "failure_recorded",
                failed_skill=failed_skill,
                error_type=error_type
            )
            
            return row[0] if row else None

    async def get_failure_stats(self) -> list[dict]:
        """
        Get failure statistics by skill and error type.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        failed_skill,
                        error_type,
                        COUNT(*) as failure_count,
                        COUNT(DISTINCT goal_id) as unique_goals
                    FROM execution_failures
                    GROUP BY failed_skill, error_type
                    ORDER BY failure_count DESC
                    LIMIT 20
                """)
            )
            rows = result.fetchall()
            
            return [
                {
                    "failed_skill": row[0],
                    "error_type": row[1],
                    "failure_count": row[2],
                    "unique_goals": row[3],
                }
                for row in rows
            ]

    async def get_skill_failure_rates(self) -> list[dict]:
        """
        Get failure rates per skill (compared to total executions).
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    WITH skill_stats AS (
                        SELECT 
                            skill_used,
                            COUNT(*) as total_executions,
                            SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
                        FROM experiences
                        WHERE skill_used IS NOT NULL
                        GROUP BY skill_used
                    ),
                    failure_stats AS (
                        SELECT 
                            failed_skill,
                            COUNT(*) as failures
                        FROM execution_failures
                        GROUP BY failed_skill
                    )
                    SELECT 
                        ss.skill_used,
                        ss.total_executions,
                        ss.successes,
                        COALESCE(fs.failures, 0) as failures,
                        CASE 
                            WHEN ss.total_executions > 0 
                            THEN COALESCE(fs.failures, 0)::float / ss.total_executions 
                            ELSE 0 
                        END as failure_rate
                    FROM skill_stats ss
                    LEFT JOIN failure_stats fs ON ss.skill_used = fs.failed_skill
                    ORDER BY failure_rate DESC
                """)
            )
            rows = result.fetchall()
            
            return [
                {
                    "skill": row[0],
                    "total_executions": row[1],
                    "successes": row[2],
                    "failures": row[3],
                    "failure_rate": row[4],
                }
                for row in rows
            ]

    async def analyze_pipeline_failures(self, capability_name: str) -> dict:
        """
        Analyze failures for a specific capability's pipelines.
        """
        async with AsyncSessionLocal() as session:
            # Get pipelines for capability
            result = await session.execute(
                text("""
                    SELECT 
                        cp.pipeline_id,
                        cp.pipeline_name,
                        cp.skills,
                        cp.total_executions,
                        cp.successful_executions,
                        cp.success_rate
                    FROM capability_pipelines cp
                    WHERE cp.capability_name = :capability_name
                """),
                {"capability_name": capability_name}
            )
            pipelines = result.fetchall()
            
            # Get failures for this capability
            result = await session.execute(
                text("""
                    SELECT 
                        failed_skill,
                        error_type,
                        COUNT(*) as count
                    FROM execution_failures
                    WHERE capability_name = :capability_name
                    GROUP BY failed_skill, error_type
                    ORDER BY count DESC
                """),
                {"capability_name": capability_name}
            )
            failures = result.fetchall()
            
            return {
                "capability_name": capability_name,
                "pipelines": [
                    {
                        "pipeline_id": str(p[0]),
                        "name": p[1],
                        "skills": p[2],
                        "total_executions": p[3] or 0,
                        "successes": p[4] or 0,
                        "success_rate": p[5] or 0,
                    }
                    for p in pipelines
                ],
                "failure_patterns": [
                    {
                        "failed_skill": f[0],
                        "error_type": f[1],
                        "count": f[2],
                    }
                    for f in failures
                ]
            }

    async def suggest_mutations(self, capability_name: str) -> list[dict]:
        """
        Analyze failures and suggest pipeline mutations.
        
        Example:
            - write_file fails with "directory_not_exist"
            - Suggest adding create_directory before write_file
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        failed_skill,
                        error_type,
                        COUNT(*) as count
                    FROM execution_failures
                    WHERE capability_name = :capability_name
                    GROUP BY failed_skill, error_type
                    HAVING COUNT(*) >= 1
                    ORDER BY count DESC
                """),
                {"capability_name": capability_name}
            )
            failure_patterns = result.fetchall()
            
            suggestions = []
            
            for failed_skill, error_type, count in failure_patterns:
                mutation = self._suggest_mutation(failed_skill, error_type)
                if mutation:
                    suggestions.append({
                        "problem": {
                            "skill": failed_skill,
                            "error": error_type,
                            "occurrences": count,
                        },
                        "suggestion": mutation
                    })
            
            return suggestions

    def _suggest_mutation(self, failed_skill: str, error_type: str) -> Optional[dict]:
        """
        Suggest a mutation based on failure pattern.
        
        This is a rule-based system. Could be enhanced with LLM.
        """
        skill_name = failed_skill.split(".")[-1] if "." in failed_skill else failed_skill
        
        # Rule-based mutations
        mutations = {
            ("write_file", "directory_not_exist"): {
                "type": "add_predecessor",
                "skill": "core.create_directory",
                "reason": "Create directory before writing file",
            },
            ("write_file", "permission_denied"): {
                "type": "add_predecessor", 
                "skill": "core.run_command",
                "command": "chmod",
                "reason": "Fix permissions before writing",
            },
            ("web_research", "timeout"): {
                "type": "add_timeout",
                "skill": "core.web_research",
                "timeout_ms": 30000,
                "reason": "Increase timeout for slow requests",
            },
            ("run_command", "command_not_found"): {
                "type": "replace_skill",
                "skill": "core.run_command",
                "alternative": "core.file_search",
                "reason": "Use file search instead of shell command",
            },
        }
        
        return mutations.get((skill_name, error_type))


async def run_failure_analysis():
    """Demo: show failure analysis."""
    engine = FailureAnalysisEngine()
    
    # Record some failures
    print("📝 Recording failures...")
    
    await engine.record_failure(
        goal_id=None,
        pipeline_id=None,
        capability_name="cap_research",
        failed_skill="core.write_file",
        error_type="directory_not_exist",
        error_message="/output/reports/2024 not found",
        context={"path": "/output/reports/2024"}
    )
    
    await engine.record_failure(
        goal_id=None,
        pipeline_id=None, 
        capability_name="cap_research",
        failed_skill="core.write_file",
        error_type="directory_not_exist",
        error_message="/output/data not found",
    )
    
    await engine.record_failure(
        goal_id=None,
        pipeline_id=None,
        capability_name="cap_research",
        failed_skill="core.web_research",
        error_type="timeout",
        error_message="Request timeout after 10s",
    )
    
    print("✅ Failures recorded")
    
    # Get stats
    print("\n📊 Failure Statistics:")
    stats = await engine.get_failure_stats()
    for s in stats:
        print(f"  {s['failed_skill']} + {s['error_type']}: {s['failure_count']} failures")
    
    # Get skill failure rates
    print("\n📈 Skill Failure Rates:")
    rates = await engine.get_skill_failure_rates()
    for r in rates[:5]:
        print(f"  {r['skill']}: {r['failure_rate']:.1%} ({r['failures']}/{r['total_executions']})")
    
    # Suggest mutations
    print("\n💡 Mutation Suggestions:")
    suggestions = await engine.suggest_mutations("cap_research")
    for s in suggestions:
        print(f"  Problem: {s['problem']['skill']} + {s['problem']['error']}")
        print(f"  Suggestion: {s['suggestion']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_failure_analysis())
