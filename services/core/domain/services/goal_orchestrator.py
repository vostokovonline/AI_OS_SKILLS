"""
Goal Orchestrator - High-Level Workflow Coordination
====================================================

Responsibility:
    Compose domain services into end-to-end workflows

This is the PUBLIC API for goal operations.

For AGI-mode: Orchestrator will be extended with:
    - Experience retrieval
    - Strategy selection
    - World model queries
    - Learning loops

Author: AI-OS Architecture v2.0
Date: 2026-03-10
Phase: Foundation (before AGI extension)
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime, timezone

from logging_config import get_logger

logger = get_logger(__name__)


class GoalOrchestrator:
    """
    High-level orchestrator for goal operations.

    Composes:
        - GoalCreationService
        - GoalExecutionService
        - GoalEvaluationService
        - GoalTransitionService (existing)
        - GoalDomainService (existing)

    Phase 1: Basic orchestration
    Phase 2 (AGI): Add experience + strategy + world model
    """

    def __init__(self):
        from .goal_creation_service import goal_creation_service
        from .goal_execution_service import goal_execution_service
        from .goal_evaluation_service import goal_evaluation_service
        from domain.goal_domain_service import goal_domain_service
        from goal_transition_service import transition_service

        self.creation = goal_creation_service
        self.execution = goal_execution_service
        self.evaluation = goal_evaluation_service
        self.domain = goal_domain_service
        self.transition = transition_service

        # AGI components (Phase 2) - placeholders
        self.experience = None  # TODO: Experience service
        self.strategy = None    # TODO: Strategy service
        self.world_model = None # TODO: World model

    # ========================================================================
    # HIGH-LEVEL WORKFLOWS
    # ========================================================================

    async def create_and_activate(
        self,
        uow: "UnitOfWork",
        title: str,
        description: str = "",
        goal_type: str = "achievable",
        is_atomic: bool = False,
        parent_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        auto_activate: bool = True
    ) -> Dict[str, Any]:
        """
        Create goal and optionally activate it.

        Workflow:
            1. Create goal (pending)
            2. Transition to active (if auto_activate)
            3. Return result

        Args:
            uow: UnitOfWork
            title: Goal title
            description: Goal description
            goal_type: Type of goal
            is_atomic: Is atomic?
            parent_id: Parent goal
            user_id: User ID
            auto_activate: Automatically transition to active

        Returns:
            dict: {goal_id, status, title, ...}
        """
        # Create goal
        goal = await self.creation.create(
            uow=uow,
            title=title,
            description=description,
            goal_type=goal_type,
            is_atomic=is_atomic,
            parent_id=parent_id,
            user_id=user_id
        )

        result = {
            "goal_id": str(goal.id),
            "status": goal._status,
            "title": goal.title,
            "goal_type": goal.goal_type,
            "is_atomic": goal.is_atomic,
            "depth_level": goal.depth_level
        }

        # Optionally activate
        if auto_activate:
            event = self.domain.transition(
                goal=goal,
                new_state="active",
                reason="Goal created and auto-activated"
            )

            logger.info(
                "goal_activated",
                goal_id=str(goal.id),
                from_state=event.from_state,
                to_state=event.to_state
            )

            result["status"] = "active"
            result["transition_event"] = {
                "from": event.from_state,
                "to": event.to_state,
                "reason": event.reason
            }

        return result

    async def execute_and_evaluate(
        self,
        uow: "UnitOfWork",
        goal_id: UUID,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute goal and evaluate result.

        Workflow:
            1. Load goal
            2. Execute (atomic or complex)
            3. Evaluate result
            4. Transition state based on evaluation
            5. Return result

        Args:
            uow: UnitOfWork
            goal_id: Goal to execute
            session_id: Optional session ID

        Returns:
            dict: {success, goal_id, execution_result, evaluation, new_status}
        """
        from infrastructure.uow import GoalRepository

        repo = GoalRepository()
        goal = await repo.get(uow.session, goal_id)

        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        # Execute
        execution_result = await self.execution.execute(
            uow=uow,
            goal=goal,
            session_id=session_id
        )

        # Evaluate
        estimate = await self.evaluation.evaluate(uow=uow, goal=goal)

        # Determine new state
        if execution_result.success and estimate.state.value == "true":
            new_state = "done"
            reason = "Execution successful and evaluation passed"
        elif execution_result.success and estimate.state.value == "uncertain":
            new_state = "active"  # Keep active, waiting for more evidence
            reason = "Execution successful but evaluation uncertain"
        elif not execution_result.success:
            new_state = "incomplete"
            reason = f"Execution failed: {execution_result.error_message}"
        else:
            new_state = "incomplete"
            reason = "Evaluation failed"

        # Transition
        event = self.domain.transition(
            goal=goal,
            new_state=new_state,
            reason=reason
        )

        logger.info(
            "goal_execution_complete",
            goal_id=str(goal_id),
            success=execution_result.success,
            new_state=new_state,
            estimate=estimate.to_dict()
        )

        return {
            "success": execution_result.success,
            "goal_id": str(goal_id),
            "execution_result": execution_result.to_dict(),
            "evaluation": estimate.to_dict(),
            "new_status": new_state,
            "transition_event": {
                "from": event.from_state,
                "to": event.to_state,
                "reason": event.reason
            }
        }

    async def decompose_and_execute_children(
        self,
        uow: "UnitOfWork",
        goal_id: UUID,
        max_depth: int = 1,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Decompose complex goal and execute children.

        Workflow:
            1. Load parent goal
            2. Decompose into subgoals
            3. Execute each subgoal
            4. Aggregate results
            5. Update parent status

        Args:
            uow: UnitOfWork
            goal_id: Parent goal to decompose
            max_depth: Maximum decomposition depth
            session_id: Optional session ID

        Returns:
            dict: {subgoals_created, execution_results, parent_status}
        """
        from infrastructure.uow import GoalRepository

        repo = GoalRepository()
        goal = await repo.get(uow.session, goal_id)

        if goal is None:
            raise ValueError(f"Goal not found: {goal_id}")

        # Execute complex (will decompose)
        execution_result = await self.execution.execute(
            uow=uow,
            goal=goal,
            session_id=session_id
        )

        # Execute each subgoal
        child_results = []
        for subgoal_id in execution_result.subgoal_ids:
            try:
                child_result = await self.execute_and_evaluate(
                    uow=uow,
                    goal_id=subgoal_id,
                    session_id=session_id
                )
                child_results.append(child_result)
            except Exception as e:
                logger.error(
                    "child_execution_failed",
                    subgoal_id=str(subgoal_id),
                    error=str(e)
                )
                child_results.append({
                    "subgoal_id": str(subgoal_id),
                    "success": False,
                    "error": str(e)
                })

        # Evaluate parent
        estimate = await self.evaluation.evaluate(uow=uow, goal=goal)

        return {
            "parent_goal_id": str(goal_id),
            "subgoals_created": len(execution_result.subgoal_ids),
            "subgoal_ids": [str(sid) for sid in execution_result.subgoal_ids],
            "child_results": child_results,
            "parent_evaluation": estimate.to_dict(),
            "parent_status": estimate.likely_status
        }

    # ========================================================================
    # AGI EXTENSIONS (Phase 2) - Placeholders
    # ========================================================================

    async def execute_with_experience(
        self,
        uow: "UnitOfWork",
        goal_id: UUID,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute goal using experience from past executions.

        TODO: Phase 2 - Implement experience retrieval
        """
        # Placeholder for AGI extension
        logger.warning(
            "execute_with_experience_not_implemented",
            goal_id=str(goal_id),
            note="Falling back to basic execution"
        )

        return await self.execute_and_evaluate(uow, goal_id, session_id)

    async def execute_with_strategy(
        self,
        uow: "UnitOfWork",
        goal_id: UUID,
        strategy_id: UUID,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute goal using specific strategy.

        TODO: Phase 2 - Implement strategy selection
        """
        # Placeholder for AGI extension
        logger.warning(
            "execute_with_strategy_not_implemented",
            goal_id=str(goal_id),
            strategy_id=str(strategy_id),
            note="Falling back to basic execution"
        )

        return await self.execute_and_evaluate(uow, goal_id, session_id)

    async def execute_with_world_model(
        self,
        uow: "UnitOfWork",
        goal_id: UUID,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute goal with world model prediction.

        TODO: Phase 3 - Implement world model integration
        """
        # Placeholder for AGI extension
        logger.warning(
            "execute_with_world_model_not_implemented",
            goal_id=str(goal_id),
            note="Falling back to basic execution"
        )

        return await self.execute_and_evaluate(uow, goal_id, session_id)


# Singleton instance
goal_orchestrator = GoalOrchestrator()
