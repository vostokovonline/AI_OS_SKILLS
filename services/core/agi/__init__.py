"""
AGI Components - Towards Autonomous Intelligence
===============================================

Critical components for AGI-like behavior:

1. ExperienceService - Learning from past executions
2. WorldModel - Understanding environment state
3. StrategyEvolution - Self-improving strategies

These components enable:
    - "What worked before?" (Experience)
    - "What will happen?" (World Model)
    - "How can I improve?" (Strategy Evolution)

Usage:
    from agi import experience_service, world_model, strategy_evolution

    # Learn from execution
    await experience_service.learn_from_execution(result, goal)

    # Predict action effect
    prediction = await world_model.predict_effect("restart server")

    # Select best strategy
    strategy = await strategy_evolution.select_strategy(
        goal_type="achievable",
        complexity=0.7
    )
"""

from .experience_service import (
    ExperienceService,
    experience_service,
    ExperienceRecord,
    OutcomeType
)

from .world_model import (
    WorldModel,
    world_model,
    EntityState,
    Relation,
    Prediction,
    EntityType,
    RelationType
)

from .strategy_evolution import (
    StrategyEvolution,
    strategy_evolution,
    Strategy,
    StrategyEvaluation,
    StrategyType
)

__all__ = [
    # Experience
    "ExperienceService",
    "experience_service",
    "ExperienceRecord",
    "OutcomeType",

    # World Model
    "WorldModel",
    "world_model",
    "EntityState",
    "Relation",
    "Prediction",
    "EntityType",
    "RelationType",

    # Strategy Evolution
    "StrategyEvolution",
    "strategy_evolution",
    "Strategy",
    "StrategyEvaluation",
    "StrategyType",
]
