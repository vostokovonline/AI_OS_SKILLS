"""
Capital Allocator - System resource state.

Budget is STATE, not config.
This enables future: dynamic budgeting, degradation response, etc.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class CapitalAllocator(Protocol):
    """
    System resource budget state.

    Budget is a STATE that changes over time, not a static config.
    """

    async def current_budget(self) -> float:
        """
        Return available budget for current cycle.

        Returns:
            float: Budget units available
        """
        ...


class FixedBudgetAllocator:
    """
    Fixed budget allocator (placeholder).

    TODO: Replace with dynamic allocator that:
        - Adjusts based on system health
        - Tracks spending vs outcomes
        - Implements capital preservation strategies
        - Responds to degradation signals
    """

    def __init__(self, budget: float = 10.0):
        """
        Initialize with fixed budget.

        Args:
            budget: Fixed budget per cycle
        """
        self._budget = budget

    async def current_budget(self) -> float:
        """Return fixed budget."""
        return self._budget
