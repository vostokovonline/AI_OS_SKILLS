"""
Arbitration Result - Decision outcome for logging and analysis.
"""
from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass(frozen=True)
class ArbitrationResult:
    """
    Result of arbitration decision.

    CRITICAL: This is decision trace for learning, not just status.
    """
    selected: List["application.arbitration.scored_intent.ScoredIntent"]
    rejected: List["application.arbitration.scored_intent.ScoredIntent"]
    total_utility: float
    total_cost: float
    budget_remaining: float | None
    timestamp: datetime

    @property
    def selection_rate(self) -> float:
        """Fraction of intents that were selected."""
        total = len(self.selected) + len(self.rejected)
        if total == 0:
            return 0.0
        return len(self.selected) / total

    @property
    def total_count(self) -> int:
        """Total number of intents processed."""
        return len(self.selected) + len(self.rejected)

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "selected_count": len(self.selected),
            "rejected_count": len(self.rejected),
            "total_count": self.total_count,
            "selection_rate": self.selection_rate,
            "total_utility": self.total_utility,
            "total_cost": self.total_cost,
            "budget_remaining": self.budget_remaining,
            "timestamp": self.timestamp.isoformat(),
            "selected": [
                {
                    "goal_id": str(s.goal_id),
                    "utility": s.utility,
                    "cost": s.cost,
                    "risk": s.risk,
                    "confidence": s.confidence,
                }
                for s in self.selected
            ],
            "rejected": [
                {
                    "goal_id": str(s.goal_id),
                    "utility": s.utility,
                    "cost": s.cost,
                    "risk": s.risk,
                    "confidence": s.confidence,
                    "rejection_reason": s.rejection_reason,
                }
                for s in self.rejected
            ],
        }
