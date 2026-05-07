"""
Estimators - Feature extraction for decision-making.

Each estimator extracts ONE observable feature from ExecutionIntent.
"""
from typing import Protocol, runtime_checkable
from abc import ABC, abstractmethod


@runtime_checkable
class UtilityEstimator(Protocol):
    """Estimate expected benefit of applying intent."""

    async def estimate(self, intent: "application.execution.intents.ExecutionIntent") -> float:
        """
        Estimate utility value.

        Returns:
            float: Expected utility (higher = better)
        """
        ...


@runtime_checkable
class CostEstimator(Protocol):
    """Estimate resource cost of applying intent."""

    async def estimate(self, intent: "application.execution.intents.ExecutionIntent") -> float:
        """
        Estimate cost value.

        Returns:
            float: Resource cost (budget units)
        """
        ...


@runtime_checkable
class RiskEstimator(Protocol):
    """Estimate risk probability of intent."""

    async def estimate(self, intent: "application.execution.intents.ExecutionIntent") -> float:
        """
        Estimate risk probability.

        Returns:
            float: Risk probability 0.0-1.0 (higher = riskier)
        """
        ...


# =============================================================================
# Minimal Implementations (for MVP)
# =============================================================================

class ConfidenceUtilityEstimator:
    """
    Utility = executor confidence.

    Creates selection pressure based on execution quality.
    """

    async def estimate(self, intent) -> float:
        """Utility is confidence from executor."""
        return intent.confidence if intent.confidence else 0.0


class ConstantCostEstimator:
    """
    Constant cost for all intents.

    TODO: Replace with historical cost data from memory.
    """

    def __init__(self, cost: float = 1.0):
        self._cost = cost

    async def estimate(self, intent) -> float:
        """Fixed cost per intent."""
        return self._cost


class ConfidenceRiskEstimator:
    """
    Risk = 1 - confidence.

    High confidence = low risk.
    Low confidence = high risk.
    """

    async def estimate(self, intent) -> float:
        """Risk is inverse of confidence."""
        conf = intent.confidence if intent.confidence else 0.0
        return 1.0 - conf
