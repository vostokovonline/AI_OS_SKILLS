"""
Semantic Planning Module

Provides:
- embedding_service: Semantic embeddings for pattern matching
- llm_router: Role-based LLM routing (Planner/Critic/Replanner)
- planning_engine: Critic + Replanner loop
- dag_planner: DAG-based parallel execution planning
- capability_planner: Capability-based planning
"""
from semantic.embedding_service import (
    embed_text,
    cosine_similarity,
    build_embedding_text,
    build_intent_embedding_text,
    get_embedding_dimension,
)
from semantic.llm_router import LLMRouter, get_router, extract_json, llm_func
from semantic.planning_engine import (
    PlanningEngine,
    create_llm_engine,
    planning_engine,
    Plan,
    Task,
    TaskResult,
    ExecutionResult,
    CriticReport,
    Planner,
    LLMCritic,
    Replanner,
    RuleBasedCritic,
    Executor,
    DECOMPOSE_PROMPT,
    CRITIC_PROMPT,
    REPLAN_PROMPT,
)

__all__ = [
    # Embedding
    "embed_text",
    "cosine_similarity",
    "build_embedding_text",
    "build_intent_embedding_text",
    "get_embedding_dimension",
    # Router
    "LLMRouter",
    "get_router",
    "extract_json",
    "llm_func",
    # Engine
    "PlanningEngine",
    "create_llm_engine",
    "planning_engine",
    "Plan",
    "Task",
    "TaskResult",
    "ExecutionResult",
    "CriticReport",
    # Components
    "Planner",
    "LLMCritic",
    "Replanner",
    "RuleBasedCritic",
    "Executor",
    # Prompts
    "DECOMPOSE_PROMPT",
    "CRITIC_PROMPT",
    "REPLAN_PROMPT",
]
