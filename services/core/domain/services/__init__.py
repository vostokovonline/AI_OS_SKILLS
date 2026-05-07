"""
Domain Services Package
========================

Pure domain logic for goal operations.

Services:
    - GoalCreationService: Create goals with validation
    - GoalExecutionService: Execute goals (atomic and complex)
    - GoalEvaluationService: Evaluate goal completion
    - GoalOrchestrator: High-level workflow coordination

Usage:
    from domain.services import goal_orchestrator

    async with get_uow() as uow:
        result = await goal_orchestrator.create_and_activate(
            uow=uow,
            title="My goal",
            description="..."
        )
"""

from .goal_creation_service import GoalCreationService, goal_creation_service
from .goal_execution_service import GoalExecutionService, goal_execution_service, ExecutionResult
from .goal_evaluation_service import GoalEvaluationService, goal_evaluation_service, TruthEstimate, TruthState
from .goal_orchestrator import GoalOrchestrator, goal_orchestrator

__all__ = [
    # Services
    "GoalCreationService",
    "GoalExecutionService",
    "GoalEvaluationService",
    "GoalOrchestrator",

    # Singletons
    "goal_creation_service",
    "goal_execution_service",
    "goal_evaluation_service",
    "goal_orchestrator",

    # Data structures
    "ExecutionResult",
    "TruthEstimate",
    "TruthState",
]
