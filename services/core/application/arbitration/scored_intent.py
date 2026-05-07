"""
ScoredIntent - Observable features for decision-making.

CRITICAL: This is OBSERVATION, not decision.
NO score here - that's Policy's job.
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional
from uuid import UUID

if TYPE_CHECKING:
    from application.execution.intents import ExecutionIntent


@dataclass(frozen=True)
class ScoredIntent:
    """
    Observable features of an execution intent.

    Contains ONLY estimations, NO decisions.
    Policy computes score from these features.

    Attributes:
        intent: Original execution intent
        utility: Expected benefit if applied (from estimator)
        cost: Estimated resource cost (from estimator)
        risk: Probability estimate of failure 0.0-1.0 (from estimator)
        confidence: Executor confidence (from intent)
        rejection_reason: Why rejected (None if selected)
    """
    intent: "ExecutionIntent"
    utility: float
    cost: float
    risk: float
    confidence: float
    rejection_reason: Optional[str] = None  # "low_utility" | "high_risk" | "budget_exhausted"

    @property
    def goal_id(self) -> UUID:
        """Convenience access to goal ID."""
        return self.intent.goal_id
