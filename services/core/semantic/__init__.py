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
from semantic.context_builder import ContextBuilder, get_context_builder
from semantic.plan_memory import PlanMemory, get_plan_memory
from semantic.planning_engine import (
    PlanningEngine,
    create_llm_engine,
    planning_engine,
    Plan,
    Task,
    TaskResult,
    ExecutionResult,
    CriticReport,
    PlanValidator,
    ExecutionValidator,
    Planner,
    LLMCritic,
    Replanner,
    RuleBasedCritic,
    Executor,
    DECOMPOSE_PROMPT,
    CRITIC_PROMPT,
    REPLAN_PROMPT,
)
from semantic.execution_orchestrator import (
    ExecutionOrchestrator,
    ExecutionResult,
    TelemetryEvent,
    get_orchestrator,
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
    # Context Builder
    "ContextBuilder",
    "get_context_builder",
    # Plan Memory
    "PlanMemory",
    "get_plan_memory",
    # Engine
    "PlanningEngine",
    "create_llm_engine",
    "planning_engine",
    "Plan",
    "Task",
    "TaskResult",
    "ExecutionResult",
    "CriticReport",
    "PlanValidator",
    "ExecutionValidator",
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
    # Orchestrator
    "ExecutionOrchestrator",
    "ExecutionResult",
    "TelemetryEvent",
    "get_orchestrator",
]
