"""
Decision Policy - Strategy for intent selection.

Policy knows HOW to select, Arbitrator knows HOW to run pipeline.
"""
from typing import Protocol, runtime_checkable, List


@runtime_checkable
class DecisionPolicy(Protocol):
    """
    Strategy pattern for intent selection.

    Policy decides WHICH intents to apply based on estimated features.
    """

    async def select(
        self,
        scored: List["application.arbitration.scored_intent.ScoredIntent"],
        budget: float | None
    ) -> List["application.arbitration.scored_intent.ScoredIntent"]:
        """
        Select subset of scored intents.

        Args:
            scored: List of intents with estimated features
            budget: Available budget (None = unlimited)

        Returns:
            List of selected intents (subset of input)
        """
        ...


class GreedyUtilityPolicy:
    """
    Select highest-utility intents first.

    OPTIMIZES: Total expected impact (NOT efficiency density)

    AVOIDS:
        - Bias toward cheap tasks
        - Small-task myopia
        - Missing strategic expensive goals

    This is UTILITY-FIRST greedy, not ratio-greedy.
    Ratio greedy (utility/cost) creates bias to cheap tasks.

    Algorithm:
        1. Sort by ABSOLUTE utility (descending)
        2. Take each if budget allows
        3. Stop when budget exhausted

    TODO:
        - Add risk penalty
        - Add exploration term
        - Add portfolio diversification
    """

    async def select(
        self,
        scored: List["application.arbitration.scored_intent.ScoredIntent"],
        budget: float | None
    ) -> List["application.arbitration.scored_intent.ScoredIntent"]:
        """
        Select highest-utility intents within budget.

        Args:
            scored: List of scored intents
            budget: Available budget (None = take all)

        Returns:
            Selected intents (utility-first order)
        """
        if budget is None:
            # No constraint → take all
            return list(scored)

        # Sort by ABSOLUTE utility (not ratio!)
        ordered = sorted(scored, key=lambda s: s.utility, reverse=True)

        remaining = budget
        selected: List = []

        for intent in ordered:
            if intent.cost <= remaining:
                selected.append(intent)
                remaining -= intent.cost

        return selected
