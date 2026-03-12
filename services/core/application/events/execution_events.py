"""
Domain Events - Execution Facts

CRITICAL: These are immutable FACTS about what happened.
Not commands, not requests - completed actions.
"""
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class GoalExecutionFinished:
    """
    Immutable fact: Goal execution completed.

    This is NOT a request to do something.
    This is a record of what ALREADY happened.

    Consumers can react to this fact, but emitter doesn't care.
    """
    goal_id: UUID
    status: str  # "completed" | "failed" | "error"
    confidence: float
    attempts: int
    artifacts_registered: int
    finished_at: datetime

    # Optional context for diagnostics
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None


@dataclass(frozen=True)
class BatchExecutionCompleted:
    """
    Immutable fact: Batch of goals executed.

    Aggregated event for monitoring and batch-level reactions.
    """
    total_goals: int
    completed: int
    failed: int
    started_at: datetime
    finished_at: datetime
    execution_time_ms: int


__all__ = [
    "GoalExecutionFinished",
    "BatchExecutionCompleted",
    "SkillExecuted",
    "ArtifactCreated",
    # Execution Trace Events
    "GoalExecutionStarted",
    "SkillSelected",
    "ArtifactProduced",
    "GoalEvaluated",
    "GoalTransitioned",
]


@dataclass(frozen=True)
class GoalExecutionStarted:
    """Immutable fact: Goal execution started."""
    goal_id: UUID
    goal_title: str
    goal_type: str  # NEW: for cognitive cache by goal_type
    is_atomic: bool
    started_at: datetime


@dataclass(frozen=True)
class SkillSelected:
    """Immutable fact: Skill was selected for goal."""
    goal_id: UUID
    skill_id: str
    skill_name: str
    score: float
    attempt: int
    selected_at: datetime


@dataclass(frozen=True)
class ArtifactProduced:
    """Immutable fact: Artifact was produced by skill."""
    goal_id: UUID
    skill_id: str
    artifact_type: str
    content_kind: str
    verification_status: str
    produced_at: datetime


@dataclass(frozen=True)
class GoalEvaluated:
    """Immutable fact: Goal was evaluated."""
    goal_id: UUID
    outcome: str
    confidence: float
    passed: bool
    artifacts_count: int
    evaluated_at: datetime


@dataclass(frozen=True)
class GoalTransitioned:
    """Immutable fact: Goal state changed."""
    goal_id: UUID
    from_state: str
    to_state: str
    reason: str
    actor: str
    transitioned_at: datetime


@dataclass(frozen=True)
class SkillExecuted:
    """Immutable fact: Skill execution completed."""
    skill_id: str
    goal_id: UUID
    success: bool
    artifacts_count: int
    execution_time_ms: int
    error: Optional[str] = None


@dataclass(frozen=True)
class ArtifactCreated:
    """Immutable fact: Artifact was created."""
    artifact_id: UUID
    goal_id: UUID
    skill_id: str
    artifact_type: str
    content_kind: str
