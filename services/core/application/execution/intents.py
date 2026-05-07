"""
Execution Intents - Decisions before application

CRITICAL: These are NOT events.
These are decisions that will be applied atomically.

Pattern:
1. Collect intents (no DB writes)
2. Validate batch (optional)
3. Apply all intents in ONE transaction
4. Emit events after commit
"""
from dataclasses import dataclass
from uuid import UUID
from typing import Literal, Optional, Dict, Any
from datetime import datetime


@dataclass(frozen=True)
class ArtifactData:
    """Artifact metadata without DB reference"""
    artifact_type: str  # "FILE", "KNOWLEDGE", "REPORT", etc.
    content_kind: str  # "code", "text", "json", etc.
    content_location: str  # file path, URL, or inline content
    verification_rule: Optional[str] = None


@dataclass(frozen=True)
class ExecutionIntent:
    """
    Decision: What to do with a goal after execution.

    This is NOT a request to execute.
    This is a decision made AFTER execution.

    OPTIMISTIC LOCKING:
        expected_version: goal.updated_at at snapshot time
        If changed between snapshot and apply → intent skipped
    """
    goal_id: UUID
    expected_version: datetime  # Optimistic lock (goal.updated_at)
    outcome: Literal["completed", "failed", "error"]
    confidence: float
    attempts: int
    artifacts: list[ArtifactData]
    error: Optional[str] = None

    # Optional context for handlers
    execution_time_ms: Optional[int] = None


__all__ = ["ExecutionIntent", "ArtifactData"]
