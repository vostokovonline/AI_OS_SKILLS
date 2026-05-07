"""
Execution Outcomes - Pure function results

CRITICAL: Executor returns outcome, NOT state changes.
"""
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any


@dataclass(frozen=True)
class ExecutionOutcome:
    """
    Pure result of goal execution.

    NO side effects.
    NO state mutations.
    NO database writes.

    Just: what happened + artifacts produced.
    """
    status: Literal["completed", "failed", "error"]
    confidence: float
    attempts: int
    artifacts: list[Dict[str, Any]]

    # Optional diagnostics
    error: Optional[str] = None
    execution_trace: Optional[Dict[str, Any]] = None


__all__ = ["ExecutionOutcome"]
