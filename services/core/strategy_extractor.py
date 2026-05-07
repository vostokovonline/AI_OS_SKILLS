"""
Strategy Extraction - Learning Loop Component
Extracts patterns from execution traces to build reusable strategies
"""
import json
from typing import Optional, Dict, Any
from sqlalchemy import text
from database import AsyncSessionLocal


async def extract_strategy_from_goal(goal_id: str) -> Optional[str]:
    """
    Extract minimal pattern from execution_trace.
    Returns pattern string if successful, None otherwise.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT title, execution_trace, status
                    FROM goals
                    WHERE id = :goal_id
                """),
                {"goal_id": goal_id}
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            title, execution_trace, status = row
            
            if not execution_trace:
                return None
            
            if isinstance(execution_trace, str):
                try:
                    execution_trace = json.loads(execution_trace)
                except:
                    return None
            
            steps = execution_trace.get("steps", [])
            if not steps:
                return None
            
            step_types = []
            for step in steps[:5]:
                step_type = step.get("step") or step.get("type") or step.get("skill_selected", "unknown")
                step_types.append(str(step_type)[:30])
            
            pattern = " → ".join(step_types)
            
            if len(pattern) < 5:
                return None
            
            context = title[:100] if title else "unknown"
            
            strategy_text = f"Pattern: {pattern} | Context: {context}"
            
            await session.execute(
                text("""
                    INSERT INTO learning_strategies (pattern, context, strategy_text, success_rate, usage_count, success_count)
                    VALUES (:pattern, :context, :text, 1.0, 1, 1)
                    ON CONFLICT (pattern) DO UPDATE SET
                        usage_count = learning_strategies.usage_count + 1,
                        success_count = learning_strategies.success_count + 1,
                        success_rate = (learning_strategies.success_count + 1.0) / (learning_strategies.usage_count + 1),
                        last_used_at = NOW()
                """),
                {
                    "pattern": pattern,
                    "context": context,
                    "text": strategy_text
                }
            )
            await session.commit()
            
            return pattern
            
    except Exception:
        return None


async def get_top_strategies(limit: int = 3) -> list:
    """
    Get top performing strategies for injection.
    Only returns strategies with usage_count >= 2 to filter noise.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT pattern, context, strategy_text, success_rate, usage_count
                    FROM learning_strategies
                    WHERE usage_count >= 2
                    ORDER BY success_rate DESC, usage_count DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            
            rows = result.fetchall()
            
            strategies = []
            for row in rows:
                pattern, context, strategy_text, sr, usage = row
                
                formatted = f"[STRATEGY] {pattern} (success: {sr:.0%}, used: {usage}x)"
                strategies.append(formatted)
            
            return strategies
            
    except Exception:
        return []


async def update_strategy_feedback(pattern: str, success: bool) -> None:
    """
    Feedback loop: update strategy stats after goal execution.
    Call this after each goal execution with the pattern and result.
    """
    try:
        async with AsyncSessionLocal() as session:
            if success:
                await session.execute(
                    text("""
                        UPDATE learning_strategies
                        SET 
                            usage_count = usage_count + 1,
                            success_count = success_count + 1,
                            success_rate = (success_count + 1.0) / (usage_count + 1),
                            last_used_at = NOW()
                        WHERE pattern = :pattern
                    """),
                    {"pattern": pattern}
                )
            else:
                await session.execute(
                    text("""
                        UPDATE learning_strategies
                        SET 
                            usage_count = usage_count + 1,
                            fail_count = fail_count + 1,
                            success_rate = success_count::float / NULLIF(usage_count + 1, 0),
                            last_used_at = NOW()
                        WHERE pattern = :pattern
                    """),
                    {"pattern": pattern}
                )
            
            await session.commit()
            
    except Exception:
        pass


__all__ = ["extract_strategy_from_goal", "get_top_strategies", "update_strategy_feedback"]