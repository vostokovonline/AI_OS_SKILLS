"""
Goal Evaluation Service - Pure Evaluation Logic
==============================================

Responsibility:
    Evaluate goal completion based on evidence

Does NOT:
    - Transition goal state
    - Modify goal entity
    - Commit transactions

Author: AI-OS Architecture v2.0
Date: 2026-03-10
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from logging_config import get_logger

logger = get_logger(__name__)


class TruthState(str, Enum):
    """Epistemic truth state"""
    TRUE = "true"
    FALSE = "false"
    UNCERTAIN = "uncertain"


@dataclass
class TruthEstimate:
    """
    Probabilistic truth estimate for goal completion.

    Based on BeliefState model.
    """
    confidence_true: float  # 0.0 to 1.0
    confidence_false: float  # 0.0 to 1.0
    uncertainty: float  # 0.0 to 1.0

    # Evidence counts
    evidence_count: int = 0
    artifacts_passed: int = 0
    artifacts_failed: int = 0

    # Subgoal progress (for aggregate goals)
    children_done: int = 0
    children_total: int = 0

    @property
    def state(self) -> TruthState:
        """Determine truth state from confidence"""
        if self.uncertainty > 0.4:
            return TruthState.UNCERTAIN

        if self.confidence_true >= 0.6:
            return TruthState.TRUE
        elif self.confidence_true <= 0.1:
            return TruthState.FALSE
        else:
            return TruthState.UNCERTAIN

    @property
    def is_certain(self) -> bool:
        """Do we have high confidence?"""
        return self.uncertainty < 0.1

    @property
    def likely_status(self) -> str:
        """Map to likely goal status"""
        if self.state == TruthState.TRUE:
            return "done"
        elif self.state == TruthState.FALSE:
            return "incomplete"
        else:
            return "pending"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "confidence_true": round(self.confidence_true, 4),
            "confidence_false": round(self.confidence_false, 4),
            "uncertainty": round(self.uncertainty, 4),
            "state": self.state.value,
            "likely_status": self.likely_status,
            "evidence_count": self.evidence_count,
            "artifacts_passed": self.artifacts_passed,
            "artifacts_failed": self.artifacts_failed,
            "children_done": self.children_done,
            "children_total": self.children_total,
            "is_certain": self.is_certain
        }


class GoalEvaluationService:
    """
    Pure domain service for goal evaluation.

    Evaluates goal completion based on:
    - Artifacts (for atomic goals)
    - Children status (for aggregate goals)
    - Manual approval (for manual mode)
    - Custom evaluator (for strict mode)
    """

    def __init__(self):
        # Dependencies
        self._artifact_registry = None
        self._completion_engine = None

    async def evaluate(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> TruthEstimate:
        """
        Evaluate goal completion based on evidence.

        Args:
            uow: UnitOfWork with active session
            goal: Goal entity to evaluate

        Returns:
            TruthEstimate: Probabilistic estimate

        Note:
            Does NOT modify goal state.
            Caller responsible for transition decision.

        Example:
            >>> service = GoalEvaluationService()
            >>> estimate = await service.evaluate(uow, goal)
            >>> if estimate.likely_status == "done":
            ...     await transition_service.transition(uow, goal.id, "done")
        """
        logger.debug(
            "evaluating_goal",
            goal_id=str(goal.id),
            goal_type=goal.goal_type,
            completion_mode=goal.completion_mode,
            is_atomic=goal.is_atomic
        )

        # Route to appropriate evaluator
        if goal.is_atomic:
            return await self._evaluate_atomic(uow, goal)
        elif goal.completion_mode == "aggregate":
            return await self._evaluate_aggregate(uow, goal)
        elif goal.completion_mode == "manual":
            return await self._evaluate_manual(uow, goal)
        elif goal.completion_mode == "strict":
            return await self._evaluate_strict(uow, goal)
        else:
            # Default evaluation
            return await self._evaluate_default(uow, goal)

    async def _evaluate_atomic(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> TruthEstimate:
        """
        Evaluate atomic goal based on artifacts.

        Rules:
        - At least one passed artifact → high confidence
        - No artifacts → uncertain
        - All failed → false
        """
        if self._artifact_registry is None:
            from artifact_registry import artifact_registry
            self._artifact_registry = artifact_registry

        # Get artifacts
        artifacts = await self._artifact_registry.get_by_goal(uow.session, goal.id)

        passed = [a for a in artifacts if a.verification_status == "passed"]
        failed = [a for a in artifacts if a.verification_status == "failed"]
        pending = [a for a in artifacts if a.verification_status == "pending"]

        # Calculate confidence based on artifacts
        if len(passed) > 0:
            # Have passed artifacts
            confidence_true = 0.9 if len(failed) == 0 else 0.7
            confidence_false = 0.1 if len(failed) == 0 else 0.3
            uncertainty = 0.0
        elif len(pending) > 0:
            # Still evaluating
            confidence_true = 0.3
            confidence_false = 0.2
            uncertainty = 0.5
        else:
            # No artifacts yet
            confidence_true = 0.1
            confidence_false = 0.1
            uncertainty = 0.8

        estimate = TruthEstimate(
            confidence_true=confidence_true,
            confidence_false=confidence_false,
            uncertainty=uncertainty,
            evidence_count=len(artifacts),
            artifacts_passed=len(passed),
            artifacts_failed=len(failed)
        )

        logger.debug(
            "atomic_goal_evaluation",
            goal_id=str(goal.id),
            estimate=estimate.to_dict()
        )

        return estimate

    async def _evaluate_aggregate(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> TruthEstimate:
        """
        Evaluate aggregate goal based on children.

        Rules:
        - All children done → true
        - Some children done → partial
        - No children done → uncertain
        """
        from models import Goal
        from sqlalchemy import select

        # Get children
        stmt = select(Goal).where(Goal.parent_id == goal.id)
        result = await uow.session.execute(stmt)
        children = result.scalars().all()

        if len(children) == 0:
            # No children - uncertain
            return TruthEstimate(
                confidence_true=0.1,
                confidence_false=0.1,
                uncertainty=0.8,
                children_total=0,
                children_done=0
            )

        # Count children by status
        done = sum(1 for c in children if c._status == "done")
        total = len(children)

        # Calculate confidence
        if done == total:
            # All children done
            confidence_true = 0.95
            confidence_false = 0.05
            uncertainty = 0.0
        elif done > 0:
            # Some progress
            confidence_true = 0.4 + (done / total) * 0.3
            confidence_false = 0.2
            uncertainty = 0.3
        else:
            # No progress yet
            confidence_true = 0.1
            confidence_false = 0.1
            uncertainty = 0.8

        estimate = TruthEstimate(
            confidence_true=confidence_true,
            confidence_false=confidence_false,
            uncertainty=uncertainty,
            children_total=total,
            children_done=done
        )

        logger.debug(
            "aggregate_goal_evaluation",
            goal_id=str(goal.id),
            estimate=estimate.to_dict()
        )

        return estimate

    async def _evaluate_manual(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> TruthEstimate:
        """
        Evaluate manual completion goal.

        Looks for DECISION artifact with approval.
        """
        if self._artifact_registry is None:
            from artifact_registry import artifact_registry
            self._artifact_registry = artifact_registry

        artifacts = await self._artifact_registry.get_by_goal(uow.session, goal.id)

        # Look for DECISION artifact
        decision_artifacts = [
            a for a in artifacts
            if a.type == "DECISION" or a.content_kind == "decision"
        ]

        if len(decision_artifacts) > 0:
            # Has decision artifact
            latest_decision = decision_artifacts[-1]
            approved = latest_decision.decision_signals.get("approved", False) if hasattr(latest_decision, 'decision_signals') else False

            if approved:
                return TruthEstimate(
                    confidence_true=0.95,
                    confidence_false=0.05,
                    uncertainty=0.0,
                    evidence_count=1
                )
            else:
                return TruthEstimate(
                    confidence_true=0.1,
                    confidence_false=0.9,
                    uncertainty=0.0,
                    evidence_count=1
                )
        else:
            # No decision yet
            return TruthEstimate(
                confidence_true=0.2,
                confidence_false=0.2,
                uncertainty=0.6,
                evidence_count=0
            )

    async def _evaluate_strict(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> TruthEstimate:
        """
        Evaluate strict mode goal with custom evaluator.

        Uses evaluation_result if available.
        """
        # Check if goal has evaluation_result
        if goal.evaluation_result:
            result = goal.evaluation_result

            confidence = result.get("confidence", 0.5)
            passed = result.get("passed", False)

            if passed:
                return TruthEstimate(
                    confidence_true=confidence,
                    confidence_false=1.0 - confidence,
                    uncertainty=0.0,
                    evidence_count=1
                )
            else:
                return TruthEstimate(
                    confidence_true=0.1,
                    confidence_false=confidence,
                    uncertainty=1.0 - confidence,
                    evidence_count=1
                )

        # No evaluation result yet
        return TruthEstimate(
            confidence_true=0.2,
            confidence_false=0.2,
            uncertainty=0.6,
            evidence_count=0
        )

    async def _evaluate_default(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> TruthEstimate:
        """Default evaluation for unknown modes"""
        return TruthEstimate(
            confidence_true=0.3,
            confidence_false=0.3,
            uncertainty=0.4,
            evidence_count=0
        )

    async def sync_status(
        self,
        uow: "UnitOfWork",
        goal: "Goal"
    ) -> str:
        """
        Sync cached status with current evaluation.

        Updates goal._status based on current evidence.

        Args:
            uow: UnitOfWork
            goal: Goal to sync

        Returns:
            str: New status (also updated in goal._status)
        """
        estimate = await self.evaluate(uow, goal)
        new_status = estimate.likely_status

        # Update internal status (via _internal_set_status)
        if hasattr(goal, '_internal_set_status'):
            goal._internal_set_status(new_status)
        else:
            # Fallback
            object.__setattr__(goal, '_status', new_status)

        logger.info(
            "goal_status_synced",
            goal_id=str(goal.id),
            new_status=new_status,
            estimate=estimate.to_dict()
        )

        return new_status


# Singleton instance
goal_evaluation_service = GoalEvaluationService()
