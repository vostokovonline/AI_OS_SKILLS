"""
Bulk Operations Layer

Immutable state transitions for goal orchestration.

All operations here:
- Work on snapshots, not ORM objects
- Return descriptions of changes, not mutations
- Are pure functions (testable without database)
"""

from .types import (
    GoalSnapshot,
    Transition,
    BulkTransitionPlan
)

__all__ = [
    "GoalSnapshot",
    "Transition",
    "BulkTransitionPlan",
]
