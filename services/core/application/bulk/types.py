"""
Bulk Operations - Immutable Types

CRITICAL: All types here are FROZEN to prevent mutations.
Bulk operations MUST work on snapshots, never on ORM objects.
"""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID


@dataclass(frozen=True)
class GoalSnapshot:
    """
    Immutable snapshot of goal state for bulk operations.

    CRITICAL:
    - frozen=True prevents ANY mutations
    - Bulk engine works ONLY on these snapshots
    - No Session, no SQLAlchemy, no database access
    """
    id: UUID
    status: str
    progress: float
    parent_id: Optional[UUID]
    depth_level: int
    is_atomic: bool
    goal_type: str
    created_at: float
    updated_at: float

    @classmethod
    def from_orm(cls, goal) -> "GoalSnapshot":
        """
        Create snapshot from ORM object.

        Called ONCE at load time.
        After this, bulk layer never touches ORM.
        """
        return cls(
            id=goal.id,
            status=goal._status,  # Direct attribute access
            progress=goal.progress,
            parent_id=goal.parent_id,
            depth_level=goal.depth_level,
            is_atomic=goal.is_atomic,
            goal_type=goal.goal_type,
            created_at=goal.created_at.timestamp() if goal.created_at else 0.0,
            updated_at=goal.updated_at.timestamp() if goal.updated_at else 0.0
        )


@dataclass(frozen=True)
class Transition:
    """
    Single state transition - description ONLY.

    Does NOT apply changes.
    Just describes WHAT should change.
    """
    goal_id: UUID
    from_status: str
    to_status: str
    reason: str
    actor: str = "system.bulk"

    def to_dict(self) -> dict:
        """Convert to dict for logging/serialization"""
        return {
            "goal_id": str(self.goal_id),
            "from_status": self.from_status,
            "to_status": self.to_status,
            "reason": self.reason,
            "actor": self.actor
        }


@dataclass(frozen=True)
class BulkTransitionPlan:
    """
    Immutable plan for bulk transitions.

    Result of pure computation on snapshots.
    Can be tested without database.
    """
    transitions: tuple[Transition, ...]
    metadata: dict

    def __len__(self) -> int:
        return len(self.transitions)

    def __iter__(self):
        return iter(self.transitions)
