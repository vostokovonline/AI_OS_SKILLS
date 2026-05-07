"""
Experience Compression Module
Transforms raw execution traces into structured patterns
"""
import json
import re
from typing import Dict, List, Optional
from uuid import UUID

# Keywords for strategy inference
STRATEGY_PATTERNS = {
    "test-driven": ["test", "проверить", "валидация", "verify", "check"],
    "analysis-first": ["анализ", "метрик", "данные", "analyze", "metrics", "research", "исследовать"],
    "iterative": ["итерац", "повтор", "retry", "цикл", "шаг за шагом"],
    "planning": ["планир", "план", "strategy", "стратег", "roadmap"],
    "creation": ["создать", "build", "сгенерир", "написать", "create", "write"],
    "optimization": ["оптимиз", "улучш", "perfomance", "скорость", "эффектив"],
}


def compress_execution_trace(trace: dict) -> Dict:
    """Compress raw execution trace into structured pattern"""
    if not trace:
        return {}
    
    steps = []
    tools = []
    pitfalls = []
    
    # Extract steps from trace
    if "steps" in trace:
        for step in trace.get("steps", []):
            if isinstance(step, dict):
                step_name = step.get("step", step.get("name", "unknown"))
                steps.append(step_name)
                
                # Extract tools used
                if "tool" in step:
                    tools.append(step["tool"])
                if "skill" in step:
                    tools.append(step["skill"])
                
                # Detect pitfalls (failed steps)
                if step.get("error") or step.get("status") == "failed":
                    pitfalls.append(f"failed: {step_name}")
    
    # Extract errors from trace
    if "errors" in trace:
        for err in trace.get("errors", []):
            pitfalls.append(str(err)[:100])
    
    return {
        "steps": steps[:5],  # Max 5 key steps
        "tools": list(set(tools))[:5],  # Unique tools
        "pitfalls": pitfalls[:3]  # Max 3 pitfalls
    }


def infer_strategy(steps: List[str], title: str = "") -> str:
    """Infer strategy from execution steps and goal title"""
    text = " ".join(steps).lower() + " " + (title or "").lower()
    
    for strategy, keywords in STRATEGY_PATTERNS.items():
        for keyword in keywords:
            if keyword in text:
                return strategy
    
    return "generic_execution"


def compress_goal_experience(goal) -> Dict:
    """Compress a single goal's execution into pattern"""
    # Get execution trace
    trace_data = goal.execution_trace
    if isinstance(trace_data, str):
        try:
            trace_data = json.loads(trace_data)
        except:
            trace_data = {}
    
    # Compress trace
    compressed = compress_execution_trace(trace_data)
    
    # Infer strategy
    strategy = infer_strategy(
        compressed.get("steps", []),
        goal.title or ""
    )
    
    # Calculate pattern score (simpler than full experience_score)
    score = 20 if goal.status == "done" else 0
    score += 15 if compressed.get("steps") else 0
    score += 10 if compressed.get("tools") else 0
    
    return {
        "goal_id": goal.id,
        "original_title": goal.title,
        "strategy": strategy,
        "key_steps": compressed.get("steps", []),
        "tools_used": compressed.get("tools", []),
        "pitfalls": compressed.get("pitfalls", []),
        "outcome": goal.status,
        "experience_score": score
    }


def format_strategy_for_prompt(pattern: Dict) -> str:
    """Format a single pattern for LLM prompt"""
    steps = ", ".join(pattern.get("key_steps", [])[:3])
    pitfalls = pattern.get("pitfalls", [])
    pitfalls_str = f" | Pitfalls: {', '.join(pitfalls)}" if pitfalls else ""
    
    return f"""Strategy: {pattern['strategy']}
Goal: {pattern['original_title'][:50]}
Steps: {steps or 'N/A'}{pitfalls_str}
Outcome: {pattern['outcome']}"""


def format_context_patterns(patterns: List[Dict]) -> str:
    """Format multiple patterns for LLM context"""
    if not patterns:
        return ""
    
    lines = ["=== Relevant Past Strategies ==="]
    for i, p in enumerate(patterns, 1):
        lines.append(f"{i}. {format_strategy_for_prompt(p)}")
    
    return "\n".join(lines)


__all__ = [
    "compress_execution_trace",
    "compress_goal_experience",
    "infer_strategy",
    "format_strategy_for_prompt",
    "format_context_patterns"
]